import { NextRequest, NextResponse } from 'next/server'

const YAHOO_SYMBOLS: Record<string, string> = {
  'EVO':      'EVO.ST',
  'SINCH':    'SINCH.ST',
  'EMBRAC B': 'EMBRAC-B.ST',
  'HTRO':     'HTRO.ST',
  'SSAB B':   'SSAB-B.ST',
  'ERIC B':   'ERIC-B.ST',
  'VOLV B':   'VOLV-B.ST',
  'INVE B':   'INVE-B.ST',
  'SEB A':    'SEB-A.ST',
  'SHB A':    'SHB-A.ST',
  'SWED A':   'SWED-A.ST',
  'AZN':      'AZN.ST',
  'ATCO A':   'ATCO-A.ST',
  'ABB':      'ABB.ST',
  'ALFA':     'ALFA.ST',
  'SAND':     'SAND.ST',
  'SKF B':    'SKF-B.ST',
  'HEXA B':   'HEXA-B.ST',
  'NIBE B':   'NIBE-B.ST',
  'BOL':      'BOL.ST',
  'TELE2 B':  'TELE2-B.ST',
  'TELIA':    'TELIA.ST',
  'HM B':     'HM-B.ST',
  'ASSA B':   'ASSA-B.ST',
  'ESSITY B': 'ESSITY-B.ST',
  'LUND B':   'LUND-B.ST',
  'FABG':     'FABG.ST',
  'BETS B':   'BETS-B.ST',
  'CINT':     'CINT.ST',
  'LATO B':   'LATO-B.ST',
  'NOLA B':   'NOLA-B.ST',
  'PEAB B':   'PEAB-B.ST',
  'SWMA':     'SWMA.ST',
  'TOBS B':   'TOBS-B.ST',
  'XVIVO':    'XVIVO.ST',
  'VOLV A':   'VOLV-A.ST',
  'ATCO B':   'ATCO-B.ST',
  'GETI B':   'GETI-B.ST',
  'HUSQ B':   'HUSQ-B.ST',
  'LIFCO B':  'LIFCO-B.ST',
  'LOOMIS':   'LOOMIS.ST',
  'NDA SE':   'NDA-SE.ST',
  'SCA B':    'SCA-B.ST',
  'SECU B':   'SECU-B.ST',
  'SWEC B':   'SWEC-B.ST',
  'TREL B':   'TREL-B.ST',
  'EQT':      'EQT.ST',
  'AXFO':     'AXFO.ST',
  'AAK':      'AAK.ST',
  'CAST':     'CAST.ST',
  'ELUX B':   'ELUX-B.ST',
  'INDU C':   'INDU-C.ST',
  'KINV B':   'KINV-B.ST',
  'ALIV SDB': 'ALIV-SDB.ST',
  'EKTA B':   'EKTA-B.ST',
  'THULE':    'THULE.ST',
  'HUFV A':   'HUFV-A.ST',
  'SAGAX B':  'SAGAX-B.ST',
  'WALL B':   'WALL-B.ST',
  'INDT':     'INDT.ST',
  'JM':       'JM.ST',
  'BURE':     'BURE.ST',
  'DIOS':     'DIOS.ST',
  'HMS':      'HMS.ST',
  'KABE B':   'KABE-B.ST',
  'NCAB':     'NCAB.ST',
  'NOTE':     'NOTE.ST',
  'NYFOSA':   'NYFOSA.ST',
  'OEM B':    'OEM-B.ST',
  'PNDX B':   'PNDX-B.ST',
  'RATO B':   'RATO-B.ST',
  'VBG B':    'VBG-B.ST',
  'ADDT B':   'ADDT-B.ST',
  'HOLMEN B': 'HOLM-B.ST',
  'OMXS30':   '^OMX',
}

// Smart fallback for tickers not in the explicit map:
// "ARJO B" → "ARJO-B.ST", "CAMX" → "CAMX.ST"
function resolveSymbol(ticker: string): string {
  return YAHOO_SYMBOLS[ticker] ?? `${ticker.replace(/ /g, '-')}.ST`
}

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json',
  'Accept-Language': 'en-US,en;q=0.9',
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker: rawTicker } = await params
  const ticker = decodeURIComponent(rawTicker)
  const symbol = resolveSymbol(ticker)
  const type = req.nextUrl.searchParams.get('type') ?? 'price'

  try {
    // Earnings calendar — uses a different Yahoo endpoint
    if (type === 'earnings') {
      const summaryUrl = `https://query1.finance.yahoo.com/v11/finance/quoteSummary/${symbol}?modules=calendarEvents`
      const summaryResp = await fetch(summaryUrl, { headers: HEADERS })
      const summaryJson = await summaryResp.json()

      const earningsDates: any[] =
        summaryJson?.quoteSummary?.result?.[0]?.calendarEvents?.earnings?.earningsDate ?? []

      const nowSec = Date.now() / 1000
      const upcoming = earningsDates.filter((d) => d.raw >= nowSec)
      const chosen = upcoming[0] ?? null

      return NextResponse.json({
        earnings_date: chosen
          ? new Date(chosen.raw * 1000).toISOString().split('T')[0]
          : null,
      })
    }

    const days = parseInt(req.nextUrl.searchParams.get('days') ?? '365')
    const range = type !== 'history' ? '1d'
      : days <= 90  ? '3mo'
      : days <= 180 ? '6mo'
      : days <= 365 ? '1y'
      : '2y'
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=${range}`
    const resp = await fetch(url, { headers: HEADERS })
    const json = await resp.json()

    // Return raw for debugging if needed
    if (req.nextUrl.searchParams.get('debug') === '1') {
      return NextResponse.json(json)
    }

    const result = json?.chart?.result?.[0]
    if (!result) {
      return NextResponse.json({ error: 'No data', raw: json }, { status: 404 })
    }

    if (type === 'history') {
      const timestamps: number[] = result.timestamp ?? []
      const ohlcv = result.indicators?.quote?.[0] ?? {}
      const adjclose = result.indicators?.adjclose?.[0]?.adjclose ?? ohlcv.close

      const data = timestamps.map((ts: number, i: number) => ({
        date:   new Date(ts * 1000).toISOString().split('T')[0],
        open:   ohlcv.open?.[i]   ?? null,
        high:   ohlcv.high?.[i]   ?? null,
        low:    ohlcv.low?.[i]    ?? null,
        close:  adjclose?.[i]     ?? ohlcv.close?.[i] ?? null,
        volume: ohlcv.volume?.[i] ?? null,
      })).filter(r => r.close !== null)

      return NextResponse.json({ data })
    } else {
      const meta = result.meta
      return NextResponse.json({
        price:      meta?.regularMarketPrice ?? 0,
        change_pct: meta?.regularMarketChangePercent ?? 0,
        volume:     meta?.regularMarketVolume ?? 0,
      })
    }
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
