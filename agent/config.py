import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Twelve Data
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Ntfy
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "mike_stock_73")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Frontend URL (used in ntfy links)
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# App settings
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
PAPER_BALANCE = float(os.getenv("PAPER_BALANCE", "0"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "2500"))

# Signal threshold
SIGNAL_THRESHOLD = 60

# Tickers with strategy config
TICKERS = {
    "EVO": {
        "name": "Evolution",
        "strategy": "trend_following",
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.08,
        "atr_multiplier": 1.3,
    },
    "SINCH": {
        "name": "Sinch",
        "strategy": "mean_reversion",
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.095,
        "atr_multiplier": 1.3,
    },
    "EMBRAC B": {
        "name": "Embracer Group",
        "strategy": "news_driven",
        "stop_loss_pct": 0.075,
        "take_profit_pct": 0.14,
        "atr_multiplier": 1.5,
    },
    "HTRO": {
        "name": "Hexatronic",
        "strategy": "breakout",
        "stop_loss_pct": 0.06,
        "take_profit_pct": 0.115,
        "atr_multiplier": 1.3,
    },
    "SSAB B": {
        "name": "SSAB",
        "strategy": "cyclical_trend",
        "stop_loss_pct": 0.045,
        "take_profit_pct": 0.09,
        "atr_multiplier": 1.3,
    },
    "VOLV B": {
        "name": "Volvo",
        "strategy": "cyclical_trend",
        "stop_loss_pct": 0.045,
        "take_profit_pct": 0.09,
        "atr_multiplier": 1.3,
    },
    "EQT": {
        "name": "EQT",
        "strategy": "trend_following",
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10,
        "atr_multiplier": 1.4,
    },
    "AZN": {
        "name": "AstraZeneca",
        "strategy": "news_driven",
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.09,
        "atr_multiplier": 1.3,
    },
}
