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
  'Accept': '*/*',
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
    if (type === 'history') {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=1y`
      const resp = await fetch(url, { headers: HEADERS })
      const json = await resp.json()
      const result = json?.chart?.result?.[0]
      if (!result) return NextResponse.json({ error: 'No data' }, { status: 404 })

      const timestamps: number[] = result.timestamp ?? []
      const ohlcv = result.indicators?.quote?.[0] ?? {}
      const adjclose = result.indicators?.adjclose?.[0]?.adjclose ?? ohlcv.close

      const data = timestamps.map((ts: number, i: number) => ({
        date: new Date(ts * 1000).toISOString().split('T')[0],
        open:   ohlcv.open?.[i]   ?? null,
        high:   ohlcv.high?.[i]   ?? null,
        low:    ohlcv.low?.[i]    ?? null,
        close:  adjclose?.[i]     ?? ohlcv.close?.[i] ?? null,
        volume: ohlcv.volume?.[i] ?? null,
      })).filter(r => r.close !== null)

      return NextResponse.json({ data })

    } else {
      const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${symbol}?modules=price`
      const resp = await fetch(url, { headers: HEADERS })
      const json = await resp.json()
      const price = json?.quoteSummary?.result?.[0]?.price
      if (!price) return NextResponse.json({ error: 'No data' }, { status: 404 })

      return NextResponse.json({
        price:      price.regularMarketPrice?.raw ?? 0,
        change_pct: price.regularMarketChangePercent?.raw ?? 0,
        volume:     price.regularMarketVolume?.raw ?? 0,
      })
    }
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
