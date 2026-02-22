interface StockEvent {
  id: string;
  ticker: string;
  event_type: string;
  description: string;
  event_date: string;
}

export default function EventsWidget({ events }: { events: StockEvent[] }) {
  if (!events?.length) {
    return <p className="text-gray-500 text-sm">Inga kommande händelser.</p>;
  }

  return (
    <div className="space-y-2">
      {events.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span className="text-amber-400 text-xs font-mono bg-amber-400/10 px-1.5 py-0.5 rounded">
              {e.ticker}
            </span>
            <span className="text-gray-300">{e.description ?? e.event_type}</span>
          </div>
          <span className="text-gray-500 text-xs">{e.event_date}</span>
        </div>
      ))}
    </div>
  );
}
