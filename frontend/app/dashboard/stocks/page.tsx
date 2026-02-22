import Link from "next/link";
import { api } from "@/lib/api";

export const revalidate = 60;

const strategyLabel: Record<string, string> = {
  trend_following: "Trendföljning",
  mean_reversion:  "Mean reversion",
  news_driven:     "Nyhetsdriven",
  breakout:        "Breakout",
  cyclical_trend:  "Cyklisk trend",
};

function RsiBadge({ rsi }: { rsi?: number }) {
  if (!rsi) return <span className="text-gray-600">–</span>;
  const color =
    rsi < 35 ? "text-green-400" : rsi > 70 ? "text-red-400" : "text-gray-300";
  const label = rsi < 35 ? "Översålt" : rsi > 70 ? "Överköpt" : "Neutral";
  return (
    <span className={color}>
      {rsi.toFixed(0)} <span className="text-xs text-gray-500">({label})</span>
    </span>
  );
}

function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return <span className="text-gray-600">–</span>;
  const color =
    score >= 60 ? "bg-green-500/20 text-green-400" :
    score >= 40 ? "bg-amber-500/20 text-amber-400" :
                  "bg-gray-700 text-gray-400";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {score}p {score >= 60 ? "🔔" : ""}
    </span>
  );
}

async function fetchStockData(ticker: string) {
  try {
    return await api.testTicker(ticker);
  } catch {
    return null;
  }
}

export default async function StocksPage() {
  const watchlist = await api.watchlist().catch(() => []);

  // Fetch live data for all watchlist stocks in parallel
  const stockData = await Promise.all(
    watchlist.map(async (stock: any) => {
      const live = await fetchStockData(stock.ticker);
      return { ...stock, live };
    })
  );

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Bevakningslista</h1>

      <div className="grid grid-cols-1 gap-4">
        {stockData.map((stock) => {
          const live = stock.live;
          const ind = live?.indicators ?? {};
          const price = live?.price;
          const ma50 = ind.ma50;
          const aboveMa50 = price && ma50 && price > ma50;

          return (
            <div
              key={stock.ticker}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                {/* Left: name + strategy */}
                <div>
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/dashboard/stocks/${stock.ticker}`}
                      className="text-lg font-bold hover:text-blue-400 transition"
                    >
                      {stock.ticker}
                    </Link>
                    <span className="text-gray-400 text-sm">{stock.name}</span>
                    <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">
                      {strategyLabel[stock.strategy] ?? stock.strategy}
                    </span>
                  </div>
                  {live?.error && (
                    <p className="text-red-400 text-xs mt-1">{live.error}</p>
                  )}
                </div>

                {/* Right: price + score */}
                <div className="flex items-center gap-4">
                  {price && (
                    <div className="text-right">
                      <p className="text-xl font-bold">{price.toFixed(2)} kr</p>
                      <p className={`text-xs ${aboveMa50 ? "text-green-400" : "text-red-400"}`}>
                        {aboveMa50 ? "↑ över MA50" : "↓ under MA50"}
                      </p>
                    </div>
                  )}
                  <ScoreBadge score={live?.buy_score} />
                </div>
              </div>

              {/* Indicator grid */}
              {!live?.error && (
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-4">
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">RSI</p>
                    <RsiBadge rsi={ind.rsi} />
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">MACD</p>
                    <span className={ind.macd >= 0 ? "text-green-400" : "text-red-400"}>
                      {ind.macd?.toFixed(2) ?? "–"}
                    </span>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">MA50</p>
                    <span className="text-gray-300">{ind.ma50?.toFixed(2) ?? "–"}</span>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">MA200</p>
                    <span className="text-gray-300">{ind.ma200?.toFixed(2) ?? "–"}</span>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">ATR</p>
                    <span className="text-gray-300">{ind.atr?.toFixed(2) ?? "–"}</span>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500 mb-0.5">Volym ×</p>
                    <span className={ind.volume_ratio >= 1.5 ? "text-green-400" : "text-gray-300"}>
                      {ind.volume_ratio?.toFixed(1) ?? "–"}×
                    </span>
                  </div>
                </div>
              )}

              {/* Buy reasons */}
              {live?.buy_reasons?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {live.buy_reasons.map((r: string, i: number) => (
                    <span
                      key={i}
                      className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full"
                    >
                      {r}
                    </span>
                  ))}
                </div>
              )}

              {/* SL / TP */}
              {live?.stop_loss && (
                <div className="flex gap-4 mt-3 text-xs text-gray-500">
                  <span>SL: <span className="text-red-400">{live.stop_loss?.toFixed(2)} kr</span></span>
                  <span>TP: <span className="text-green-400">{live.take_profit?.toFixed(2)} kr</span></span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
