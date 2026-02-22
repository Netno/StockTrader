import { NextRequest, NextResponse } from 'next/server'
import yahooFinance from 'yahoo-finance2'

const YAHOO_SYMBOLS: Record<string, string> = {
  'EVO':      'EVO.ST',
  'SINCH':    'SINCH.ST',
  'EMBRAC B': 'EMBRAC-B.ST',
  'HTRO':     'HTRO.ST',
  'SSAB B':   'SSAB-B.ST',
}

export async function GET(
  req: NextRequest,
  { params }: { params: { ticker: string } }
) {
  const ticker = decodeURIComponent(params.ticker)
  const symbol = YAHOO_SYMBOLS[ticker] ?? ticker
  const type = req.nextUrl.searchParams.get('type') ?? 'price'

  try {
    if (type === 'history') {
      const result = await yahooFinance.historical(symbol, {
        period1: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        interval: '1d',
      })
      return NextResponse.json({ data: result })
    } else {
      const result = await yahooFinance.quote(symbol)
      return NextResponse.json({
        price: result.regularMarketPrice,
        change_pct: result.regularMarketChangePercent,
        volume: result.regularMarketVolume,
      })
    }
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
