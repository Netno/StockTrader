"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

export default function TradeClose({ tradeId }: { tradeId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  if (result) return <span className="text-xs text-gray-400">{result}</span>;

  const close = async () => {
    if (!confirm("Stäng positionen till aktuellt marknadspris?")) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/trades/${tradeId}/close`, { method: "POST" });
      const data = await res.json();
      if (data.error) {
        setResult(`Fel: ${data.error}`);
      } else {
        setResult(`Stängd ${data.exit_price?.toFixed(2)} kr (${data.pnl_pct >= 0 ? "+" : ""}${data.pnl_pct?.toFixed(1)}%)`);
        router.refresh();
      }
    } catch {
      setResult("Nätverksfel");
    }
    setLoading(false);
  };

  return (
    <button
      disabled={loading}
      onClick={close}
      className="px-2 py-1 text-xs rounded-lg bg-gray-700 hover:bg-red-900/50 hover:text-red-300 text-gray-400 disabled:opacity-50 transition"
    >
      {loading ? "..." : "Stäng"}
    </button>
  );
}
