import { supabase } from "@/lib/supabase";

export const revalidate = 30;

type NotificationType =
  | "buy_signal"
  | "sell_signal"
  | "report_warning"
  | "morning_summary"
  | "evening_summary"
  | "scan_suggestion"
  | "info";

interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  ticker: string | null;
  created_at: string;
}

const typeConfig: Record<NotificationType, { label: string; color: string; icon: string }> = {
  buy_signal:       { label: "Kopsignal",       color: "bg-green-500/15 text-green-400 border-green-500/30",  icon: "↑" },
  sell_signal:      { label: "Saljsignal",       color: "bg-red-500/15 text-red-400 border-red-500/30",        icon: "↓" },
  report_warning:   { label: "Rapportvarning",   color: "bg-amber-500/15 text-amber-400 border-amber-500/30",  icon: "!" },
  morning_summary:  { label: "Morgonsummering",  color: "bg-blue-500/15 text-blue-400 border-blue-500/30",     icon: "☀" },
  evening_summary:  { label: "Kvallssummering",  color: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30", icon: "☾" },
  scan_suggestion:  { label: "Watchlist-forslag", color: "bg-purple-500/15 text-purple-400 border-purple-500/30", icon: "↕" },
  info:             { label: "Info",             color: "bg-gray-700 text-gray-400 border-gray-600",           icon: "i" },
};

export default async function NotificationsPage() {
  const { data: notifications } = await supabase
    .from("stock_notifications")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);

  const items = (notifications ?? []) as Notification[];

  const countByType = items.reduce<Record<string, number>>((acc, n) => {
    acc[n.type] = (acc[n.type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Notislogg</h1>
        <span className="text-sm text-gray-500">{items.length} totalt</span>
      </div>

      {/* Summary chips */}
      {items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(countByType).map(([type, count]) => {
            const cfg = typeConfig[type as NotificationType] ?? typeConfig.info;
            return (
              <span
                key={type}
                className={`text-xs px-2.5 py-1 rounded-full border font-medium ${cfg.color}`}
              >
                {cfg.icon} {cfg.label} ({count})
              </span>
            );
          })}
        </div>
      )}

      {/* Log table */}
      {items.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500 text-sm">
          Inga notiser loggade anu. De dyker upp har nar agenten skickar kop/salj-signaler,
          summerings- eller rapportvarningar.
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
          {items.map((n) => {
            const cfg = typeConfig[n.type] ?? typeConfig.info;
            return (
              <div key={n.id} className="p-4 flex gap-4 hover:bg-gray-800/30 transition">
                {/* Icon */}
                <div className={`mt-0.5 w-7 h-7 rounded-full border flex items-center justify-center text-xs font-bold shrink-0 ${cfg.color}`}>
                  {cfg.icon}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm">{n.title}</span>
                    {n.ticker && (
                      <span className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                        {n.ticker}
                      </span>
                    )}
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${cfg.color}`}>
                      {cfg.label}
                    </span>
                  </div>
                  <pre className="text-xs text-gray-400 mt-1.5 whitespace-pre-wrap font-sans leading-relaxed">
                    {n.message}
                  </pre>
                </div>

                {/* Timestamp */}
                <div className="text-xs text-gray-600 shrink-0 text-right pt-0.5">
                  <div>{new Date(n.created_at).toLocaleDateString("sv-SE", { day: "numeric", month: "short", timeZone: "Europe/Stockholm" })}</div>
                  <div>{new Date(n.created_at).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" })}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
