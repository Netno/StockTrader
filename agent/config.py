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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-3-27b-it")

# Ntfy
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "mike_stock_73")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Frontend URL (used in ntfy links)
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# App settings
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
PAPER_BALANCE = float(os.getenv("PAPER_BALANCE", "0"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "4"))
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "2000"))

# Signal threshold
SIGNAL_THRESHOLD = 60
