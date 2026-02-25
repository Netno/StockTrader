# AKTIEMOTOR — Projektinstruktioner

## Vad systemet är

En **rekommendationsmotor** för svenska aktier. Agenten analyserar marknaden och skickar köp/säljrekommendationer. Användaren agerar alltid manuellt på Avanza. Systemet exekverar aldrig affärer automatiskt.

Flödet:

1. KÖP-signal → push-notis → användaren köper på Avanza → bekräftar i appen
2. SÄLJ-signal → push-notis → användaren säljer på Avanza → klickar Stäng i appen

**Allt i systemet ska designas utifrån detta.**

---

## Arkitektur

| Komponent       | Teknologi                    | Plattform                                 |
| --------------- | ---------------------------- | ----------------------------------------- |
| Agent (backend) | Python FastAPI + APScheduler | Railway (port 8080)                       |
| Frontend        | Next.js 16 App Router        | Vercel                                    |
| Databas         | Supabase (PostgreSQL)        | Supabase                                  |
| AI-analys       | Google Gemini 2.5 Flash      | Via google-genai                          |
| Push-notiser    | ntfy.sh                      | Topic: mike_stock_73                      |
| Prisdata        | Yahoo Finance v8 API         | Via Vercel-proxy (Railway IPs blockerade) |

### Viktigt om deployment

- `git push` triggar Railway-deploy automatiskt
- `git push` triggar Vercel **bara om filer under `frontend/` ändrats** (ignoreCommand konfigurerat)
- Vercel har deploymentgräns — pusha inte frontend i onödan
- Testa frontend-ändringar lokalt först: `npm run dev -- -p 4000`
- Lokalt kör frontend på **port 4000** (3000 används av annan app)
- Agent-URL lokalt: pekar på Railway (`NEXT_PUBLIC_AGENT_URL` i `.env.local`)

### Miljövariabler

- `agent/.env` — alla agent-nycklar (Supabase, Gemini, ntfy, FRONTEND_URL)
- `frontend/.env.local` — frontend-nycklar (Supabase, NextAuth, Google OAuth, agent-URL)

---

## Backend (agent/)

### Struktur

```
agent/
  main.py          — FastAPI endpoints
  scheduler.py     — APScheduler jobs + process_ticker()
  config.py        — Konfiguration och TICKERS-dict
  stock_scanner.py — Daglig/veckovis skanning av ~75 aktier
  analysis/
    indicators.py      — Tekniska indikatorer (pandas-ta)
    decision_engine.py — Scoring för köp/sälj, portföljrotation
    sentiment.py       — Gemini sentiment + signalbeskrivning
  data/
    yahoo_client.py    — Hämtar prisdata via Vercel-proxy
    news_fetcher.py    — RSS-nyheter
    insider_fetcher.py — FI-insiderdata
  db/
    supabase_client.py — All databasinteraktion
  notifications/
    ntfy.py            — Push-notiser
```

### Schemalagda jobb

- 08:30 — Morgonkontroll (återställ räknare)
- 08:45 — Morgonsummering (push-notis)
- 08:55 — **Discovery scan** (bred sökning, bara när positioner < MAX_POSITIONS)
- 09:00–17:28 — Trading loop var 2:a minut (köp/säljsignaler)
- 17:35 — Kvällssummering (push-notis)
- 17:45 — Daglig skanning av hela universumet (portföljrotation)
- Söndag 18:00 — Veckovis skanning

### Discovery Mode vs Portfolio Mode

Systemet har två faser:

**Discovery Mode** (positioner < MAX_POSITIONS):
- Varje morgon 08:55 skannas hela universumet (~75 aktier)
- Top ~15 kandidater sätts som aktiv watchlist baserat på kombinerad poäng (40% kandidatkvalitet + 60% köp-pre-score)
- Trading-loopen analyserar dessa bredare under dagen
- Aktier med öppna positioner skyddas alltid
- Manuell trigger: `POST /api/discovery-scan`

**Portfolio Mode** (positioner = MAX_POSITIONS):
- Discovery hoppas över — watchlist är smal (positionerade + reserv)
- Trading-loopen fokuserar på stop-loss/take-profit för öppna positioner
- Rotationslogik letar efter starkare kandidater vid kvällsskanning

### Signallogik

- **KÖP**: score ≥ 60 → sparas som `pending` → push-notis → användaren bekräftar
- **SÄLJ**: score ≥ 55 (baserat på teknisk analys + P&L) → push-notis → användaren agerar manuellt
- **Rotation**: om max positioner nått och ny kandidat score > svagaste + 15 → säljsignal på svagaste
- Ingen auto-execution — användaren agerar alltid

### Kodstandard backend

- Asynkront (async/await) genomgående
- Felhantering med try/except och logger.warning/error
- Inga brytande förändringar mot Supabase-schemat utan genomtänkt migration
- httpx för HTTP-anrop (inte requests)

### Supabase / Databas

- **Row Level Security (RLS)** ska ALLTID aktiveras på nya tabeller: `ALTER TABLE public.<tabell> ENABLE ROW LEVEL SECURITY;`
- Vid nya tabeller: inkludera alltid RLS-aktivering i SQL:en som ges till användaren
- Alla tabeller använder `public`-schemat
- Inga brytande schemaändringar utan migration-plan

---

## Frontend (frontend/)

### Teknologi

- Next.js 16 App Router, React 19, TypeScript
- Tailwind CSS v4
- Supabase JS-klient
- NextAuth (Google OAuth)
- Recharts för grafer

### Design & UX-principer

- **Mörkt tema** genomgående (bg-gray-900, bg-gray-800, borders i gray-800)
- **Mobilanpassat** — push-notiser öppnas på mobil, primära actions måste fungera på liten skärm
- Sidebar dold på mobil (`hidden md:flex`)
- Tabeller dolda på mobil, kortlayout visas istället
- **Tydliga CTA:er** — bekräfta/neka-knappar ska synas tydligt
- `cursor-pointer` på alla knappar och länkar (satt globalt i globals.css)
- Färgkoder: grönt = köp/vinst, rött = sälj/förlust, orange = varning/väntar

### Sidstruktur

```
/dashboard           — Översikt, öppna positioner, portföljnotiser
/dashboard/signals   — Köp/säljsignaler med bekräfta/neka
/dashboard/stocks    — Aktielista med priser
/dashboard/history   — Avslutade affärer
/dashboard/news      — Nyhetsflöde
/dashboard/suggestions — (Används ej aktivt)
```

### API-kommunikation

- `frontend/lib/api.ts` — alla anrop mot Railway-agenten
- Supabase anropas direkt från frontend för notiser och portföljdata
- Vercel-proxy `/api/market/[ticker]` — hämtar prisdata från Yahoo Finance

### Kodstandard frontend

- Server Components som default, `"use client"` bara när interaktivitet krävs
- `revalidate` satt per sida (15–30 sekunder typiskt)
- Inga nya npm-paket utan god anledning (Vercel build-gräns)
- Felhantering med try/catch, aldrig krascha sidan pga API-fel

---

## Viktiga beslut (ändra inte utan anledning)

- **Yahoo Finance via Vercel-proxy** — Railway IPs är blockerade av Yahoo
- **pandas-ta 0.4.67b0** — enda kompatibla versionen med nuvarande beroenden
- **supabase>=2.9.0** — krävs för httpx>=0.28.1 (google-genai-krav)
- **NIXPACKS_PYTHON_VERSION=3.12** — satt som Railway env var, inte i fil
- **Port 8080** på Railway — måste matcha Railway-domänens port
- **Port 4000** lokalt för frontend

---

## Testning

1. Starta frontend lokalt: `npm run dev -- -p 4000` i `frontend/`
2. Agenten körs på Railway (produktionsmiljö)
3. Testa signal-flödet: `POST /api/test-signal` → bekräfta i appen
4. Testa notiser: `POST /api/notify-test`
5. Testa en aktie: `GET /api/test/EVO`
