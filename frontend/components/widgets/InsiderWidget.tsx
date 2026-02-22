interface InsiderEvent {
  id: string;
  ticker: string;
  event_type: string;
  description: string;
  amount: number;
  event_date: string;
}

export default function InsiderWidget({ events }: { events: InsiderEvent[] }) {
  if (!events?.length) {
    return <p className="text-gray-500 text-sm">Inga insiderhändelser.</p>;
  }

  return (
    <div className="space-y-2">
      {events.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-sm">
          <div>
            <span className="font-semibold">{e.ticker}</span>
            <span className="text-gray-400 ml-2">{e.description}</span>
          </div>
          <div className="text-right">
            {e.amount && (
              <span className="text-green-400 font-mono text-xs">
                {(e.amount / 1_000).toFixed(0)}k kr
              </span>
            )}
            <p className="text-gray-600 text-xs">{e.event_date}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
