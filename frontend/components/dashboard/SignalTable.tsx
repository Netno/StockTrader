interface Signal {
  id: string;
  ticker: string;
  signal_type: string;
  price: number;
  quantity: number;
  confidence: number;
  score: number;
  reasons: string[];
  created_at: string;
}

export default function SignalTable({ signals }: { signals: Signal[] }) {
  if (!signals?.length) {
    return <p className="text-gray-500 text-sm">Inga signaler ännu.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-800">
            <th className="pb-2 pr-4">Tid</th>
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4">Signal</th>
            <th className="pb-2 pr-4">Pris</th>
            <th className="pb-2 pr-4">Antal</th>
            <th className="pb-2 pr-4">Score</th>
            <th className="pb-2">Confidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {signals.map((s) => (
            <tr key={s.id} className="hover:bg-gray-800/40 transition">
              <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">
                {new Date(s.created_at).toLocaleString("sv-SE", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  timeZone: "Europe/Stockholm",
                })}
              </td>
              <td className="py-2 pr-4 font-semibold">{s.ticker}</td>
              <td className="py-2 pr-4">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                    s.signal_type === "BUY"
                      ? "bg-green-500/20 text-green-400"
                      : "bg-red-500/20 text-red-400"
                  }`}
                >
                  {s.signal_type === "BUY" ? "KÖP" : "SÄLJ"}
                </span>
              </td>
              <td className="py-2 pr-4">{s.price?.toFixed(2)} kr</td>
              <td className="py-2 pr-4">{s.quantity}</td>
              <td className="py-2 pr-4">{s.score}p</td>
              <td className="py-2">
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-gray-800 rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full"
                      style={{ width: `${s.confidence}%` }}
                    />
                  </div>
                  <span className="text-gray-400">{s.confidence?.toFixed(0)}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
