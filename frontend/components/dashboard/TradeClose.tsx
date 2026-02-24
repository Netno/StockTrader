"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

export default function TradeClose({ tradeId }: { tradeId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [showInput, setShowInput] = useState(false);
  const [priceValue, setPriceValue] = useState("");

  if (result) return <span className="text-xs text-gray-400">{result}</span>;

  const close = async () => {
    setLoading(true);
    try {
      const body: Record<string, number> = {};
      const p = parseFloat(priceValue);
      if (priceValue && !isNaN(p) && p > 0) body.price = p;

      const res = await fetch(`${API}/api/trades/${tradeId}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.error) {
        setResult(`Fel: ${data.error}`);
      } else {
        setResult(
          `Stängd ${data.exit_price?.toFixed(2)} kr (${data.pnl_pct >= 0 ? "+" : ""}${data.pnl_pct?.toFixed(1)}%)`,
        );
        router.refresh();
      }
    } catch {
      setResult("Nätverksfel");
    }
    setLoading(false);
  };

  if (!showInput) {
    return (
      <button
        disabled={loading}
        onClick={() => setShowInput(true)}
        className="px-2 py-1 text-xs rounded-lg bg-gray-700 hover:bg-red-900/50 hover:text-red-300 text-gray-400 disabled:opacity-50 transition"
      >
        Stäng
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <input
        type="number"
        step="0.01"
        value={priceValue}
        onChange={(e) => setPriceValue(e.target.value)}
        placeholder="Säljkurs (valfritt)"
        className="w-32 px-2 py-1 text-xs rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-blue-500 focus:outline-none"
      />
      <button
        disabled={loading}
        onClick={close}
        className="px-2 py-1 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white disabled:opacity-50 transition font-medium"
      >
        {loading ? "..." : "Stäng"}
      </button>
      <button
        disabled={loading}
        onClick={() => setShowInput(false)}
        className="px-2 py-1 text-xs rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50 transition"
      >
        Avbryt
      </button>
    </div>
  );
}
