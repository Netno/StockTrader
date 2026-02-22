"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const AGENT_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

async function apiPost(path: string, body?: unknown) {
  const res = await fetch(`${AGENT_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  return res.json();
}

export default function DepositButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [showForm, setShowForm] = useState(false);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function handleDeposit() {
    const kr = parseFloat(amount);
    if (!kr || kr <= 0) { setError("Ange ett giltigt belopp"); return; }
    setError("");
    const res = await apiPost("/api/deposits", { amount: kr, note });
    if (res.ok) {
      setShowForm(false);
      setAmount("");
      setNote("");
      startTransition(() => router.refresh());
    } else {
      setError(res.error ?? "Något gick fel");
    }
  }

  async function handleReset() {
    if (!confirm("Nollställ ALLT? Alla affärer, signaler och insättningar raderas.")) return;
    await apiPost("/api/reset");
    startTransition(() => router.refresh());
  }

  if (showForm) {
    return (
      <div className="flex flex-col gap-2">
        <input
          type="number"
          placeholder="Belopp (kr)"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm w-full focus:outline-none focus:border-green-500"
        />
        <input
          type="text"
          placeholder="Notering (valfritt)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm w-full focus:outline-none focus:border-gray-500"
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={handleDeposit}
            disabled={pending}
            className="flex-1 bg-green-600 hover:bg-green-500 text-white text-xs font-semibold rounded-lg px-3 py-1.5 transition"
          >
            Sätt in
          </button>
          <button
            onClick={() => { setShowForm(false); setError(""); }}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-lg px-3 py-1.5 transition"
          >
            Avbryt
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2">
      <button
        onClick={() => setShowForm(true)}
        className="flex-1 bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-600/30 text-xs font-semibold rounded-lg px-3 py-1.5 transition"
      >
        + Sätt in kapital
      </button>
      <button
        onClick={handleReset}
        className="bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-red-400 border border-gray-700 text-xs rounded-lg px-3 py-1.5 transition"
        title="Nollställ allt"
      >
        Nollställ
      </button>
    </div>
  );
}
