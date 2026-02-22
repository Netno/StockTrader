"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

const statusBadge: Record<string, string> = {
  confirmed: "bg-green-500/20 text-green-400",
  rejected:  "bg-red-500/20 text-red-400",
  auto:      "bg-gray-700 text-gray-400",
};

const statusLabel: Record<string, string> = {
  confirmed: "Bekräftad",
  rejected:  "Nekad",
  auto:      "Auto",
};

export default function SignalActions({
  signalId,
  status,
}: {
  signalId: string;
  status: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  if (status !== "pending") {
    const cls = statusBadge[status] ?? "bg-gray-700 text-gray-400";
    const lbl = statusLabel[status] ?? status;
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
        {lbl}
      </span>
    );
  }

  if (done) {
    return (
      <span className="text-xs text-gray-400">{done}</span>
    );
  }

  const act = async (action: "confirm" | "reject") => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/signals/${signalId}/${action}`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setDone(action === "confirm" ? "Köpt!" : "Nekad");
        router.refresh();
      }
    } catch {
      setError("Nätverksfel");
    }
    setLoading(false);
  };

  return (
    <div className="flex items-center gap-2">
      {error && <span className="text-xs text-red-400">{error}</span>}
      <button
        disabled={loading}
        onClick={() => act("confirm")}
        className="px-3 py-1 text-xs rounded-lg bg-green-600 hover:bg-green-500 text-white disabled:opacity-50 transition font-medium"
      >
        {loading ? "..." : "Bekräfta köp"}
      </button>
      <button
        disabled={loading}
        onClick={() => act("reject")}
        className="px-3 py-1 text-xs rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50 transition"
      >
        Neka
      </button>
    </div>
  );
}
