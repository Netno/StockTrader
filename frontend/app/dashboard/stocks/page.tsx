import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { AVANZA_URLS } from "@/lib/avanza";

// Matchar trading-loopens 2-minutersintervall — ingen anledning att uppdatera snabbare
export const revalidate = 120;

const strategyLabel: Record<string, string> = {
  trend_following: "Trendföljning",
  mean_reversion: "Mean reversion",
  news_driven: "Nyhetsdriven",
  breakout: "Breakout",
  cyclical_trend: "Cyklisk trend",
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
  if (score === undefined || score === null)
    return <span className="text-gray-600">–</span>;
  const color =
    score >= 60
      ? "bg-green-500/20 text-green-400"
      : score >= 40
        ? "bg-amber-500/20 text-amber-400"
        : "bg-gray-700 text-gray-400";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {score}p {score >= 60 ? "🔔" : ""}
    </span>
  );
}

export default async function StocksPage() {
  // 1. Hämta watchlist direkt från Supabase (undviker Railway-anrop)
  const { data: watchlist = [] } = await supabase
    .from("stock_watchlist")
    .select("*")
    .eq("active", true);

  const tickers = (watchlist ?? []).map((s: any) => s.ticker);
  if (tickers.length === 0)
    return <div className="text-gray-500">Ingen watchlist.</div>;

  // 2. Hämta senaste indikatorer, priser och signaler i parallell från Supabase
  // INGA anrop till Railway eller Yahoo Finance — datan skrivs av trading-loopen var 2:a minut
  // Kör individuella queries per ticker med limit(1) för garanterat senaste per ticker
  const [indicatorResults, priceResults, signalResults] = await Promise.all([
    Promise.all(
      tickers.map((t: string) =>
        supabase
          .from("stock_indicators")
          .select("*")
          .eq("ticker", t)
          .order("timestamp", { ascending: false })
          .limit(1)
          .single(),
      ),
    ),
    Promise.all(
      tickers.map((t: string) =>
        supabase
          .from("stock_prices")
          .select("ticker, price, volume, timestamp")
          .eq("ticker", t)
          .order("timestamp", { ascending: false })
          .limit(1)
          .single(),
      ),
    ),
    Promise.all(
      tickers.map((t: string) =>
        supabase
          .from("stock_signals")
          .select(
            "ticker, score, reasons, stop_loss_price, take_profit_price, signal_type, created_at",
          )
          .eq("ticker", t)
          .order("created_at", { ascending: false })
          .limit(1)
          .single(),
      ),
    ),
  ]);

  // Bygg map: ticker -> senaste rad
  const indMap: Record<string, any> = {};
  for (const { data } of indicatorResults) {
    if (data) indMap[data.ticker] = data;
  }
  const priceMap: Record<string, any> = {};
  for (const { data } of priceResults) {
    if (data) priceMap[data.ticker] = data;
  }
  const sigMap: Record<string, any> = {};
  for (const { data } of signalResults) {
    if (data) sigMap[data.ticker] = data;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Bevakningslista</h1>

      <div className="grid grid-cols-1 gap-4">
        {(watchlist ?? []).map((stock: any) => {
          const ind = indMap[stock.ticker] ?? {};
          const priceRow = priceMap[stock.ticker];
          const sig = sigMap[stock.ticker];
          const price = priceRow?.price;
          const ma50 = ind.ma50;
          const aboveMa50 = price && ma50 && price > ma50;
          const reasons: string[] = sig?.reasons ?? [];

          return (
            <div
              key={stock.ticker}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                {/* Vänster: namn + strategi */}
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
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
                    {(AVANZA_URLS[stock.ticker] ?? stock.avanza_url) && (
                      <a
                        href={AVANZA_URLS[stock.ticker] ?? stock.avanza_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full hover:bg-blue-500/20 transition"
                      >
                        Avanza ↗
                      </a>
                    )}
                  </div>
                </div>

                {/* Höger: pris + score */}
                <div className="flex items-center gap-4">
                  {price && (
                    <div className="text-right">
                      <p className="text-xl font-bold">{price.toFixed(2)} kr</p>
                      <p
                        className={`text-xs ${aboveMa50 ? "text-green-400" : "text-red-400"}`}
                      >
                        {aboveMa50 ? "↑ över MA50" : "↓ under MA50"}
                      </p>
                    </div>
                  )}
                  <ScoreBadge score={ind.buy_score ?? sig?.score} />
                </div>
              </div>

              {/* Indikatorrutnät */}
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-4">
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">RSI</p>
                  <RsiBadge rsi={ind.rsi} />
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">MACD</p>
                  <span
                    className={
                      ind.macd >= 0 ? "text-green-400" : "text-red-400"
                    }
                  >
                    {ind.macd?.toFixed(2) ?? "–"}
                  </span>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">MA50</p>
                  <span className="text-gray-300">
                    {ind.ma50?.toFixed(2) ?? "–"}
                  </span>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">MA200</p>
                  <span className="text-gray-300">
                    {ind.ma200?.toFixed(2) ?? "–"}
                  </span>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">ATR</p>
                  <span className="text-gray-300">
                    {ind.atr?.toFixed(2) ?? "–"}
                  </span>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500 mb-0.5">Volym ×</p>
                  <span
                    className={
                      ind.volume_ratio >= 1.5
                        ? "text-green-400"
                        : "text-gray-300"
                    }
                  >
                    {ind.volume_ratio?.toFixed(1) ?? "–"}×
                  </span>
                </div>
              </div>

              {/* Senaste signalskäl */}
              {reasons.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {reasons.map((r: string, i: number) => (
                    <span
                      key={i}
                      className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full"
                    >
                      {r}
                    </span>
                  ))}
                </div>
              )}

              {/* SL / TP från senaste signal */}
              {sig?.stop_loss_price && (
                <div className="flex gap-4 mt-3 text-xs text-gray-500">
                  <span>
                    SL:{" "}
                    <span className="text-red-400">
                      {sig.stop_loss_price?.toFixed(2)} kr
                    </span>
                  </span>
                  <span>
                    TP:{" "}
                    <span className="text-green-400">
                      {sig.take_profit_price?.toFixed(2)} kr
                    </span>
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
