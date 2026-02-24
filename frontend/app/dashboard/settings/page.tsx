"use client";

import { useEffect, useState, useTransition } from "react";
import AiStatsChart from "../../components/dashboard/AiStatsChart";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

interface AiStats {
  date: string;
  hour: number;
  model: string;
  calls_ok: number;
  calls_failed: number;
  calls_rate_limited: number;
  cache_hits: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_calls: number;
  avg_latency_s: number;
  total_latency_s: number;
  by_type: Record<string, number>;
  daily_totals: {
    calls_ok: number;
    calls_failed: number;
    calls_rate_limited: number;
    cache_hits: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    total_calls: number;
    avg_latency_s: number;
    total_latency_s: number;
  };
}

interface AiStatsHistoryRow {
  date: string;
  model: string;
  calls_ok: number;
  calls_failed: number;
  calls_rate_limited: number;
  cache_hits: number;
  input_tokens: number;
  output_tokens: number;
  total_latency_s: number;
  by_type: Record<string, number>;
}

const SETTING_META: Record<
  string,
  {
    label: string;
    description: string;
    unit: string;
    min: number;
    max: number;
    step: number;
  }
> = {
  max_positions: {
    label: "Max öppna positioner",
    description: "Hur många aktier du maximalt äger samtidigt.",
    unit: "st",
    min: 1,
    max: 10,
    step: 1,
  },
  max_position_size: {
    label: "Max positionsstorlek",
    description:
      "Maximalt belopp som investeras per köpsignal. Vid lägre confidence investeras 72% eller 40% av detta.",
    unit: "kr",
    min: 500,
    max: 50000,
    step: 500,
  },
  signal_threshold: {
    label: "Signaltröskel",
    description:
      "Minimumscore (0–100) som krävs för att en köp- eller säljsignal ska skickas. Lägre = fler signaler, högre = färre men starkare signaler.",
    unit: "p",
    min: 30,
    max: 90,
    step: 5,
  },
};

export default function SettingsPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const [aiStats, setAiStats] = useState<AiStats | null>(null);
  const [aiHistory, setAiHistory] = useState<AiStatsHistoryRow[]>([]);

  useEffect(() => {
    fetch(`${API}/api/settings`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setValues(d.settings ?? {}))
      .catch(() => setError("Kunde inte ladda inställningar."));
    fetch(`${API}/api/ai-stats`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setAiStats(d))
      .catch(() => {});
    fetch(`${API}/api/ai-stats/history`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setAiHistory(Array.isArray(d) ? d : []))
      .catch(() => {});
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
                <p className="text-xs text-gray-500 mt-0.5">
                  {meta.description}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  min={meta.min}
                  max={meta.max}
                  step={meta.step}
                  value={values[key] ?? ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [key]: e.target.value }))
                  }
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
        {saved && (
          <span className="text-sm text-green-400">
            ✓ Sparade — gäller direkt
          </span>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-1 text-xs text-gray-500">
        <p className="font-semibold text-gray-400 mb-2">
          Hur fungerar inställningarna?
        </p>
        <p>
          Ändringar sparas direkt i databasen och gäller från nästa analyscykel
          (inom 2 minuter). Ingen omstart av agenten krävs.
        </p>
        <p className="mt-2">
          Dessa inställningar ersätter de hårdkodade standardvärdena och kan
          ändras när som helst.
        </p>
      </div>

      {/* AI Usage Stats */}
      <h2 className="text-lg font-bold mt-8">AI-användning idag</h2>
      {aiStats ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-semibold text-white">Modell:</span>
            <span className="text-sm text-blue-400 font-mono">
              {aiStats.model}
            </span>
            <span className="text-xs text-gray-500 ml-auto">
              {aiStats.date}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-white">
                {aiStats.daily_totals?.calls_ok ?? aiStats.calls_ok}
              </p>
              <p className="text-xs text-gray-500">Lyckade anrop</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-red-400">
                {aiStats.daily_totals?.calls_failed ?? aiStats.calls_failed}
              </p>
              <p className="text-xs text-gray-500">Misslyckade</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-orange-400">
                {aiStats.daily_totals?.calls_rate_limited ??
                  aiStats.calls_rate_limited}
              </p>
              <p className="text-xs text-gray-500">Rate limited</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-green-400">
                {aiStats.daily_totals?.cache_hits ?? aiStats.cache_hits}
              </p>
              <p className="text-xs text-gray-500">Cache-träffar</p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Input tokens</p>
              <p className="text-lg font-bold text-white">
                {(
                  aiStats.daily_totals?.input_tokens ?? aiStats.input_tokens
                ).toLocaleString("sv-SE")}
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Output tokens</p>
              <p className="text-lg font-bold text-white">
                {(
                  aiStats.daily_totals?.output_tokens ?? aiStats.output_tokens
                ).toLocaleString("sv-SE")}
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Totalt tokens</p>
              <p className="text-lg font-bold text-white">
                {(
                  aiStats.daily_totals?.total_tokens ?? aiStats.total_tokens
                ).toLocaleString("sv-SE")}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Snitt svarstid</p>
              <p className="text-lg font-bold text-white">
                {aiStats.daily_totals?.avg_latency_s ?? aiStats.avg_latency_s}s
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Total tid i AI</p>
              <p className="text-lg font-bold text-white">
                {(
                  aiStats.daily_totals?.total_latency_s ??
                  aiStats.total_latency_s
                ).toFixed(1)}
                s
              </p>
            </div>
          </div>

          {Object.keys(aiStats.by_type).length > 0 && (
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-2">Anrop per typ</p>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(aiStats.by_type).map(([typ, count]) => (
                  <span
                    key={typ}
                    className="text-xs bg-blue-500/10 text-blue-400 px-2 py-1 rounded-full border border-blue-500/20"
                  >
                    {typ}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-600">
            Statistiken sparas i databasen och överlever deploys. Cache-träffar
            = sparade AI-anrop (nyheter cachas 6h, beskrivningar 2h).
          </p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-sm text-gray-500">Laddar AI-statistik...</p>
        </div>
      )}

      {/* AI Stats Chart */}
      <AiStatsChart />

      {/* AI Stats History */}
      {aiHistory.length > 0 && (
        <>
          <h2 className="text-lg font-bold mt-8">AI-historik</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            {/* Desktop table */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                    <th className="px-4 py-3">Datum</th>
                    <th className="px-4 py-3 text-right">Anrop</th>
                    <th className="px-4 py-3 text-right">Fel</th>
                    <th className="px-4 py-3 text-right">Rate&nbsp;limit</th>
                    <th className="px-4 py-3 text-right">Cache</th>
                    <th className="px-4 py-3 text-right">Tokens</th>
                    <th className="px-4 py-3 text-right">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {aiHistory.map((row) => (
                    <tr key={row.date} className="text-gray-300">
                      <td className="px-4 py-2 text-white font-mono text-xs">
                        {row.date}
                      </td>
                      <td className="px-4 py-2 text-right text-green-400">
                        {row.calls_ok}
                      </td>
                      <td className="px-4 py-2 text-right text-red-400">
                        {row.calls_failed || "–"}
                      </td>
                      <td className="px-4 py-2 text-right text-orange-400">
                        {row.calls_rate_limited || "–"}
                      </td>
                      <td className="px-4 py-2 text-right text-blue-400">
                        {row.cache_hits}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {(row.input_tokens + row.output_tokens).toLocaleString(
                          "sv-SE",
                        )}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-500">
                        {row.total_latency_s.toFixed(1)}s
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="sm:hidden divide-y divide-gray-800">
              {aiHistory.map((row) => (
                <div key={row.date} className="p-4 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-xs font-mono text-white">
                      {row.date}
                    </span>
                    <span className="text-xs text-gray-500">{row.model}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <p className="text-green-400 font-bold">{row.calls_ok}</p>
                      <p className="text-gray-600">Anrop</p>
                    </div>
                    <div>
                      <p className="text-blue-400 font-bold">
                        {row.cache_hits}
                      </p>
                      <p className="text-gray-600">Cache</p>
                    </div>
                    <div>
                      <p className="text-white font-bold">
                        {(row.input_tokens + row.output_tokens).toLocaleString(
                          "sv-SE",
                        )}
                      </p>
                      <p className="text-gray-600">Tokens</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
