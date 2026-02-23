import json
import re
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)

# Cache: headline -> sentiment result (lives for the lifetime of the process)
_sentiment_cache: dict[str, dict] = {}


async def analyze_sentiment(ticker: str, headline: str) -> dict:
    """Send a news headline to Gemini for short-term sentiment analysis."""
    if headline in _sentiment_cache:
        return _sentiment_cache[headline]

    prompt = (
        f"Du är en aktieanalytiker. Analysera denna nyhet om {ticker}.\n"
        f"Är den positiv, negativ eller neutral för aktiekursen på kort sikt (1-5 dagar)?\n"
        f'Svara ENDAST med JSON: {{"sentiment": "POSITIVE/NEGATIVE/NEUTRAL", '
        f'"score": -1.0 till 1.0, "reason": "kort motivering"}}\n'
        f"Nyhet: {headline}"
    )

    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        text = response.text.strip()

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            sentiment = {
                "sentiment": result.get("sentiment", "NEUTRAL").upper(),
                "score": float(result.get("score", 0.0)),
                "reason": result.get("reason", ""),
            }
            _sentiment_cache[headline] = sentiment
            return sentiment
    except Exception as e:
        print(f"Gemini error for {ticker}: {e}")

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

    prompt = (
        f"Du är en aktierådgivare. Förklara på enkel svenska varför agenten ger en {action}-rekommendation "
        f"för {ticker} vid kurs {price:.2f} kr.\n\n"
        f"Tekniska skäl:\n{reasons_text}{news_part}\n\n"
        f"Skriv 2-3 meningar som förklarar logiken bakom rekommendationen för en privatperson. "
        f"Var konkret och nämn de viktigaste skälen. Inga rubriker, bara löptext."
    )

    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini description error for {ticker}: {e}")
        return ", ".join(reasons[:3])
