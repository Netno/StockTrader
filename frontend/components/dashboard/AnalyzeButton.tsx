"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

export default function AnalyzeButton({ ticker }: { ticker: string }) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const router = useRouter();

  const run = async () => {
    setLoading(true);
    setDone(false);
    try {
      await fetch(`${API}/api/test/${encodeURIComponent(ticker)}`, { cache: "no-store" });
      setDone(true);
      setTimeout(() => {
        setDone(false);
        router.refresh();
      }, 1500);
    } catch {}
    setLoading(false);
  };

  return (
    <button
      onClick={run}
      disabled={loading}
      className="text-xs border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-white rounded-lg px-3 py-1.5 transition disabled:opacity-50"
    >
      {loading ? "Analyserar..." : done ? "✓ Klar" : "Analysera nu"}
    </button>
  );
}
