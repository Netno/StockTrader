# Hur AKTIEMOTOR fungerar
*En guide för den som kan lite om aktiehandel*

---

## Vad är det här?

AKTIEMOTOR är ett personligt verktyg som hjälper dig att hitta rätt tidpunkt att köpa och sälja svenska aktier. Det är en **rekommendationsmotor** — systemet fattar inga beslut åt dig. Det analyserar marknaden, hittar intressanta lägen, och skickar en push-notis till din mobil. **Du** köper eller säljer på Avanza. Systemet håller sedan koll på hur det gick.

---

## Grundläggande begrepp (förenklat)

**Aktie** — en ägarandel i ett börsnoterat företag. Om Evolution (EVO) är värt 10 miljarder och är uppdelat i 100 miljoner aktier, äger du en hundramiljondel av företaget om du köper en aktie.

**Kurs/pris** — vad en aktie kostar just nu på börsen. Priset ändras sekund för sekund när köpare och säljare handlar.

**Teknisk analys** — att titta på hur priset rört sig historiskt för att försöka förutse hur det rör sig framöver. Man tittar inte på om företaget är bra eller dåligt — bara på prisets mönster.

**Position** — en aktie du äger just nu. Att "öppna en position" = att köpa. Att "stänga en position" = att sälja.

**P&L** (Profit & Loss) — din vinst eller förlust. P&L i kr = (sälj-pris − köp-pris) × antal aktier.

**Stop-loss** — ett skyddspris. Om kursen faller till det priset är det en varningssignal att sälja och begränsa förlusten.

**Take-profit** — ett målpris. Om kursen stiger till det priset är det ett bra läge att realisera vinsten.

---

## Det stora flödet — steg för steg

```
Börsen öppnar 09:00
       ↓
Agenten analyserar varje bevakad aktie var 2:e minut
       ↓
   Hittar ett bra köpläge?
      YES → Push-notis till mobilen → Du köper på Avanza → Du bekräftar i appen
      NO  → Fortsätter bevaka
       ↓
   Du äger aktien. Agenten fortsätter bevaka.
       ↓
   Hittar ett säljläge? (Stop-loss / Take-profit / Teknisk signal)
      YES → Push-notis till mobilen → Du säljer på Avanza → Du klickar Stäng i appen
       ↓
Affären sparas med P&L i historiken
```

---

## Del 1: Analysen — hur hittar agenten köp- och säljlägen?

### Tekniska indikatorer

Agenten beräknar ett antal **indikatorer** för varje aktie. Tänk på det som ett batteri av instrument som mäter aktiens "hälsa":

#### RSI — Relative Strength Index
Mäter om en aktie är **översåld** (för billig) eller **överköpt** (för dyr) på kort sikt. Skalan går 0–100.
- RSI under 35 → aktien har fallit mycket snabbt → potentiellt köpläge (+25 poäng)
- RSI över 70 → aktien har stigit mycket snabbt → potentiellt säljläge (+25 poäng)

#### MACD — Moving Average Convergence Divergence
En indikator som fångar **trendskiften**. Tekniskt sett är det skillnaden mellan två glidande medelvärden (12-dagars och 26-dagars).
- MACD korsar sin signallinje uppåt → trenden vänder uppåt → köpsignal (+20 poäng)
- MACD korsar sin signallinje nedåt → trenden vänder nedåt → säljsignal (+20 poäng)

#### Glidande medelvärden — MA50 och MA200
Prisets genomsnitt de senaste 50 respektive 200 handelsdagarna. Aktier "studsar" ofta mot dessa nivåer.
- Pris nära MA50 (inom 2%) → potentiellt stödnivå → +20 poäng
- Pris nära MA200 (within 2%) → starkt långsiktigt stöd → +20 poäng
- Pris under MA50 → aktien är i nedtrend → säljsignal (+20 poäng)

#### Bollinger Bands
Tre linjer runt priset: ett medelvärde + ett övre band + ett undre band. Banden visar hur volatil (ryckig) aktien är.
- Pris rör det undre bandet → aktien är tillfälligt lågt värderad → +10 poäng

#### Volym
Hur mycket av aktien som handlas. Hög volym vid en prisrörelse bekräftar att rörelsen är "äkta".
- Volym 50% högre än snittet → marknaden vaknar till → +15 poäng

#### ATR — Average True Range
Mäter hur mycket aktien rör sig per dag i genomsnitt. Används för att beräkna rimliga stop-loss och take-profit-nivåer som är anpassade till aktiens volatilitet.

### Relativ styrka vs OMXS30
Agenten jämför varje aktie mot **OMXS30-index** (de 30 största bolagen på Stockholmsbörsen). Om aktien stiger mer än index går den bra relativt sett.
- +15% bättre än index (20 dagar) → stark outperformance → +20 poäng
- +5–15% bättre → outperformance → +10 poäng
- -10% sämre → underperformance → **-10 poäng** (köpavdrag), **+15 poäng** (säljbonus)

### Gemini AI — nyhetssentiment
För varje aktie hämtas de senaste nyheterna. Google Gemini 2.5 Flash läser rubriken och bedömer om nyheten är positiv, negativ eller neutral för aktien på kort sikt (1–5 dagar).
- Positiv nyhet → +15 poäng på köpscore
- Negativ nyhet → +15 poäng på säljscore

### Insiderköp
Agenten hämtar data från **Finansinspektionen** om chefer och styrelseledamöter har köpt aktier i det egna bolaget. Stora insiderköp är en stark signal att insynspersoner tror på aktien.
- Insiderköp >500 000 kr → +10 poäng

### Resultatrapport-varning
Börsbolag publicerar **kvartalsrapporter** några gånger per år. Kursen kan röra sig mycket kring rapporten — åt båda håll. Det är ett riskabelt läge att köpa in sig.
- Rapport inom 48 timmar → **-20 poäng** (köpavdrag)

---

## Del 2: Scoring — hur bestäms köp- och säljbeslut?

Alla ovanstående indikatorer ger poäng. Poängen adderas till ett **totalt score**. Signalen skickas bara om poängen är **60 eller högre**.

### Köpscore — exempel
```
RSI 32 (översålt)               +25p
MACD crossover uppåt            +20p
Volym 80% över snitt            +15p
Gemini: Positiv nyhet           +15p
RS vs OMXS30: +12%              +10p
                                ─────
Total:                           85p  → KÖP-signal skickas
```

### Säljscore — exempel
```
RSI 74 (överköpt)               +25p
MACD crossover nedåt            +20p
Pris under MA50                 +20p
                                ─────
Total:                           65p  → SÄLJ-signal skickas
```

### Stop-loss och Take-profit
Beräknas automatiskt baserat på **ATR** (aktiens dagliga rörelse). Formeln är:
- Stop-loss = köppris − (ATR × 1.3) → skyddar mot normala svängningar
- Take-profit = köppris × 1.10 → 10% vinst som mål (kan variera per aktie)

Dessa nivåer skickas med i notisen och visas i appen.

---

## Del 3: Bevakningslistan — vilka aktier analyseras?

Agenten håller en **bevakningslista** med aktier som analyseras aktivt var 2:e minut under handelsdagen (normalt ~10 st). Listan uppdateras automatiskt varje kväll och varje söndag.

### Daglig och veckovis scanning

| Tidpunkt | Vad händer |
|----------|-----------|
| Vardagar 17:45 | Daglig skanning av hela universumet |
| Söndagar 18:00 | Veckovis skanning (samma logik, men mer tid att köra klart) |

Scannern genomsöker ett **universum av ~75 svenska Large/Mid Cap-aktier** och poängsätter var och en efter fyra kriterier:

| Kriterium | Poäng | Förklaring |
|-----------|-------|-----------|
| Daglig volatilitet 2–8% | +30p | Lagom rörig — varken för tråkig eller för ryckig för att handla |
| Hög handelsvolym (>1.5× snitt) | +25p | Mycket folk handlar = lättare att köpa/sälja när du vill |
| Pris över MA50 | +20p | Aktien är i upptrend på medellång sikt |
| Pris över MA200 | +15p | Aktien är i upptrend på lång sikt |
| RSI mellan 30–70 | +10p | Varken extremt översålt eller överköpt — i ett "normalt" läge |

### Vad händer om en bättre aktie hittas?

Scannern jämför de **5 bästa nya kandidaterna** mot de **2 svagaste på bevakningslistan**. Om en ny kandidat har mer än 10 poäng fler än den svagaste, byts den ut automatiskt:

```
Svag på listan:   SINCH  (45p) → avaktiveras
Bättre kandidat:  BURE   (78p) → läggs till
```

Aktier du **äger just nu** byts aldrig ut ur bevakningslistan — agenten fortsätter bevaka dem tills du säljer.

### Notisen du får

När ett byte sker skickas en push-notis:
```
⟳ Watchlist uppdaterad
1 byte(n):
  SINCH (45p) -> BURE (78p)
```

Om inga byten görs skickas ändå en tyst bekräftelse: *"Watchlist-skanning klar — inga byten gjordes."*

Dessa notiser visas i **"Portfoljnotiser"** på dashboarden med en lila ⟳-ikon.

### Portföljrotation (under handelsdagen)

Om alla 3 positioner redan är fyllda och agenten hittar en ny aktie med klart högre köpscore, skickas en **säljrekommendation** på den svagaste positionen du äger:

```
Du äger: EVO (svagast just nu, säljscore 45p)
Ny kandidat: BURE (köpscore 80p, dvs 35p bättre)

→ Notis: "Sälj EVO på Avanza för att frigöra kapital till BURE"
```

Logiken är enkel: sälj det sämsta du äger och byt till det bättre alternativet.

---

## Del 4: Flödet för en köpaffär

### 1. Agenten hittar ett läge
Var 2:e minut analyseras alla bevakade aktier. Om en aktie når 60+ poäng skapas en **väntande signal** i databasen.

### 2. Push-notis på mobilen
Du får en notis via **ntfy.sh**-appen:
```
📈 KÖP-signal: EVO
Pris: 532 kr × 4 aktier = 2 128 kr
Score: 85p | Confidence: 85%
SL: 515 kr | TP: 574 kr
[Klicka för att bekräfta]
```

### 3. Du köper på Avanza
Du öppnar Avanza och köper det antal aktier som rekommenderas. Detta gör **du manuellt** — systemet kan inte handla åt dig.

### 4. Du bekräftar i appen
Du öppnar AKTIEMOTOR-appen (klickar länken i notisen), hittar signalen och klickar **Bekräfta**. Nu vet systemet att du verkligen köpte, och en position öppnas i dashboarden med löpande P&L.

> Om du väljer att inte köpa klickar du **Neka** istället.

---

## Del 5: Flödet för en säljaffär

### 1. Agenten bevakar din position
Var 2:e minut kontrolleras om din aktie har:
- Nått **stop-loss** (kursen har fallit för mycket)
- Nått **take-profit** (kursen har stigit till målet)
- Fått ett säljscore ≥ 60 (tekniska indikatorer pekar nedåt)

### 2. Push-notis på mobilen
```
📉 SÄLJ-signal: EVO
Pris: 574 kr (+7.9%) | P&L: +168 kr
Anledning: Take-profit nådd
Sälj på Avanza och stäng i appen
```

### 3. Du säljer på Avanza
Du säljer manuellt på Avanza.

### 4. Du stänger i appen
I dashboarden klickar du **Stäng** på den öppna positionen. Systemet beräknar och sparar din vinst/förlust.

---

## Del 6: Push-notiser

Notiserna skickas via **ntfy.sh** — en gratis app du installerar på mobilen. Topic: `mike_stock_73`.

**Typer av notiser:**
| Notis | Tid | Innehåll |
|-------|-----|----------|
| Morgonsummering | 08:45 | Portföljvärde, antal positioner, pausade aktier |
| KÖP-signal | Under handelsdagen | Ticker, pris, score, SL/TP, länk till appen |
| SÄLJ-signal | Under handelsdagen | Ticker, pris, P&L, anledning |
| Kvällssummering | 17:35 | Dagens signaler, P&L |

---

## Del 7: Dashboarden — vad ser du?

### Startsidan
- **Tillgänglig kassa** — hur mycket kapital du har kvar att investera
- **Investerat** — summa låst i öppna positioner
- **Avslutade affärer** — antal genomförda affärer
- **Totalt P&L** — total vinst/förlust i kronor
- **Väntande signaler** — köpsignaler som kräver din bekräftelse
- **Öppna positioner** — aktier du äger just nu med löpande P&L
- **Portföljnotiser** — morgen/kvällssummeringar

### Signaler (`/dashboard/signals`)
Lista med alla köp- och säljsignaler. Köpsignaler har bekräfta/neka-knappar. Säljsignaler visar bara "Sälj på Avanza".

### Aktier (`/dashboard/stocks`)
Prislista på alla bevakade aktier.

### Historik (`/dashboard/history`)
Alla avslutade affärer med P&L, anledning till stängning, datum.

### Nyheter (`/dashboard/news`)
Nyhetsflöde med Gemini-sentiment för alla bevakade aktier.

---

## Del 8: Kapitalet — insättning och nollställning

Du sätter in kapital i appen för att systemet ska veta hur mycket du har att handla med. Det påverkar **positionsstorlek** — om du har 10 000 kr och max 3 positioner, investeras ca 2 500 kr per affär.

**Sätta in kapital:** Klicka "+ Sätt in kapital" på dashboarden.

**Nollställa allt:** Klicka "Nollställ" (raderar alla affärer, signaler och insättningar) och gör sedan en ny insättning för att börja om rent.

---

## Del 9: Schemaläggning — när händer vad?

| Tid | Händelse |
|-----|----------|
| 08:30 | Morgonkontroll — nollställer dagliga räknare |
| 08:45 | Morgonsummering — push-notis med portföljöversikt |
| 09:00–17:28 | **Handelsloop var 2:e minut** — analyserar alla bevakade aktier |
| 17:35 | Kvällssummering — push-notis med dagens resultat |
| 17:45 | Daglig skanning — söker igenom 75 aktier, uppdaterar bevakningslistan |
| Söndag 18:00 | Veckovis skanning — samma som daglig men mer grundlig |

Allt detta körs automatiskt på Railway (en molntjänst) — du behöver inte ha datorn igång.

---

## Del 10: Teknisk arkitektur (för den nyfikne)

```
Din mobil (ntfy-app)
     ↑ push-notiser

AKTIEMOTOR-appen (Vercel)
     ↑ visar data, tar emot bekräftelser

Agenten (Railway)
     ├── Analyserar aktier var 2:e minut
     ├── Hämtar prisdata via Vercel-proxy (Yahoo Finance)
     ├── Kallar Gemini AI för nyhetsanalys
     └── Sparar allt i Supabase (databasen)

Supabase (PostgreSQL-databas)
     └── Lagrar signaler, affärer, positioner, nyheter, insättningar
```

Prisdata från Yahoo Finance hämtas via Vercel (en omväg) eftersom Railway-serverns IP-adresser är blockerade av Yahoo.

---

*Systemet hanterar aldrig riktiga pengar automatiskt. Allt bygger på att du agerar på rekommendationerna och köper/säljer på Avanza manuellt.*
