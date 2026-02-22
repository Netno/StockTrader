import json
import re
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)


async def analyze_sentiment(ticker: str, headline: str) -> dict:
    """Send a news headline to Gemini for short-term sentiment analysis."""
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
            return {
                "sentiment": result.get("sentiment", "NEUTRAL").upper(),
                "score": float(result.get("score", 0.0)),
                "reason": result.get("reason", ""),
            }
    except Exception as e:
        print(f"Gemini error for {ticker}: {e}")

    return {"sentiment": "NEUTRAL", "score": 0.0, "reason": "Analys misslyckades"}
