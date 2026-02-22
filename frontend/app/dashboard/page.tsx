import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import StatCard from "@/components/dashboard/StatCard";
import SignalActions from "@/components/dashboard/SignalActions";
import TradeClose from "@/components/dashboard/TradeClose";
import Link from "next/link";

export const revalidate = 15;

const notifIcon: Record<string, string> = {
  morning_summary: "☀",
  evening_summary: "☾",
  scan_suggestion: "⟳",
  info:            "i",
};

const notifColor: Record<string, string> = {
  morning_summary: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  evening_summary: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
  scan_suggestion: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  info:            "bg-gray-700 text-gray-400 border-gray-600",
};

export default async function DashboardPage() {
  const [signals, positions, trades, summary, portfolioNotifs] = await Promise.allSettled([
    api.signals(50),
    api.positions(),
    api.trades("closed"),
    api.summary(),
    supabase
      .from("stock_notifications")
      .select("*")
      .is("ticker", null)
      .order("created_at", { ascending: false })
      .limit(15)
      .then((r) => r.data ?? []),
  ]);

  const signalData    = signals.status    === "fulfilled" ? signals.value    : [];
  const positionsData = positions.status  === "fulfilled" ? positions.value  : {};
  const tradesData    = trades.status     === "fulfilled" ? trades.value     : [];
  const summaryData   = summary.status    === "fulfilled" ? summary.value    : null;
  const notifData     = portfolioNotifs.status === "fulfilled" ? portfolioNotifs.value : [];

  const pendingSignals = signalData.filter(
    (s: any) => s.signal_type === "BUY" && s.status === "pending"
  );
  const openCount   = Object.keys(positionsData).length;
  const totalTrades = tradesData.length;
  const totalPnlKr  = tradesData.reduce((s: number, t: any) => s + (t.pnl_kr ?? 0), 0);

  // Invested value from open positions
  const invested = Object.values(positionsData as Record<string, any>).reduce(
    (s: number, p: any) => s + p.price * p.quantity,
    0
  );

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Tillgänglig kassa"
          value={`${(summaryData?.available_cash ?? 0).toFixed(0)} kr`}
          sub={`av ${(summaryData?.total_deposited ?? 0).toFixed(0)} kr insatt`}
        />
        <StatCard label="Investerat" value={`${invested.toFixed(0)} kr`} sub={`${openCount} position${openCount !== 1 ? "er" : ""}`} />
        <StatCard label="Avslutade affärer" value={String(totalTrades)} />
        <StatCard
          label="Totalt P&L"
          value={`${totalPnlKr >= 0 ? "+" : ""}${totalPnlKr.toFixed(0)} kr`}
          sub={totalTrades > 0 ? `${Math.round(
            (tradesData.filter((t: any) => (t.pnl_kr ?? 0) > 0).length / totalTrades) * 100
          )}% vinst` : undefined}
        />
      </div>

      {/* Pending signals banner */}
      {pendingSignals.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-amber-400">
              {pendingSignals.length} köpsignal{pendingSignals.length > 1 ? "er" : ""} väntar på bekräftelse
            </p>
            <Link href="/dashboard/signals" className="text-xs text-amber-400/70 hover:text-amber-300 transition">
              Se alla signaler →
            </Link>
          </div>
          {pendingSignals.slice(0, 3).map((s: any) => (
            <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <Link href={`/dashboard/stocks/${s.ticker}`} className="font-bold hover:text-blue-400 transition">
                      {s.ticker}
                    </Link>
                    <span className="text-xs text-gray-500">
                      {new Date(s.created_at).toLocaleString("sv-SE", {
                        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-lg font-bold">{s.price?.toFixed(2)} kr</p>
                  <p className="text-xs text-gray-400">
                    {s.quantity} aktier &middot; ~{(s.price * s.quantity)?.toFixed(0)} kr &middot; Score {s.score}p
                  </p>
                  {s.indicators?.signal_description && (
                    <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                      {s.indicators.signal_description}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 text-xs">
                  <span className="text-red-400">SL {s.stop_loss_price?.toFixed(2)}</span>
                  <span className="text-green-400">TP {s.take_profit_price?.toFixed(2)}</span>
                </div>
              </div>
              <div className="mt-3">
                <SignalActions signalId={s.id} status={s.status} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Open positions */}
        <div className="xl:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-300">Öppna positioner</h2>
          </div>
          {openCount === 0 ? (
            <p className="text-gray-600 text-sm">
              Inga öppna positioner. Köpsignaler dyker upp här när agenten hittar möjligheter.
            </p>
          ) : (
            <div className="space-y-3">
              {Object.entries(positionsData as Record<string, any>).map(([ticker, pos]) => {
                const pnlColor = pos.pnl_kr >= 0 ? "text-green-400" : "text-red-400";
                return (
                  <div key={ticker} className="bg-gray-800 rounded-xl p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Link href={`/dashboard/stocks/${ticker}`} className="font-bold hover:text-blue-400 transition">
                            {ticker}
                          </Link>
                          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">
                            Öppet
                          </span>
                        </div>
                        <p className="text-sm text-gray-300">
                          Ingatt {pos.price?.toFixed(2)} kr &times; {pos.quantity} st
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          Aktuellt {pos.current_price?.toFixed(2)} kr
                        </p>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold text-lg ${pnlColor}`}>
                          {pos.pnl_kr >= 0 ? "+" : ""}{pos.pnl_kr?.toFixed(0)} kr
                        </p>
                        <p className={`text-xs ${pnlColor}`}>
                          {pos.pnl_pct >= 0 ? "+" : ""}{pos.pnl_pct?.toFixed(1)}%
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3">
                      <div className="flex gap-4 text-xs">
                        <span className="text-red-400">SL {pos.stop_loss_price?.toFixed(2)}</span>
                        <span className="text-green-400">TP {pos.take_profit_price?.toFixed(2)}</span>
                      </div>
                      {pos.trade_id && <TradeClose tradeId={pos.trade_id} />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Portfolio notifications */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Portföljnotiser</h2>
          {notifData.length === 0 ? (
            <p className="text-gray-600 text-sm">
              Inga notiser än. Morgon- och kvällssummeringar dyker upp här.
            </p>
          ) : (
            <div className="space-y-3">
              {(notifData as any[]).map((n) => (
                <div key={n.id} className="flex gap-3">
                  <div
                    className={`mt-0.5 w-6 h-6 rounded-full border flex items-center justify-center text-xs font-bold shrink-0 ${
                      notifColor[n.type] ?? notifColor.info
                    }`}
                  >
                    {notifIcon[n.type] ?? "i"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-300">{n.title}</p>
                    <pre className="text-xs text-gray-500 mt-0.5 whitespace-pre-wrap font-sans leading-relaxed line-clamp-3">
                      {n.message}
                    </pre>
                  </div>
                  <p className="text-xs text-gray-700 shrink-0">
                    {new Date(n.created_at).toLocaleTimeString("sv-SE", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
