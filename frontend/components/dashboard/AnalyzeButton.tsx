"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

export default function AnalyzeButton({ ticker }: { ticker: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const run = async () => {
    setLoading(true);
    setError("");
    setDone(false);
    try {
      const res = await fetch(`${API}/api/run/${encodeURIComponent(ticker)}`, {
        method: "POST",
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDone(true);
      setTimeout(() => window.location.reload(), 1500);
    } catch (e: any) {
      setError(e.message ?? "Nätverksfel");
    }
    setLoading(false);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={run}
        disabled={loading}
        className="text-xs border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-white rounded-lg px-3 py-1.5 transition disabled:opacity-50"
      >
        {loading ? "Analyserar..." : done ? "✓ Klar" : "Analysera nu"}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
