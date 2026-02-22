# 🤖 AKTIEMOTOR – Komplett Projektplan (uppdaterad)

## Stack
| Del | Teknologi |
|-----|-----------|
| Backend / Agent | Python 3.11 + FastAPI |
| Schemaläggning | APScheduler (persistent process, inte cronjob) |
| Databas | Supabase (befintlig org, nya tabeller med prefix `stock_`) |
| Frontend | Next.js 14 + Tailwind CSS + Recharts |
| Auth | NextAuth.js (credentials provider – ej Supabase Auth) |
| Hosting | Railway (både backend och frontend) |
| Push-notiser | ntfy.sh → topic: `mike_stock_73` |
| Aktiedata | `avanza-api` (inofficiellt Python-bibliotek) |
| Nyheter | Google News RSS per aktie |
| Nyhetsanalys (AI) | Google Gemini via AI Studio API (`gemini-1.5-flash`) |
| Teknisk analys | Python-biblioteket `ta` (RSI, MACD, MA, Bollinger Bands, ATR) |
| Insiderdata | Finansinspektionen öppet API |

---

## 📊 Portfölj – Slutgiltiga aktier

Valda baserat på jämförelse av tre oberoende AI-analyser (Claude, ChatGPT, Gemini).
Alla fem bekräftade som genuina tradingaktier med tillräcklig daglig volatilitet.

| Ticker | Bolag | Lista | Daglig volatilitet | Signaler/vecka | Strategi |
|--------|-------|-------|-------------------|----------------|----------|
| **EVO** | Evolution | Large Cap | 2–4% | 1–2 | Trendföljning (SMA50/200 + EMA20) |
| **SINCH** | Sinch | Large Cap | 3–5% | 2–3 | Mean reversion (RSI + Bollinger) |
| **EMBRAC B** | Embracer Group | Large Cap | 4–8% | 2–5 | Nyhetsdriven (VWAP + volymspik) |
| **HTRO** | Hexatronic | Mid Cap | 3–6% | 2–4 | Breakout (Donchian 20 + volym) |
| **SSAB B** | SSAB | Large Cap | 2–5% | 1–3 | Cyklisk trend (SMA50/200 + MACD) |

### Kapitalallokering (10 000 kr)
- Max per position: **25%** (2 500 kr)
- Max simultana positioner: **3 st** (aldrig alla 5 samtidigt)
- Confidence-baserad viktning:
  - Hög (3+ indikatorer): 2 500 kr
  - Medel (2 indikatorer): 1 500–2 000 kr
  - Låg (1 indikator): 1 000 kr

---

## 🧠 Beslutslogik – Poängsystem

Signaler kräver **minst 2–3 indikatorer** åt samma håll. ATR-baserade stop-losses används istället för fasta procentsatser.

### Köpsignal (kräver ≥ 60p)
```
RSI < 35 (översålt)                    → +25p
MACD crossover uppåt                   → +20p
Pris studsar på MA50 eller MA200       → +20p
Volym > 150% av 20-dagars snitt        → +15p
Gemini nyhetssentiment positivt        → +15p
Insiderköp senaste 30 dagar (FI API)   → +10p
Bollinger Band touch undre nivå        → +10p
Rapport inom 48h                       → -20p ⚠️ (agenten pausar)
```

### Säljsignal (kräver ≥ 60p)
```
RSI > 70 (överköpt)                    → +25p
MACD crossover nedåt                   → +20p
Take-profit nådd (se per aktie nedan)  → +30p
Stop-loss nådd (ATR-baserat)           → +50p (alltid sälj)
Gemini nyhetssentiment negativt        → +15p
Close under MA50                       → +20p
```

### Stop-loss och Take-profit per aktie
| Ticker | Stop-loss | Take-profit | Primär strategi |
|--------|-----------|-------------|-----------------|
| EVO | 3–4.5% | 6–10% | Trendföljning |
| SINCH | 4–6% | 7–12% | Mean reversion |
| EMBRAC B | 6–9% (1.5× ATR) | 10–18% | Nyhetsdriven |
| HTRO | 5–7% (1.3× ATR) | 9–14% | Breakout |
| SSAB B | 3.5–5.5% | 7–11% | Cyklisk trend |

### FI Insider-filter
Om teknisk analys säger SÄLJ men en insider köpt för >500 000 kr senaste 30 dagarna → agenten håller igen och flaggar istället.

### Cooldown-regler
- **48h före rapport** → agenten går i cash-läge för den aktien
- **Lågvolymsdagar** (helgdagar, halvdagar) → inga signaler
- **RSI ensamt** räcker aldrig – kräver alltid minst ett kriterium till

---

## 🤖 Gemini AI – Nyhetsanalys

Agenten skickar varje nyhet till Gemini för sentimentanalys:

```python
prompt = f"""
Du är en aktieanalytiker. Analysera denna nyhet om {ticker}.
Är den positiv, negativ eller neutral för aktiekursen på kort sikt (1-5 dagar)?
Svara ENDAST med JSON: 
{{"sentiment": "POSITIVE/NEGATIVE/NEUTRAL", "score": -1.0 till 1.0, "reason": "kort motivering"}}
Nyhet: {headline}
"""
```

Modell: `gemini-1.5-flash` (snabb + gratis inom generous rate limits)

---

## 📱 Notis-format (ntfy.sh)

**Köpsignal:**
```
🟢 KÖP Sinch (SINCH)
Pris: 52.40 kr | Antal: 38 aktier (~1 991 kr)
RSI: 28 (översålt) ✓
Bollinger: Touch undre band ✓
Volym: +165% vs snitt ✓
Gemini: Positivt sentiment ✓
Stop-loss: 49.80 kr (-5%)
Take-profit: 58.20 kr (+11%)
Confidence: 78%
```

**Säljsignal:**
```
🔴 SÄLJ Sinch (SINCH)
Pris: 57.90 kr | Innehav: 38 aktier
Vinst: +10.5% (+209 kr) 🎉
RSI: 71 (överköpt) ✓
Take-profit nådd ✓
Confidence: 81%
```

**Rapport-varning:**
```
⚠️ RAPPORT OM 48H – EMBRAC B
Agenten pausar trading i Embracer
Rapport: Torsdag kl 08:00
Nuvarande position: INGEN
```

**Daglig morgonsummering (08:45):**
```
☀️ Börsen öppnar om 15 min
Portfölj: 10 420 kr (+4.2%)
Öppna positioner: 1 (SSAB B)
Dagens rapporter: HTRO kl 07:30 ⚠️
Agenten bevakar: 4 aktier (HTRO pausad)
```

---

## ⚙️ Agentens schema

```
Vardagar 08:30  → Kontrollera rapportdatum, sätt cooldown-flaggor
Vardagar 08:45  → Skicka morgonsummering via ntfy
Vardagar 09:00–17:30 → Aktiv loop var 2:e minut:
  1. Hämta kurser via avanza-api
  2. Beräkna RSI, MACD, MA, Bollinger, ATR, volymratio
  3. Hämta senaste nyheter (Google News RSS)
  4. Skicka nyheter till Gemini för sentiment
  5. Kontrollera FI insider-data
  6. Kör poängsystemet
  7. Skicka signal om ≥60p och ingen cooldown
  8. Spara allt till Supabase
Vardagar 17:35  → Daglig summering via ntfy
Vardagar 18:00  → Batch-hämtning av nyheter för natten
Helger          → Agenten sover helt
```

---

## 📁 Mappstruktur

```
aktiemotor/
├── agent/
│   ├── main.py
│   ├── scheduler.py
│   ├── config.py
│   ├── requirements.txt
│   ├── data/
│   │   ├── avanza_client.py
│   │   ├── news_fetcher.py
│   │   └── insider_fetcher.py
│   ├── analysis/
│   │   ├── indicators.py       # RSI, MACD, MA, Bollinger, ATR, volym
│   │   ├── sentiment.py        # Gemini API-anrop
│   │   └── decision_engine.py  # Poängsystem + cooldown + signaler
│   ├── notifications/
│   │   └── ntfy.py
│   └── db/
│       └── supabase_client.py
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── login/page.tsx
│   │   └── dashboard/
│   │       ├── page.tsx
│   │       ├── stocks/[ticker]/page.tsx
│   │       ├── signals/page.tsx
│   │       ├── news/page.tsx
│   │       └── history/page.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   └── PaperTradingBanner.tsx
│   │   ├── dashboard/
│   │   │   ├── StatCard.tsx
│   │   │   ├── PortfolioChart.tsx
│   │   │   ├── RsiChart.tsx
│   │   │   ├── BollingerChart.tsx
│   │   │   └── SignalTable.tsx
│   │   ├── stocks/
│   │   │   ├── StockCard.tsx
│   │   │   └── StockDetail.tsx
│   │   └── widgets/
│   │       ├── SentimentWidget.tsx
│   │       ├── EventsWidget.tsx
│   │       └── InsiderWidget.tsx
│   ├── lib/
│   │   ├── auth.ts
│   │   ├── supabase.ts
│   │   └── api.ts
│   └── middleware.ts
│
├── .env.example
├── README.md
└── railway.toml
```

---

## 🗄️ Supabase-tabeller (prefix: `stock_`)

```sql
CREATE TABLE stock_watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  name TEXT NOT NULL,
  avanza_id TEXT,
  strategy TEXT,
  stop_loss_pct NUMERIC,
  take_profit_pct NUMERIC,
  atr_multiplier NUMERIC DEFAULT 1.3,
  active BOOLEAN DEFAULT true,
  cooldown_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stock_prices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  price NUMERIC NOT NULL,
  volume BIGINT,
  timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE stock_indicators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  rsi NUMERIC,
  macd NUMERIC,
  macd_signal NUMERIC,
  macd_histogram NUMERIC,
  ma20 NUMERIC,
  ma50 NUMERIC,
  ma200 NUMERIC,
  ema20 NUMERIC,
  bollinger_upper NUMERIC,
  bollinger_lower NUMERIC,
  atr NUMERIC,
  volume_ratio NUMERIC,
  timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE stock_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  price NUMERIC NOT NULL,
  quantity INT,
  confidence NUMERIC,
  score INT,
  reasons JSONB,
  indicators JSONB,
  stop_loss_price NUMERIC,
  take_profit_price NUMERIC,
  paper_mode BOOLEAN DEFAULT true,
  executed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stock_portfolio (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  action TEXT NOT NULL,
  price NUMERIC NOT NULL,
  quantity INT NOT NULL,
  total_value NUMERIC NOT NULL,
  stop_loss_price NUMERIC,
  take_profit_price NUMERIC,
  paper_mode BOOLEAN DEFAULT true,
  signal_id UUID REFERENCES stock_signals(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stock_news (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  headline TEXT NOT NULL,
  url TEXT,
  sentiment TEXT,
  sentiment_score NUMERIC,
  gemini_reason TEXT,
  source TEXT,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stock_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  event_type TEXT NOT NULL,
  description TEXT,
  amount NUMERIC,
  event_date DATE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🌍 Miljövariabler (.env)

```env
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your-service-role-key

# Avanza
AVANZA_USERNAME=din@email.se
AVANZA_PASSWORD=dittlösenord
AVANZA_TOTP_SECRET=din-totp-secret

# Google AI Studio
GEMINI_API_KEY=din-gemini-api-nyckel
GEMINI_MODEL=gemini-1.5-flash

# Ntfy
NTFY_TOPIC=mike_stock_73

# NextAuth
NEXTAUTH_SECRET=generera-med-openssl
NEXTAUTH_URL=https://din-app.railway.app
DASHBOARD_USERNAME=mike
DASHBOARD_PASSWORD=välj-ett-bra-lösenord

# App
PAPER_TRADING=true
PAPER_BALANCE=10000
MAX_POSITIONS=3
MAX_POSITION_SIZE=2500
```

---

## 📦 Dependencies

**requirements.txt (Python):**
```
fastapi==0.111.0
uvicorn==0.29.0
apscheduler==3.10.4
avanza-api==4.1.0
supabase==2.4.0
httpx==0.27.0
feedparser==6.0.11
google-generativeai==0.5.0
pandas==2.2.2
ta==0.11.0
python-dotenv==1.0.1
```

**package.json (Next.js):**
```
next@14, react@18, tailwindcss@3, recharts@2,
next-auth@4, @supabase/supabase-js@2, lucide-react
```

---

## 🚀 Byggordning

### Steg 1 – Setup (30 min)
- [ ] Skapa GitHub-repo: `aktiemotor`
- [ ] Skapa mappstruktur
- [ ] Skapa Railway-projekt, koppla GitHub-repo
- [ ] Lägg till miljövariabler i Railway

### Steg 2 – Supabase (20 min)
- [ ] Kör SQL ovan i befintlig Supabase-org
- [ ] Mata in de 5 aktierna i `stock_watchlist`

### Steg 3 – Python-agent (3–4 tim)
- [ ] avanza_client.py
- [ ] indicators.py (RSI, MACD, MA, Bollinger, ATR)
- [ ] news_fetcher.py
- [ ] sentiment.py (Gemini)
- [ ] insider_fetcher.py (FI API)
- [ ] decision_engine.py (poängsystem + cooldown)
- [ ] ntfy.py
- [ ] supabase_client.py
- [ ] scheduler.py + main.py

### Steg 4 – Next.js frontend (3–4 tim)
- [ ] Setup + auth
- [ ] Alla sidor och komponenter
- [ ] Realtidsuppdatering via Supabase

### Steg 5 – Paper trading (2–4 veckor)
- [ ] Verifiera notiser och signaler
- [ ] Följ och logga resultat

### Steg 6 – Skarp handel
- [ ] PAPER_TRADING=false
- [ ] 10 000 kr via Avanza 🚀

---

## ❓ FAQ

**Varför Gemini och inte Claude för nyhetsanalys?**
Du har redan Google AI Studio-konto. Gemini 1.5 Flash är gratis och snabb nog för realtidsanalys.

**Kan agenten handla automatiskt?**
Nej – medvetet val. Signal → du klickar i Avanza. Full kontroll.

**Kostar det något?**
Railway: 0 kr | Supabase: 0 kr | ntfy.sh: 0 kr | Gemini: 0 kr | **Totalt: 0 kr/månad**
