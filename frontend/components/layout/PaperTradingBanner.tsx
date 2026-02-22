"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";
const REFRESH_MS = 30_000;

interface Summary {
  total_deposited: number;
  available_cash: number;
  invested: number;
  market_value: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_value: number;
  total_pct: number;
}

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function pnlColor(n: number) {
  return n > 0 ? "text-green-400" : n < 0 ? "text-red-400" : "text-gray-400";
}

function sign(n: number) {
  return n >= 0 ? "+" : "";
}

export default function PaperTradingBanner() {
  const [s, setS] = useState<Summary | null>(null);
  const [showDeposit, setShowDeposit] = useState(false);
  const [depositAmount, setDepositAmount] = useState("");
  const [depositNote, setDepositNote] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/summary`, { cache: "no-store" });
      if (res.ok) setS(await res.json());
    } catch {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const addDeposit = async () => {
    const amount = parseFloat(depositAmount);
    if (!amount || amount <= 0) return;
    setSaving(true);
    try {
      await fetch(`${API}/api/deposits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, note: depositNote || "Insattning" }),
      });
      setShowDeposit(false);
      setDepositAmount("");
      setDepositNote("");
      await load();
    } catch {}
    setSaving(false);
  };

  const totalDelta = s ? s.total_value - s.total_deposited : 0;

  return (
    <>
      <div className="bg-gray-950 border-b border-gray-800 px-5 py-2 flex items-center gap-6 flex-wrap text-sm">

        {/* Portfolio value */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span className="text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded px-1.5 py-0.5 font-medium shrink-0">
            PAPER
          </span>

          {s ? (
            <>
              {/* Total value — the big number */}
              <div className="flex items-baseline gap-2">
                <span className="text-white font-bold text-base">{fmt(s.total_value)} kr</span>
                <span className={`text-xs font-semibold ${pnlColor(totalDelta)}`}>
                  {sign(totalDelta)}{fmt(totalDelta)} kr ({sign(s.total_pct)}{s.total_pct.toFixed(1)}%)
                </span>
              </div>

              <span className="text-gray-700 hidden sm:block">|</span>

              {/* Available cash — the action number */}
              <div className="hidden sm:flex items-center gap-1.5">
                <span className="text-xs text-gray-500">Disponibelt:</span>
                <span className={`font-semibold text-sm ${s.available_cash > 0 ? "text-blue-400" : "text-gray-500"}`}>
                  {fmt(s.available_cash)} kr
                </span>
              </div>

              {/* Breakdown */}
              <div className="hidden lg:flex items-center gap-4 text-xs text-gray-500">
                {s.invested > 0 && (
                  <span>Investerat: <span className="text-gray-300">{fmt(s.invested)} kr</span></span>
                )}
                {s.unrealized_pnl !== 0 && (
                  <span>
                    Orealiserat:{" "}
                    <span className={pnlColor(s.unrealized_pnl)}>
                      {sign(s.unrealized_pnl)}{fmt(s.unrealized_pnl)} kr
                    </span>
                  </span>
                )}
                {s.realized_pnl !== 0 && (
                  <span>
                    Realiserat:{" "}
                    <span className={pnlColor(s.realized_pnl)}>
                      {sign(s.realized_pnl)}{fmt(s.realized_pnl)} kr
                    </span>
                  </span>
                )}
                <span>Insatt: <span className="text-gray-400">{fmt(s.total_deposited)} kr</span></span>
              </div>
            </>
          ) : (
            <span className="text-gray-600 text-xs">Laddar portfolio...</span>
          )}
        </div>

        {/* Deposit button */}
        <button
          onClick={() => setShowDeposit(true)}
          className="text-xs text-gray-500 hover:text-white border border-gray-700 hover:border-gray-500 rounded px-2 py-1 transition shrink-0"
        >
          + Insattning
        </button>
      </div>

      {/* Deposit modal */}
      {showDeposit && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setShowDeposit(false); }}
        >
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-80 space-y-4 shadow-2xl">
            <h3 className="font-semibold text-white">Registrera insattning</h3>
            <p className="text-xs text-gray-500">
              Belopp du sattar in i papportfoljon. Paverkar disponibelt kapital.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Belopp (kr)</label>
                <input
                  type="number"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  placeholder="10000"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Notering (valfritt)</label>
                <input
                  type="text"
                  value={depositNote}
                  onChange={(e) => setDepositNote(e.target.value)}
                  placeholder="Startkapital"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div className="flex gap-3 pt-1">
              <button
                onClick={addDeposit}
                disabled={saving || !depositAmount}
                className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition"
              >
                {saving ? "Sparar..." : "Registrera"}
              </button>
              <button
                onClick={() => setShowDeposit(false)}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg py-2 text-sm transition"
              >
                Avbryt
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
