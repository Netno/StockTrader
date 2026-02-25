import { api } from "@/lib/api";
import Link from "next/link";

export const revalidate = 30;

export default async function HistoryPage() {
  let trades: any[] = [];
  try {
    trades = await api.trades("closed");
  } catch {}

  const totalPnlKr  = trades.reduce((s, t) => s + (t.pnl_kr ?? 0), 0);
  const winners     = trades.filter((t) => (t.pnl_kr ?? 0) > 0);
  const losers      = trades.filter((t) => (t.pnl_kr ?? 0) <= 0);
  const winRate     = trades.length > 0 ? Math.round((winners.length / trades.length) * 100) : 0;

  const closeReasonLabel: Record<string, string> = {
    stop_loss:   "Stop-loss nådd",
    take_profit: "Take-profit nådd",
    signal:      "Säljsignal",
    manual:      "Stängd manuellt",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Handelshistorik</h1>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 text-xs mb-1">Totalt resultat</p>
          <p className={`text-2xl font-bold ${totalPnlKr >= 0 ? "text-green-400" : "text-red-400"}`}>
            {totalPnlKr >= 0 ? "+" : ""}{totalPnlKr.toFixed(0)} kr
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 text-xs mb-1">Affärer</p>
          <p className="text-2xl font-bold">{trades.length}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 text-xs mb-1">Vinstprocent</p>
          <p className={`text-2xl font-bold ${winRate >= 50 ? "text-green-400" : "text-red-400"}`}>
            {winRate}%
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 text-xs mb-1">Vinst / Förlust</p>
          <p className="text-lg font-bold">
            <span className="text-green-400">{winners.length}</span>
            <span className="text-gray-600 mx-1">/</span>
            <span className="text-red-400">{losers.length}</span>
          </p>
        </div>
      </div>

      {/* Trades — desktop table */}
      <div className="hidden md:block bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="p-4">Öppnad</th>
              <th className="p-4">Stängd</th>
              <th className="p-4">Ticker</th>
              <th className="p-4">Inpris</th>
              <th className="p-4">Utpris</th>
              <th className="p-4">Antal</th>
              <th className="p-4">Orsak</th>
              <th className="p-4 text-right">Resultat</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {trades.length === 0 && (
              <tr>
                <td colSpan={8} className="p-6 text-center text-gray-500">
                  Inga avslutade affärer än.
                </td>
              </tr>
            )}
            {trades.map((t: any) => {
              const pnl = t.pnl_kr ?? 0;
              const pnlPct = t.pnl_pct ?? 0;
              return (
                <tr key={t.id} className="hover:bg-gray-800/30 transition">
                  <td className="p-4 text-gray-400 whitespace-nowrap text-xs">
                    {new Date(t.opened_at).toLocaleString("sv-SE", {
                      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm",
                    })}
                  </td>
                  <td className="p-4 text-gray-400 whitespace-nowrap text-xs">
                    {t.closed_at
                      ? new Date(t.closed_at).toLocaleString("sv-SE", {
                          day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm",
                        })
                      : "–"}
                  </td>
                  <td className="p-4 font-semibold">
                    <Link href={`/dashboard/stocks/${t.ticker}`} className="hover:text-blue-400 transition">
                      {t.ticker}
                    </Link>
                  </td>
                  <td className="p-4">{t.entry_price?.toFixed(2)} kr</td>
                  <td className="p-4">{t.exit_price?.toFixed(2) ?? "–"}</td>
                  <td className="p-4 text-gray-400">{t.quantity}</td>
                  <td className="p-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      t.close_reason === "stop_loss"
                        ? "bg-red-500/20 text-red-400"
                        : t.close_reason === "take_profit"
                        ? "bg-green-500/20 text-green-400"
                        : "bg-gray-700 text-gray-400"
                    }`}>
                      {closeReasonLabel[t.close_reason] ?? t.close_reason ?? "–"}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <p className={`font-semibold ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pnl >= 0 ? "+" : ""}{pnl.toFixed(0)} kr
                    </p>
                    <p className={`text-xs ${pnlPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
                    </p>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Trades — mobile card list */}
      <div className="md:hidden space-y-3">
        {trades.length === 0 && (
          <p className="text-center text-gray-500 text-sm py-6">Inga avslutade affärer än.</p>
        )}
        {trades.map((t: any) => {
          const pnl = t.pnl_kr ?? 0;
          const pnlPct = t.pnl_pct ?? 0;
          return (
            <div key={t.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
              {/* Row 1: ticker + P&L */}
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/dashboard/stocks/${t.ticker}`}
                  className="font-bold text-white hover:text-blue-400 transition text-base"
                >
                  {t.ticker}
                </Link>
                <div className="text-right">
                  <p className={`font-semibold ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {pnl >= 0 ? "+" : ""}{pnl.toFixed(0)} kr
                  </p>
                  <p className={`text-xs ${pnlPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* Row 2: prices + quantity */}
              <div className="flex items-center gap-4 text-sm text-gray-300">
                <span>In: <span className="text-white font-medium">{t.entry_price?.toFixed(2)} kr</span></span>
                <span className="text-gray-600">→</span>
                <span>Ut: <span className="text-white font-medium">{t.exit_price?.toFixed(2) ?? "–"}</span></span>
                <span className="text-gray-500 text-xs ml-auto">{t.quantity} st</span>
              </div>

              {/* Row 3: dates + close reason */}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="text-xs text-gray-500 space-y-0.5">
                  <p>Öppnad: {new Date(t.opened_at).toLocaleString("sv-SE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}</p>
                  {t.closed_at && (
                    <p>Stängd: {new Date(t.closed_at).toLocaleString("sv-SE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}</p>
                  )}
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  t.close_reason === "stop_loss"
                    ? "bg-red-500/20 text-red-400"
                    : t.close_reason === "take_profit"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-gray-700 text-gray-400"
                }`}>
                  {closeReasonLabel[t.close_reason] ?? t.close_reason ?? "–"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
