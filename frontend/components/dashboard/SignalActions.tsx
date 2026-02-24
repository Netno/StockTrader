"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

const statusBadge: Record<string, string> = {
  confirmed: "bg-green-500/20 text-green-400",
  rejected: "bg-red-500/20 text-red-400",
  auto: "bg-gray-700 text-gray-400",
};

const statusLabel: Record<string, string> = {
  confirmed: "Bekräftad",
  rejected: "Nekad",
  auto: "Auto",
};

export default function SignalActions({
  signalId,
  status,
  signalPrice,
  signalQuantity,
}: {
  signalId: string;
  status: string;
  signalPrice?: number;
  signalQuantity?: number;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [showPriceInput, setShowPriceInput] = useState(false);
  const [priceValue, setPriceValue] = useState(signalPrice?.toFixed(2) ?? "");
  const [quantityValue, setQuantityValue] = useState(
    signalQuantity?.toString() ?? "",
  );

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
    return <span className="text-xs text-gray-400">{done}</span>;
  }

  const act = async (action: "confirm" | "reject") => {
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, number> = {};
      if (action === "confirm") {
        const p = parseFloat(priceValue);
        const q = parseInt(quantityValue, 10);
        if (priceValue && !isNaN(p) && p > 0) body.price = p;
        if (quantityValue && !isNaN(q) && q > 0) body.quantity = q;
      }
      const res = await fetch(`${API}/api/signals/${signalId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setDone(
          action === "confirm"
            ? `Köpt @ ${data.entry_price?.toFixed(2) ?? ""} kr`
            : "Nekad",
        );
        router.refresh();
      }
    } catch {
      setError("Nätverksfel");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-2">
      {error && <span className="text-xs text-red-400">{error}</span>}
      {showPriceInput && (
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1">
            <label className="text-xs text-gray-500">Kurs:</label>
            <input
              type="number"
              step="0.01"
              value={priceValue}
              onChange={(e) => setPriceValue(e.target.value)}
              className="w-24 px-2 py-1 text-xs rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-blue-500 focus:outline-none"
              placeholder="Köpkurs"
            />
          </div>
          <div className="flex items-center gap-1">
            <label className="text-xs text-gray-500">Antal:</label>
            <input
              type="number"
              step="1"
              value={quantityValue}
              onChange={(e) => setQuantityValue(e.target.value)}
              className="w-20 px-2 py-1 text-xs rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-blue-500 focus:outline-none"
              placeholder="Antal"
            />
          </div>
        </div>
      )}
      <div className="flex items-center gap-2">
        {!showPriceInput ? (
          <button
            disabled={loading}
            onClick={() => setShowPriceInput(true)}
            className="px-3 py-1 text-xs rounded-lg bg-green-600 hover:bg-green-500 text-white disabled:opacity-50 transition font-medium"
          >
            Bekräfta köp
          </button>
        ) : (
          <button
            disabled={loading}
            onClick={() => act("confirm")}
            className="px-3 py-1 text-xs rounded-lg bg-green-600 hover:bg-green-500 text-white disabled:opacity-50 transition font-medium"
          >
            {loading ? "..." : "Köp"}
          </button>
        )}
        <button
          disabled={loading}
          onClick={() => act("reject")}
          className="px-3 py-1 text-xs rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50 transition"
        >
          Neka
        </button>
      </div>
    </div>
  );
}
