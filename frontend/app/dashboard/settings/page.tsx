"use client";

import { useEffect, useState, useTransition } from "react";
import AiStatsChart from "@/components/dashboard/AiStatsChart";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

interface DiscoveryCandidate {
  ticker: string;
  name: string;
  combined_score: number;
  candidate_score: number;
  buy_pre_score: number;
  reasons: string[];
  buy_reasons?: string[];
  is_positioned: boolean;
}

interface FilteredTicker {
  ticker: string;
  reason: string;
}

interface ErrorTicker {
  ticker: string;
  error: string;
}

interface DiscoveryResult {
  ok: boolean;
  scanned?: number;
  errors?: number;
  filtered_count?: number;
  total_universe?: number;
  market_regime?: string;
  watchlist_size?: number;
  candidates?: DiscoveryCandidate[];
  filtered?: FilteredTicker[];
  error_tickers?: ErrorTicker[];
  scanned_at?: string;
  error?: string;
}

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
  const [discoveryRunning, setDiscoveryRunning] = useState(false);
  const [discoveryResult, setDiscoveryResult] =
    useState<DiscoveryResult | null>(null);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [showFiltered, setShowFiltered] = useState(false);
  const [showErrors, setShowErrors] = useState(false);

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
    // Load latest discovery scan from DB
    fetch(`${API}/api/discovery-scan/latest`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) setDiscoveryResult(d);
      })
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

      {/* Discovery Scan */}
      <h2 className="text-lg font-bold mt-8">Discovery Scan</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <p className="text-sm text-gray-400">
          Skannar alla ~124 aktier på Nasdaq Stockholm (Large &amp; Mid Cap) och
          väljer de bästa kandidaterna som watchlist. Tar ca 2–5 minuter.
        </p>
        <button
          onClick={async () => {
            setDiscoveryRunning(true);
            setDiscoveryResult(null);
            setExpandedTicker(null);
            setShowFiltered(false);
            setShowErrors(false);
            try {
              // Trigger scan in background
              const res = await fetch(`${API}/api/discovery-scan`, {
                method: "POST",
                cache: "no-store",
              });
              const startData = await res.json();
              if (!startData.ok) {
                setDiscoveryResult({
                  ok: false,
                  error: startData.error ?? "Kunde inte starta scan.",
                });
                setDiscoveryRunning(false);
                return;
              }
              // Poll for result every 10 seconds
              const poll = setInterval(async () => {
                try {
                  const statusRes = await fetch(
                    `${API}/api/discovery-scan/status`,
                    { cache: "no-store" },
                  );
                  const status = await statusRes.json();
                  if (!status.running) {
                    clearInterval(poll);
                    // Fetch the saved result
                    const latestRes = await fetch(
                      `${API}/api/discovery-scan/latest`,
                      { cache: "no-store" },
                    );
                    const latest = await latestRes.json();
                    if (latest.ok) {
                      setDiscoveryResult(latest);
                    } else {
                      setDiscoveryResult({
                        ok: false,
                        error: "Scan klar men kunde inte hämta resultat.",
                      });
                    }
                    setDiscoveryRunning(false);
                  }
                } catch {
                  // Keep polling on network errors
                }
              }, 10000);
              // Safety timeout after 8 minutes
              setTimeout(() => {
                clearInterval(poll);
                setDiscoveryRunning(false);
              }, 480000);
            } catch {
              setDiscoveryResult({
                ok: false,
                error: "Nätverksfel — kunde inte nå agenten.",
              });
              setDiscoveryRunning(false);
            }
          }}
          disabled={discoveryRunning}
          className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg px-5 py-2 text-sm font-semibold transition"
        >
          {discoveryRunning ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Skannar aktier...
            </span>
          ) : (
            "Kör Discovery Scan"
          )}
        </button>

        {discoveryResult && (
          <div className="space-y-3">
            {discoveryResult.ok ? (
              <>
                {/* Tidsstämpel */}
                {discoveryResult.scanned_at && (
                  <p className="text-xs text-gray-600">
                    Senaste scan:{" "}
                    {new Date(discoveryResult.scanned_at).toLocaleString(
                      "sv-SE",
                    )}
                  </p>
                )}

                {/* Summary badges */}
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="bg-gray-800 rounded-lg px-3 py-1.5">
                    <span className="text-gray-500">Skannade: </span>
                    <span className="text-white font-semibold">
                      {discoveryResult.scanned}
                    </span>
                    {discoveryResult.total_universe && (
                      <span className="text-gray-600">
                        /{discoveryResult.total_universe}
                      </span>
                    )}
                  </span>
                  <span className="bg-gray-800 rounded-lg px-3 py-1.5">
                    <span className="text-gray-500">I watchlist: </span>
                    <span className="text-white font-semibold">
                      {discoveryResult.watchlist_size}
                    </span>
                  </span>
                  <span className="bg-gray-800 rounded-lg px-3 py-1.5">
                    <span className="text-gray-500">Marknad: </span>
                    <span
                      className={`font-semibold ${
                        discoveryResult.market_regime === "BULL"
                          ? "text-green-400"
                          : discoveryResult.market_regime === "BULL_EARLY"
                            ? "text-green-300"
                            : discoveryResult.market_regime === "BEAR"
                              ? "text-red-400"
                              : "text-yellow-400"
                      }`}
                    >
                      {discoveryResult.market_regime}
                    </span>
                  </span>
                  {(discoveryResult.filtered_count ?? 0) > 0 && (
                    <span
                      className="bg-gray-800 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-gray-700 transition"
                      onClick={() => setShowFiltered(!showFiltered)}
                    >
                      <span className="text-gray-500">Filtrerade: </span>
                      <span className="text-orange-400 font-semibold">
                        {discoveryResult.filtered_count}
                      </span>
                      <span className="text-gray-600 ml-1 text-xs">
                        {showFiltered ? "▲" : "▼"}
                      </span>
                    </span>
                  )}
                  {(discoveryResult.errors ?? 0) > 0 && (
                    <span
                      className="bg-gray-800 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-gray-700 transition"
                      onClick={() => setShowErrors(!showErrors)}
                    >
                      <span className="text-gray-500">Fel: </span>
                      <span className="text-red-400 font-semibold">
                        {discoveryResult.errors}
                      </span>
                      <span className="text-gray-600 ml-1 text-xs">
                        {showErrors ? "▲" : "▼"}
                      </span>
                    </span>
                  )}
                </div>

                {/* Filtered tickers (collapsible) */}
                {showFiltered &&
                  discoveryResult.filtered &&
                  discoveryResult.filtered.length > 0 && (
                    <div className="bg-gray-800 rounded-lg p-3 space-y-1 max-h-48 overflow-y-auto">
                      <p className="text-xs font-semibold text-orange-400 mb-2">
                        Filtrerade aktier
                      </p>
                      {discoveryResult.filtered.map((f) => (
                        <div
                          key={f.ticker}
                          className="flex justify-between text-xs gap-2"
                        >
                          <span className="text-gray-400 font-mono shrink-0">
                            {f.ticker}
                          </span>
                          <span className="text-gray-500 text-right">
                            {f.reason}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                {/* Error tickers (collapsible) */}
                {showErrors &&
                  discoveryResult.error_tickers &&
                  discoveryResult.error_tickers.length > 0 && (
                    <div className="bg-gray-800 rounded-lg p-3 space-y-1 max-h-48 overflow-y-auto">
                      <p className="text-xs font-semibold text-red-400 mb-2">
                        Aktier med fel
                      </p>
                      {discoveryResult.error_tickers.map((e) => (
                        <div
                          key={e.ticker}
                          className="flex justify-between text-xs gap-4"
                        >
                          <span className="text-gray-400 font-mono shrink-0">
                            {e.ticker}
                          </span>
                          <span className="text-red-400/70 truncate text-right">
                            {e.error}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                {/* Candidates table */}
                {discoveryResult.candidates &&
                  discoveryResult.candidates.length > 0 && (
                    <div className="bg-gray-800 rounded-lg overflow-hidden">
                      <div className="px-4 py-2 border-b border-gray-700">
                        <p className="text-xs font-semibold text-gray-400">
                          Topp-kandidater i ny watchlist
                        </p>
                      </div>
                      {/* Desktop table */}
                      <div className="hidden sm:block">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs text-gray-500 border-b border-gray-700">
                              <th className="px-4 py-2">#</th>
                              <th className="px-4 py-2">Aktie</th>
                              <th className="px-4 py-2 text-right">Kombi</th>
                              <th className="px-4 py-2 text-right">Köp-pre</th>
                              <th className="px-4 py-2 text-right">Kandidat</th>
                              <th className="px-4 py-2">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-700">
                            {discoveryResult.candidates.map((c, i) => (
                              <tr
                                key={c.ticker}
                                className={`text-gray-300 cursor-pointer hover:bg-gray-700/50 transition ${expandedTicker === c.ticker ? "bg-gray-700/30" : ""}`}
                                onClick={() =>
                                  setExpandedTicker(
                                    expandedTicker === c.ticker
                                      ? null
                                      : c.ticker,
                                  )
                                }
                              >
                                <td className="px-4 py-2 text-gray-500 text-xs">
                                  {i + 1}
                                </td>
                                <td className="px-4 py-2">
                                  <span className="text-white font-semibold">
                                    {c.ticker}
                                  </span>
                                  <span className="text-gray-500 ml-2 text-xs">
                                    {c.name}
                                  </span>
                                  {c.buy_reasons &&
                                    c.buy_reasons.length > 0 && (
                                      <span className="text-gray-600 ml-1 text-xs">
                                        {expandedTicker === c.ticker
                                          ? "▲"
                                          : "▼"}
                                      </span>
                                    )}
                                </td>
                                <td className="px-4 py-2 text-right font-mono">
                                  <span
                                    className={
                                      c.combined_score >= 50
                                        ? "text-green-400"
                                        : c.combined_score >= 30
                                          ? "text-yellow-400"
                                          : "text-gray-400"
                                    }
                                  >
                                    {c.combined_score.toFixed(0)}p
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-right font-mono">
                                  <span
                                    className={
                                      c.buy_pre_score >= 40
                                        ? "text-green-400"
                                        : "text-gray-400"
                                    }
                                  >
                                    {c.buy_pre_score.toFixed(0)}p
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-right font-mono text-gray-400">
                                  {c.candidate_score.toFixed(0)}p
                                </td>
                                <td className="px-4 py-2">
                                  {c.is_positioned ? (
                                    <span className="text-xs bg-blue-500/15 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">
                                      Position
                                    </span>
                                  ) : (
                                    <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">
                                      Ny
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {/* Expanded buy reasons (below table) */}
                        {expandedTicker &&
                          (() => {
                            const c = discoveryResult.candidates?.find(
                              (x) => x.ticker === expandedTicker,
                            );
                            if (!c?.buy_reasons?.length) return null;
                            return (
                              <div className="px-4 py-3 border-t border-gray-700 bg-gray-750">
                                <p className="text-xs text-gray-500 mb-1.5">
                                  Köpsignaler för {c.ticker}:
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {c.buy_reasons.map((r, ri) => (
                                    <span
                                      key={ri}
                                      className="text-xs bg-gray-700/50 text-gray-400 px-2 py-0.5 rounded"
                                    >
                                      {r}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                      </div>
                      {/* Mobile cards */}
                      <div className="sm:hidden divide-y divide-gray-700">
                        {discoveryResult.candidates.map((c, i) => (
                          <div
                            key={c.ticker}
                            className="p-3 space-y-1 cursor-pointer"
                            onClick={() =>
                              setExpandedTicker(
                                expandedTicker === c.ticker ? null : c.ticker,
                              )
                            }
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="text-white font-semibold">
                                  {i + 1}. {c.ticker}
                                </span>
                                <span className="text-gray-500 ml-2 text-xs">
                                  {c.name}
                                </span>
                              </div>
                              {c.is_positioned && (
                                <span className="text-xs bg-blue-500/15 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">
                                  Position
                                </span>
                              )}
                            </div>
                            <div className="flex gap-3 text-xs">
                              <span>
                                <span className="text-gray-500">Kombi </span>
                                <span
                                  className={
                                    c.combined_score >= 50
                                      ? "text-green-400 font-semibold"
                                      : "text-gray-300"
                                  }
                                >
                                  {c.combined_score.toFixed(0)}p
                                </span>
                              </span>
                              <span>
                                <span className="text-gray-500">Köp </span>
                                <span
                                  className={
                                    c.buy_pre_score >= 40
                                      ? "text-green-400 font-semibold"
                                      : "text-gray-300"
                                  }
                                >
                                  {c.buy_pre_score.toFixed(0)}p
                                </span>
                              </span>
                            </div>
                            {expandedTicker === c.ticker &&
                              c.buy_reasons &&
                              c.buy_reasons.length > 0 && (
                                <div className="flex flex-wrap gap-1 pt-1">
                                  {c.buy_reasons.map((r, ri) => (
                                    <span
                                      key={ri}
                                      className="text-xs bg-gray-700/50 text-gray-400 px-2 py-0.5 rounded"
                                    >
                                      {r}
                                    </span>
                                  ))}
                                </div>
                              )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </>
            ) : (
              <p className="text-sm text-red-400">
                {discoveryResult.error ?? "Okänt fel"}
              </p>
            )}
          </div>
        )}
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
