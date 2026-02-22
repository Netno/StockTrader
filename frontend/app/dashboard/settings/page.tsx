"use client";

import { useEffect, useState, useTransition } from "react";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

const SETTING_META: Record<string, { label: string; description: string; unit: string; min: number; max: number; step: number }> = {
  max_positions: {
    label: "Max öppna positioner",
    description: "Hur många aktier du maximalt äger samtidigt.",
    unit: "st",
    min: 1, max: 10, step: 1,
  },
  max_position_size: {
    label: "Max positionsstorlek",
    description: "Maximalt belopp som investeras per köpsignal. Vid lägre confidence investeras 72% eller 40% av detta.",
    unit: "kr",
    min: 500, max: 50000, step: 500,
  },
  signal_threshold: {
    label: "Signaltröskel",
    description: "Minimumscore (0–100) som krävs för att en köp- eller säljsignal ska skickas. Lägre = fler signaler, högre = färre men starkare signaler.",
    unit: "p",
    min: 30, max: 90, step: 5,
  },
};

export default function SettingsPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    fetch(`${API}/api/settings`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setValues(d.settings ?? {}))
      .catch(() => setError("Kunde inte ladda inställningar."));
  }, []);

  const handleSave = () => {
    setError("");
    setSaved(false);
    startTransition(async () => {
      try {
        const res = await fetch(`${API}/api/settings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
        });
        const data = await res.json();
        if (data.error) {
          setError(data.error);
        } else {
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
        }
      } catch {
        setError("Nätverksfel — kunde inte spara.");
      }
    });
  };

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-xl font-bold">Inställningar</h1>

      <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
        {Object.entries(SETTING_META).map(([key, meta]) => (
          <div key={key} className="p-5 space-y-2">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-white">{meta.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{meta.description}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  min={meta.min}
                  max={meta.max}
                  step={meta.step}
                  value={values[key] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                  className="w-24 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white text-right focus:outline-none focus:border-blue-500"
                />
                <span className="text-xs text-gray-500 w-6">{meta.unit}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={pending}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-5 py-2 text-sm font-semibold transition"
        >
          {pending ? "Sparar..." : "Spara inställningar"}
        </button>
        {saved && <span className="text-sm text-green-400">✓ Sparade — gäller direkt</span>}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-1 text-xs text-gray-500">
        <p className="font-semibold text-gray-400 mb-2">Hur fungerar inställningarna?</p>
        <p>Ändringar sparas direkt i databasen och gäller från nästa analyscykel (inom 2 minuter). Ingen omstart av agenten krävs.</p>
        <p className="mt-2">Dessa inställningar ersätter de hårdkodade standardvärdena och kan ändras när som helst.</p>
      </div>
    </div>
  );
}
