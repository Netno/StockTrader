import { NextRequest, NextResponse } from 'next/server'

const YAHOO_SYMBOLS: Record<string, string> = {
  'EVO':      'EVO.ST',
  'SINCH':    'SINCH.ST',
  'EMBRAC B': 'EMBRAC-B.ST',
  'HTRO':     'HTRO.ST',
  'SSAB B':   'SSAB-B.ST',
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
  const symbol = YAHOO_SYMBOLS[ticker] ?? ticker
  const type = req.nextUrl.searchParams.get('type') ?? 'price'

  try {
    const range = type === 'history' ? '1y' : '1d'
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
