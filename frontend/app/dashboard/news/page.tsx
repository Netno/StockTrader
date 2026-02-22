import { api } from "@/lib/api";

export const revalidate = 60;

const sentimentColor: Record<string, string> = {
  POSITIVE: "text-green-400 bg-green-400/10",
  NEGATIVE: "text-red-400 bg-red-400/10",
  NEUTRAL: "text-gray-400 bg-gray-700",
};

const sentimentLabel: Record<string, string> = {
  POSITIVE: "Positiv",
  NEGATIVE: "Negativ",
  NEUTRAL: "Neutral",
};

export default async function NewsPage() {
  let news: any[] = [];
  try {
    news = await api.news(undefined, 100);
  } catch {}

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Nyheter</h1>

      <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
        {news.length === 0 && (
          <p className="p-6 text-gray-500 text-sm">Inga nyheter hämtade ännu.</p>
        )}
        {news.map((item) => (
          <div key={item.id} className="p-4 flex items-start gap-4 hover:bg-gray-800/30 transition">
            <span
              className={`mt-1 shrink-0 text-xs px-2 py-0.5 rounded-full font-semibold ${
                sentimentColor[item.sentiment] ?? sentimentColor.NEUTRAL
              }`}
            >
              {sentimentLabel[item.sentiment] ?? "–"}
            </span>
            <div className="flex-1 min-w-0">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm hover:text-blue-400 transition line-clamp-2"
              >
                {item.headline}
              </a>
              <p className="text-xs text-gray-500 mt-1">
                {item.ticker} · {item.source} ·{" "}
                {item.published_at
                  ? new Date(item.published_at).toLocaleString("sv-SE", {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "–"}
              </p>
              {item.gemini_reason && (
                <p className="text-xs text-gray-600 mt-1 italic">{item.gemini_reason}</p>
              )}
            </div>
            <span className="shrink-0 text-xs font-mono text-gray-600">
              {item.sentiment_score?.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
