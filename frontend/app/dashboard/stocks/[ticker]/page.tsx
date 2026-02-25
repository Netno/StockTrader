import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import RsiChart from "@/components/dashboard/RsiChart";
import BollingerChart from "@/components/dashboard/BollingerChart";
import AnalyzeButton from "@/components/dashboard/AnalyzeButton";
import { AVANZA_URLS } from "@/lib/avanza";
import Link from "next/link";

export const revalidate = 30;

const TABS = ["indikatorer", "signaler", "nyheter", "notiser"] as const;
type Tab = (typeof TABS)[number];

const sentimentColor: Record<string, string> = {
  POSITIVE: "text-green-400",
  NEGATIVE: "text-red-400",
  NEUTRAL:  "text-gray-500",
};

const notifIcon: Record<string, string> = {
  buy_signal:     "↑",
  sell_signal:    "↓",
  report_warning: "!",
  info:           "i",
};

const notifColor: Record<string, string> = {
  buy_signal:     "bg-green-500/15 text-green-400 border-green-500/30",
  sell_signal:    "bg-red-500/15 text-red-400 border-red-500/30",
  report_warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  info:           "bg-gray-700 text-gray-400 border-gray-600",
};

export default async function StockDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { ticker: rawTicker } = await params;
  const { tab: rawTab } = await searchParams;
  const ticker = decodeURIComponent(rawTicker).toUpperCase();
  const activeTab: Tab = (TABS.includes(rawTab as Tab) ? rawTab : "indikatorer") as Tab;

  // Always fetch live indicators
  const live = await api.testTicker(ticker).catch(() => null);
  const ind = live?.indicators ?? {};
  const price = live?.price;

  // Fetch tab-specific data
  const [signals, news, notifications] = await Promise.all([
    activeTab === "signaler"
      ? supabase.from("stock_signals").select("*").eq("ticker", ticker).order("created_at", { ascending: false }).limit(50).then(r => r.data ?? [])
      : Promise.resolve([]),
    activeTab === "nyheter"
      ? supabase.from("stock_news").select("*").eq("ticker", ticker).order("created_at", { ascending: false }).limit(50).then(r => r.data ?? [])
      : Promise.resolve([]),
    activeTab === "notiser"
      ? supabase.from("stock_notifications").select("*").eq("ticker", ticker).order("created_at", { ascending: false }).limit(50).then(r => r.data ?? [])
      : Promise.resolve([]),
  ]);

  const rsiData = ind.rsi ? [{ date: "Nu", rsi: ind.rsi }] : [];
  const bbData = ind.bollinger_upper ? [{
    date: "Nu",
    price: ind.current_price,
    upper: ind.bollinger_upper,
    lower: ind.bollinger_lower,
    mid:   ind.bollinger_mid,
  }] : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Link href="/dashboard/stocks" className="text-gray-500 hover:text-white text-sm transition">
              ← Aktier
            </Link>
            <span className="text-gray-700">/</span>
            <h1 className="text-xl font-bold">{ticker}</h1>
            {AVANZA_URLS[ticker] && (
              <a
                href={AVANZA_URLS[ticker]}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full hover:bg-blue-500/20 transition"
              >
                Avanza ↗
              </a>
            )}
            <AnalyzeButton ticker={ticker} />
          </div>
          {price && (
            <p className="text-3xl font-bold mt-1">{price.toFixed(2)} kr</p>
          )}
        </div>
        {live?.buy_score !== undefined && (
          <div className={`px-4 py-2 rounded-xl border text-sm font-semibold ${
            live.buy_score >= 60
              ? "bg-green-500/15 text-green-400 border-green-500/30"
              : "bg-gray-800 text-gray-400 border-gray-700"
          }`}>
            Köpsignal: {live.buy_score}p {live.buy_score >= 60 ? "— AKTIV" : "/ 60p"}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {TABS.map((tab) => (
          <Link
            key={tab}
            href={`/dashboard/stocks/${ticker}?tab=${tab}`}
            className={`px-4 py-2 text-sm font-medium capitalize transition border-b-2 -mb-px ${
              activeTab === tab
                ? "border-blue-500 text-white"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </Link>
        ))}
      </div>

      {/* Tab: Indikatorer */}
      {activeTab === "indikatorer" && (
        <div className="space-y-6">
          {live?.error ? (
            <p className="text-red-400 text-sm">{live.error}</p>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: "RSI (14)",       value: ind.rsi?.toFixed(1),          color: ind.rsi < 35 ? "text-green-400" : ind.rsi > 70 ? "text-red-400" : "text-white" },
                  { label: "MACD",           value: ind.macd?.toFixed(3),         color: ind.macd >= 0 ? "text-green-400" : "text-red-400" },
                  { label: "MA50",           value: ind.ma50?.toFixed(2),         color: price > ind.ma50 ? "text-green-400" : "text-red-400" },
                  { label: "MA200",          value: ind.ma200?.toFixed(2),        color: price > ind.ma200 ? "text-green-400" : "text-red-400" },
                  { label: "EMA20",          value: ind.ema20?.toFixed(2),        color: "text-white" },
                  { label: "Bollinger over", value: ind.bollinger_upper?.toFixed(2), color: "text-white" },
                  { label: "Bollinger under",value: ind.bollinger_lower?.toFixed(2), color: "text-white" },
                  { label: "ATR",            value: ind.atr?.toFixed(2),          color: "text-white" },
                  { label: "Volym x",        value: ind.volume_ratio ? `${ind.volume_ratio}x` : null, color: ind.volume_ratio >= 1.5 ? "text-green-400" : "text-white" },
                  { label: "Stop-loss",      value: live?.stop_loss?.toFixed(2),  color: "text-red-400" },
                  { label: "Take-profit",    value: live?.take_profit?.toFixed(2),color: "text-green-400" },
                  { label: "Datapunkter",    value: live?.data_points,            color: "text-gray-400" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <p className="text-xs text-gray-500 mb-1">{label}</p>
                    <p className={`text-lg font-semibold ${color}`}>{value ?? "–"}</p>
                  </div>
                ))}
              </div>

              {live?.buy_reasons?.length > 0 && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-3">Aktiva köpsignals-kriterier</p>
                  <div className="flex flex-wrap gap-2">
                    {live.buy_reasons.map((r: string, i: number) => (
                      <span key={i} className="text-xs bg-blue-500/10 text-blue-400 px-2.5 py-1 rounded-full border border-blue-500/20">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <RsiChart data={rsiData} ticker={ticker} />
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <BollingerChart data={bbData} ticker={ticker} />
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab: Signaler */}
      {activeTab === "signaler" && (
        <>
          {signals.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl">
              <p className="p-6 text-gray-500 text-sm">Inga signaler för {ticker} än.</p>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-800">
                      <th className="p-4">Tid</th>
                      <th className="p-4">Signal</th>
                      <th className="p-4">Pris</th>
                      <th className="p-4">Antal</th>
                      <th className="p-4">Score</th>
                      <th className="p-4">Confidence</th>
                      <th className="p-4">SL / TP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {signals.map((s: any) => (
                      <tr key={s.id} className="hover:bg-gray-800/30">
                        <td className="p-4 text-gray-400 whitespace-nowrap">
                          {new Date(s.created_at).toLocaleString("sv-SE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}
                        </td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${s.signal_type === "BUY" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                            {s.signal_type === "BUY" ? "KÖP" : "SÄLJ"}
                          </span>
                        </td>
                        <td className="p-4">{s.price?.toFixed(2)} kr</td>
                        <td className="p-4">{s.quantity}</td>
                        <td className="p-4">{s.score}p</td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-gray-800 rounded-full h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${s.confidence}%` }} />
                            </div>
                            <span className="text-gray-400">{s.confidence?.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="p-4 text-xs">
                          <span className="text-red-400">{s.stop_loss_price?.toFixed(2)}</span>
                          <span className="text-gray-600 mx-1">/</span>
                          <span className="text-green-400">{s.take_profit_price?.toFixed(2)}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile card list */}
              <div className="md:hidden space-y-3">
                {signals.map((s: any) => (
                  <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
                    {/* Row 1: badge + time */}
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${s.signal_type === "BUY" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                        {s.signal_type === "BUY" ? "KÖP" : "SÄLJ"}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(s.created_at).toLocaleString("sv-SE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}
                      </span>
                    </div>

                    {/* Row 2: price + quantity */}
                    <div className="flex items-baseline gap-3">
                      <span className="text-lg font-bold">{s.price?.toFixed(2)} kr</span>
                      <span className="text-xs text-gray-400">{s.quantity} st</span>
                    </div>

                    {/* Row 3: score + confidence bar + SL/TP */}
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{s.score}p</span>
                        <div className="w-16 bg-gray-800 rounded-full h-1.5">
                          <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${s.confidence}%` }} />
                        </div>
                        <span className="text-xs text-gray-400">{s.confidence?.toFixed(0)}%</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-red-400">SL {s.stop_loss_price?.toFixed(2) ?? "–"}</span>
                        <span className="text-gray-600 mx-1">/</span>
                        <span className="text-green-400">TP {s.take_profit_price?.toFixed(2) ?? "–"}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {/* Tab: Nyheter */}
      {activeTab === "nyheter" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
          {news.length === 0 ? (
            <p className="p-6 text-gray-500 text-sm">Inga nyheter inhämtade för {ticker} än.</p>
          ) : (
            (news as any[]).map((item) => (
              <div key={item.id} className="p-4 flex items-start gap-3 hover:bg-gray-800/30 transition">
                <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                  item.sentiment === "POSITIVE" ? "bg-green-400" :
                  item.sentiment === "NEGATIVE" ? "bg-red-400" : "bg-gray-600"
                }`} />
                <div className="flex-1 min-w-0">
                  <a href={item.url} target="_blank" rel="noopener noreferrer"
                    className={`text-sm hover:text-blue-400 transition ${sentimentColor[item.sentiment] ?? "text-gray-300"}`}>
                    {item.headline}
                  </a>
                  {item.gemini_reason && (
                    <p className="text-xs text-gray-600 mt-0.5 italic">{item.gemini_reason}</p>
                  )}
                  <p className="text-xs text-gray-600 mt-0.5">
                    {item.source} · {item.published_at ? new Date(item.published_at).toLocaleString("sv-SE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" }) : "–"}
                  </p>
                </div>
                <span className="text-xs font-mono text-gray-600 shrink-0">
                  {item.sentiment_score?.toFixed(2)}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Notiser */}
      {activeTab === "notiser" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
          {notifications.length === 0 ? (
            <p className="p-6 text-gray-500 text-sm">Inga notiser skickade för {ticker} än.</p>
          ) : (
            (notifications as any[]).map((n) => (
              <div key={n.id} className="p-4 flex gap-3 hover:bg-gray-800/30 transition">
                <div className={`mt-0.5 w-7 h-7 rounded-full border flex items-center justify-center text-xs font-bold shrink-0 ${notifColor[n.type] ?? notifColor.info}`}>
                  {notifIcon[n.type] ?? "i"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold">{n.title}</p>
                  <pre className="text-xs text-gray-400 mt-1 whitespace-pre-wrap font-sans leading-relaxed">{n.message}</pre>
                </div>
                <div className="text-xs text-gray-600 shrink-0 text-right pt-0.5">
                  <div>{new Date(n.created_at).toLocaleDateString("sv-SE", { day: "numeric", month: "short", timeZone: "Europe/Stockholm" })}</div>
                  <div>{new Date(n.created_at).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}</div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
