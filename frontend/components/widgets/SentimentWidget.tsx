interface NewsItem {
  id: string;
  ticker: string;
  headline: string;
  sentiment: string;
  sentiment_score: number;
  gemini_reason: string;
  published_at: string;
}

export default function SentimentWidget({ news }: { news: NewsItem[] }) {
  if (!news?.length) return <p className="text-gray-500 text-sm">Inga nyheter.</p>;

  return (
    <div className="space-y-3">
      {news.slice(0, 5).map((item) => (
        <div key={item.id} className="flex items-start gap-3">
          <span
            className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
              item.sentiment === "POSITIVE"
                ? "bg-green-400"
                : item.sentiment === "NEGATIVE"
                ? "bg-red-400"
                : "bg-gray-500"
            }`}
          />
          <div>
            <p className="text-sm leading-snug">{item.headline}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {item.ticker} · {item.gemini_reason}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
