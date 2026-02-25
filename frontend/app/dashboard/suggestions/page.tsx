import { api } from "@/lib/api";

export const revalidate = 60;

const statusColor: Record<string, string> = {
  pending: "text-amber-400 bg-amber-400/10",
  accepted: "text-green-400 bg-green-400/10",
  rejected: "text-gray-500 bg-gray-700",
};

const statusLabel: Record<string, string> = {
  pending: "Väntar",
  accepted: "Godkänd",
  rejected: "Avvisad",
};

export default async function SuggestionsPage() {
  let suggestions: any[] = [];
  try {
    suggestions = await api.suggestions();
  } catch {}

  const pending = suggestions.filter((s) => s.status === "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Watchlist-förslag</h1>
        {pending.length > 0 && (
          <span className="bg-amber-500/20 text-amber-400 text-xs font-semibold px-2.5 py-1 rounded-full">
            {pending.length} väntar på beslut
          </span>
        )}
      </div>

      <p className="text-sm text-gray-400">
        Varje söndag skannar agenten ~30 svenska aktier och föreslår byten om
        ett bättre alternativ hittas. Godkänner du ett förslag uppdaterar du
        watchlist manuellt i Supabase.
      </p>

      {suggestions.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500 text-sm">
          Inga förslag ännu. Nästa skanning sker söndag kl 18:00, eller trigga
          manuellt via <code className="text-gray-400">POST /api/scan</code>.
        </div>
      ) : (
        <div className="space-y-3">
          {suggestions.map((s) => (
            <div
              key={s.id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-red-400 font-semibold">
                    {s.replace_ticker}
                  </span>
                  <span className="text-gray-500 text-sm">
                    ({s.replace_score?.toFixed(0)}p)
                  </span>
                  <span className="text-gray-600">→</span>
                  <span className="text-green-400 font-semibold">
                    {s.suggested_ticker}
                  </span>
                  <span className="text-gray-500 text-sm">
                    ({s.suggested_score?.toFixed(0)}p)
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                      statusColor[s.status] ?? statusColor.pending
                    }`}
                  >
                    {statusLabel[s.status] ?? s.status}
                  </span>
                </div>
                <span className="text-xs text-gray-600 shrink-0">
                  {s.created_at
                    ? new Date(s.created_at).toLocaleDateString("sv-SE", {
                        timeZone: "Europe/Stockholm",
                      })
                    : "–"}
                </span>
              </div>

              <p className="text-sm text-gray-400 mt-2">
                <span className="text-gray-300 font-medium">
                  {s.suggested_name}
                </span>{" "}
                ersätter{" "}
                <span className="text-gray-300 font-medium">
                  {s.replace_name}
                </span>
              </p>

              {s.suggested_reasons?.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {s.suggested_reasons.map((r: string, i: number) => (
                    <li key={i} className="text-xs text-gray-500">
                      • {r}
                    </li>
                  ))}
                </ul>
              )}

              {s.status === "pending" && (
                <div className="flex gap-2 mt-4">
                  <form
                    action={`/api/agent/suggestions/${s.id}/accept`}
                    method="POST"
                  >
                    <button className="px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-xs font-semibold transition">
                      Godkänn
                    </button>
                  </form>
                  <form
                    action={`/api/agent/suggestions/${s.id}/reject`}
                    method="POST"
                  >
                    <button className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-semibold transition">
                      Avvisa
                    </button>
                  </form>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
