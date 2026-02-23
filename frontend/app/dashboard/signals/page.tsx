import { api } from "@/lib/api";
import SignalActions from "@/components/dashboard/SignalActions";
import Link from "next/link";

export const revalidate = 15;

export default async function SignalsPage() {
  let signals: any[] = [];
  try {
    signals = await api.signals(100);
  } catch {}

  const pending = signals.filter((s) => s.signal_type === "BUY" && s.status === "pending");
  const buys    = signals.filter((s) => s.signal_type === "BUY");
  const sells   = signals.filter((s) => s.signal_type === "SELL");

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Signaler</h1>

      {/* Stats — 1 col on mobile, 3 cols on sm+ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 mb-1">Totalt</p>
          <p className="text-2xl font-bold">{signals.length}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 mb-1">Köpsignaler</p>
          <p className="text-2xl font-bold text-green-400">{buys.length}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 mb-1">Säljsignaler</p>
          <p className="text-2xl font-bold text-red-400">{sells.length}</p>
        </div>
      </div>

      {/* Pending signals — require action */}
      {pending.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-amber-400">
            {pending.length} signal{pending.length > 1 ? "er" : ""} väntar på bekräftelse
          </p>
          {pending.map((s: any) => (
            <div
              key={s.id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Link
                      href={`/dashboard/stocks/${s.ticker}`}
                      className="font-bold text-white hover:text-blue-400 transition"
                    >
                      {s.ticker}
                    </Link>
                    <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full font-semibold">
                      KÖP
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(s.created_at).toLocaleString("sv-SE", {
                        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-2xl font-bold">{s.price?.toFixed(2)} kr</p>
                  <p className="text-sm text-gray-400">
                    {s.quantity} aktier &middot; ~{(s.price * s.quantity)?.toFixed(0)} kr
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="text-gray-500 text-xs">Stop-loss</p>
                  <p className="text-red-400 font-semibold">{s.stop_loss_price?.toFixed(2)} kr</p>
                  <p className="text-gray-500 text-xs mt-1">Take-profit</p>
                  <p className="text-green-400 font-semibold">{s.take_profit_price?.toFixed(2)} kr</p>
                </div>
              </div>

              {/* Description */}
              {s.indicators?.signal_description && (
                <p className="text-sm text-gray-300 leading-relaxed">
                  {s.indicators.signal_description}
                </p>
              )}

              {/* Score + reasons */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-1.5">
                  <div className="w-20 bg-gray-800 rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full"
                      style={{ width: `${s.confidence}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400">{s.score}p</span>
                </div>
                {(s.reasons ?? []).slice(0, 4).map((r: string, i: number) => (
                  <span
                    key={i}
                    className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20"
                  >
                    {r}
                  </span>
                ))}
              </div>

              <SignalActions signalId={s.id} status={s.status} />
            </div>
          ))}
        </div>
      )}

      {/* All signals — desktop table */}
      <div className="hidden md:block bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="p-4">Tid</th>
              <th className="p-4">Ticker</th>
              <th className="p-4">Signal</th>
              <th className="p-4">Pris</th>
              <th className="p-4">Antal</th>
              <th className="p-4">Score</th>
              <th className="p-4">SL / TP</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {signals.length === 0 && (
              <tr>
                <td colSpan={8} className="p-6 text-center text-gray-500">
                  Inga signaler än.
                </td>
              </tr>
            )}
            {signals.map((s: any) => (
              <tr key={s.id} className="hover:bg-gray-800/30 transition">
                <td className="p-4 text-gray-400 whitespace-nowrap">
                  {new Date(s.created_at).toLocaleString("sv-SE", {
                    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                  })}
                </td>
                <td className="p-4 font-semibold">
                  <Link href={`/dashboard/stocks/${s.ticker}`} className="hover:text-blue-400 transition">
                    {s.ticker}
                  </Link>
                </td>
                <td className="p-4">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                    s.signal_type === "BUY"
                      ? "bg-green-500/20 text-green-400"
                      : "bg-red-500/20 text-red-400"
                  }`}>
                    {s.signal_type === "BUY" ? "KÖP" : "SÄLJ"}
                  </span>
                </td>
                <td className="p-4">{s.price?.toFixed(2)} kr</td>
                <td className="p-4">{s.quantity}</td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="w-12 bg-gray-800 rounded-full h-1.5">
                      <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${s.confidence}%` }} />
                    </div>
                    <span className="text-gray-400">{s.score}p</span>
                  </div>
                </td>
                <td className="p-4 text-xs">
                  <span className="text-red-400">{s.stop_loss_price?.toFixed(2) ?? "–"}</span>
                  <span className="text-gray-600 mx-1">/</span>
                  <span className="text-green-400">{s.take_profit_price?.toFixed(2) ?? "–"}</span>
                </td>
                <td className="p-4">
                  {s.signal_type === "BUY" ? (
                    <SignalActions signalId={s.id} status={s.status ?? "pending"} />
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400">
                      Sälj på Avanza
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* All signals — mobile card list */}
      <div className="md:hidden space-y-3">
        {signals.length === 0 && (
          <p className="text-center text-gray-500 text-sm py-6">Inga signaler än.</p>
        )}
        {signals.map((s: any) => (
          <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            {/* Row 1: ticker + badge + time */}
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <Link
                  href={`/dashboard/stocks/${s.ticker}`}
                  className="font-bold text-white hover:text-blue-400 transition"
                >
                  {s.ticker}
                </Link>
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                  s.signal_type === "BUY"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-red-500/20 text-red-400"
                }`}>
                  {s.signal_type === "BUY" ? "KÖP" : "SÄLJ"}
                </span>
              </div>
              <span className="text-xs text-gray-500">
                {new Date(s.created_at).toLocaleString("sv-SE", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>

            {/* Row 2: price + quantity */}
            <div className="flex items-baseline gap-3">
              <span className="text-lg font-bold">{s.price?.toFixed(2)} kr</span>
              <span className="text-xs text-gray-400">{s.quantity} st</span>
            </div>

            {/* Row 3: score bar + SL/TP */}
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-1.5">
                <div className="w-16 bg-gray-800 rounded-full h-1.5">
                  <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${s.confidence}%` }} />
                </div>
                <span className="text-xs text-gray-400">{s.score}p</span>
              </div>
              <div className="text-xs">
                <span className="text-red-400">SL {s.stop_loss_price?.toFixed(2) ?? "–"}</span>
                <span className="text-gray-600 mx-1">/</span>
                <span className="text-green-400">TP {s.take_profit_price?.toFixed(2) ?? "–"}</span>
              </div>
            </div>

            {/* Row 4: action */}
            {s.signal_type === "BUY" ? (
              <SignalActions signalId={s.id} status={s.status ?? "pending"} />
            ) : (
              <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400">
                Sälj på Avanza
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
