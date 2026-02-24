import asyncio
import json
import logging
import re
import time
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=GEMINI_API_KEY)

# Cache: headline -> (result, expires_at) — 6 timmars TTL
_sentiment_cache: dict[str, tuple] = {}
_SENTIMENT_TTL = 6 * 3600  # 6 timmar

_RATE_LIMIT_WAIT = 6  # sekunder att vänta vid 429 (Free Tier: 10 RPM = 6s/anrop)

# Gemini API call counter (for logging)
_gemini_call_count = 0


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate" in msg or "resource_exhausted" in msg


async def _call_gemini(prompt: str, temperature: float = 0.1, context: str = "") -> str | None:
    """Kör ett Gemini-anrop med ett automatiskt retry vid rate limit (429).
    
    Args:
        prompt: Prompten att skicka till Gemini.
        temperature: Modellens temperatur.
        context: Beskrivning av anropet för loggning (t.ex. 'sentiment:EVO', 'description:SINCH:BUY').
    """
    global _gemini_call_count
    _gemini_call_count += 1
    call_id = _gemini_call_count
    prompt_len = len(prompt)
    
    logger.info(f"[Gemini #{call_id}] START {context} | modell={GEMINI_MODEL} | temp={temperature} | prompt={prompt_len} tecken")
    t0 = time.monotonic()
    
    for attempt in range(2):
        try:
            # Kör synkrona Gemini-anropet i en thread för att inte blockera event loop
            response = await asyncio.to_thread(
                _client.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            elapsed = time.monotonic() - t0
            response_text = response.text.strip()
            logger.info(
                f"[Gemini #{call_id}] OK {context} | {elapsed:.1f}s | svar={len(response_text)} tecken"
            )
            return response_text
        except Exception as e:
            elapsed = time.monotonic() - t0
            if _is_rate_limit(e) and attempt == 0:
                logger.warning(
                    f"[Gemini #{call_id}] RATE LIMIT {context} | {elapsed:.1f}s | "
                    f"väntar {_RATE_LIMIT_WAIT}s och försöker igen"
                )
                await asyncio.sleep(_RATE_LIMIT_WAIT)
                t0 = time.monotonic()  # reset timer för retry
                continue
            logger.error(
                f"[Gemini #{call_id}] FEL {context} | {elapsed:.1f}s | {type(e).__name__}: {e}"
            )
            return None
    return None


async def analyze_sentiment(ticker: str, headline: str) -> dict:
    """Send a news headline to Gemini for short-term sentiment analysis."""
    entry = _sentiment_cache.get(headline)
    if entry and time.monotonic() < entry[1]:
        logger.info(f"[Gemini CACHE HIT] sentiment:{ticker} | headline='{headline[:60]}...'")
        return entry[0]

    logger.info(f"[Gemini CACHE MISS] sentiment:{ticker} | headline='{headline[:60]}...'")

    prompt = (
        f"Du är en aktieanalytiker. Analysera denna nyhet om {ticker}.\n"
        f"Är den positiv, negativ eller neutral för aktiekursen på kort sikt (1-5 dagar)?\n"
        f'Svara ENDAST med JSON: {{"sentiment": "POSITIVE/NEGATIVE/NEUTRAL", '
        f'"score": -1.0 till 1.0, "reason": "kort motivering"}}\n'
        f"Nyhet: {headline}"
    )

    text = await _call_gemini(prompt, temperature=0.1, context=f"sentiment:{ticker}")
    if text:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                sentiment = {
                    "sentiment": result.get("sentiment", "NEUTRAL").upper(),
                    "score": float(result.get("score", 0.0)),
                    "reason": result.get("reason", ""),
                }
                _sentiment_cache[headline] = (sentiment, time.monotonic() + _SENTIMENT_TTL)
                logger.info(
                    f"[Gemini RESULTAT] sentiment:{ticker} | {sentiment['sentiment']} "
                    f"(score={sentiment['score']:.2f}) | {sentiment['reason'][:80]}"
                )
                return sentiment
            except Exception as e:
                logger.warning(f"[Gemini JSON-FEL] sentiment:{ticker} | {e} | raw='{text[:200]}'")
        else:
            logger.warning(f"[Gemini FORMAT-FEL] sentiment:{ticker} | Inget JSON i svar: '{text[:200]}'")

    logger.warning(f"[Gemini FALLBACK] sentiment:{ticker} | Returnerar NEUTRAL")
    return {"sentiment": "NEUTRAL", "score": 0.0, "reason": "Analys misslyckades"}


async def generate_signal_description(
    ticker: str,
    signal_type: str,
    price: float,
    reasons: list[str],
    news_headline: str = "",
) -> str:
    """Generate a plain-Swedish explanation of why this signal was triggered."""
    action = "KÖP" if signal_type == "BUY" else "SÄLJ"
    reasons_text = "\n".join(f"- {r}" for r in reasons)
    news_part = f"\nSenaste nyhet: {news_headline}" if news_headline else ""
    context = f"description:{ticker}:{signal_type}"

    logger.info(f"[Gemini] Genererar signalbeskrivning för {ticker} ({action}) vid {price:.2f} kr")

    prompt = (
        f"Du är en aktierådgivare. Förklara på enkel svenska varför agenten ger en {action}-rekommendation "
        f"för {ticker} vid kurs {price:.2f} kr.\n\n"
        f"Tekniska skäl:\n{reasons_text}{news_part}\n\n"
        f"Skriv 2-3 meningar som förklarar logiken bakom rekommendationen för en privatperson. "
        f"Var konkret och nämn de viktigaste skälen. Inga rubriker, bara löptext."
    )

    text = await _call_gemini(prompt, temperature=0.3, context=context)
    if text:
        logger.info(f"[Gemini RESULTAT] description:{ticker} | '{text[:100]}...'")
        return text

    logger.warning(f"[Gemini FALLBACK] description:{ticker} | Använder skäl som fallback")
    return ", ".join(reasons[:3])
