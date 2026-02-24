"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const API = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

type Granularity = "daily" | "hourly";
type Metric = "calls" | "tokens" | "cache" | "latency";

interface ChartRow {
  label: string;
  date: string;
  hour?: number;
  model?: string;
  calls_ok: number;
  calls_failed: number;
  calls_rate_limited: number;
  cache_hits: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens?: number;
  total_latency_s: number;
}

const METRICS: { key: Metric; label: string }[] = [
  { key: "calls", label: "Anrop" },
  { key: "tokens", label: "Tokens" },
  { key: "cache", label: "Cache" },
  { key: "latency", label: "Svarstid" },
];

export default function AiStatsChart() {
  const [granularity, setGranularity] = useState<Granularity>("daily");
  const [metric, setMetric] = useState<Metric>("calls");
  const [rawData, setRawData] = useState<ChartRow[]>([]); // always hourly rows
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<string>(""); // for hourly: which day

  // Fetch hourly data once — aggregate daily client-side
  useEffect(() => {
    fetch(`${API}/api/ai-stats/history?granularity=hourly&days=30`, {
      cache: "no-store",
    })
      .then((r) => r.json())
      .then((d) => {
        if (Array.isArray(d)) {
          const sorted = [...d].sort((a, b) => {
            if (a.date !== b.date) return a.date.localeCompare(b.date);
            return (a.hour ?? 0) - (b.hour ?? 0);
          });
          setRawData(sorted);
          if (sorted.length > 0) {
            setSelectedDay(sorted[sorted.length - 1].date);
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []); // only once on mount

  // Aggregate hourly rows into daily totals client-side
  const dailyData: ChartRow[] = (() => {
    const byDate = new Map<string, ChartRow>();
    for (const row of rawData) {
      const existing = byDate.get(row.date);
      if (existing) {
        existing.calls_ok += row.calls_ok;
        existing.calls_failed += row.calls_failed;
        existing.calls_rate_limited += row.calls_rate_limited;
        existing.cache_hits += row.cache_hits;
        existing.input_tokens += row.input_tokens;
        existing.output_tokens += row.output_tokens;
        existing.total_latency_s += row.total_latency_s;
        existing.model = row.model; // use latest model
      } else {
        byDate.set(row.date, { ...row, label: row.date });
      }
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  })();

  // Available days for the day picker (hourly mode)
  const availableDays = [...new Set(rawData.map((r) => r.date))].sort();

  // For hourly: filter to selected day. For daily: last 30 entries.
  const chartData =
    granularity === "hourly"
      ? rawData.filter((r) => r.date === selectedDay)
      : dailyData.slice(-30);

  // Format label for display
  const formatLabel = (label: string) => {
    if (granularity === "hourly") {
      // "2026-02-24 14:00" → "14:00"
      const parts = label.split(" ");
      return parts.length === 2 ? parts[1] : label;
    }
    // "2026-02-24" → "24/2"
    const parts = label.split("-");
    if (parts.length === 3) {
      return `${parseInt(parts[2])}/${parseInt(parts[1])}`;
    }
    return label;
  };

  // Format day for display in picker: "2026-02-24" → "Mån 24/2"
  const formatDay = (dateStr: string) => {
    const d = new Date(dateStr + "T12:00:00");
    const weekday = ["Sön", "Mån", "Tis", "Ons", "Tor", "Fre", "Lör"][
      d.getDay()
    ];
    const [, m, day] = dateStr.split("-");
    return `${weekday} ${parseInt(day)}/${parseInt(m)}`;
  };

  // Get model from most recent entry
  const currentModel = chartData.length
    ? chartData[chartData.length - 1]?.model || "–"
    : "–";

  // Custom tooltip
  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean;
    payload?: Array<{ name: string; value: number; color: string }>;
    label?: string;
  }) => {
    if (!active || !payload?.length) return null;
    const row = chartData.find((d) => d.label === label);
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs shadow-lg">
        <p className="text-gray-400 mb-1">{label}</p>
        {row?.model && (
          <p className="text-blue-400 mb-2 font-mono text-[10px]">
            {row.model}
          </p>
        )}
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color }}>
            {p.name}: {p.value.toLocaleString("sv-SE")}
            {metric === "latency" ? "s" : ""}
          </p>
        ))}
      </div>
    );
  };

  const renderBars = () => {
    switch (metric) {
      case "calls":
        return (
          <>
            <Bar
              dataKey="calls_ok"
              name="Lyckade"
              fill="#22c55e"
              radius={[2, 2, 0, 0]}
              stackId="calls"
              activeBar={false}
            />
            <Bar
              dataKey="calls_rate_limited"
              name="Rate limited"
              fill="#f97316"
              radius={[0, 0, 0, 0]}
              stackId="calls"
              activeBar={false}
            />
            <Bar
              dataKey="calls_failed"
              name="Misslyckade"
              fill="#ef4444"
              radius={[2, 2, 0, 0]}
              stackId="calls"
              activeBar={false}
            />
          </>
        );
      case "tokens":
        return (
          <>
            <Bar
              dataKey="input_tokens"
              name="Input"
              fill="#3b82f6"
              radius={[2, 2, 0, 0]}
              stackId="tokens"
              activeBar={false}
            />
            <Bar
              dataKey="output_tokens"
              name="Output"
              fill="#8b5cf6"
              radius={[2, 2, 0, 0]}
              stackId="tokens"
              activeBar={false}
            />
          </>
        );
      case "cache":
        return (
          <>
            <Bar
              dataKey="cache_hits"
              name="Cache-träffar"
              fill="#06b6d4"
              radius={[2, 2, 0, 0]}
              activeBar={false}
            />
            <Bar
              dataKey="calls_ok"
              name="API-anrop"
              fill="#6366f1"
              radius={[2, 2, 0, 0]}
              activeBar={false}
            />
          </>
        );
      case "latency":
        return (
          <Bar
            dataKey="total_latency_s"
            name="Total latency"
            fill="#eab308"
            radius={[2, 2, 0, 0]}
            activeBar={false}
          />
        );
    }
  };

  if (loading && !rawData.length) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <p className="text-sm text-gray-500">Laddar graf...</p>
      </div>
    );
  }

  if (!rawData.length) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <p className="text-sm text-gray-500">
          Ingen AI-historik att visa ännu.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      {/* Header with model badge */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">AI-anrop</h3>
          <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20 font-mono">
            {currentModel}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2">
        {/* Granularity toggle */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700">
          {(["daily", "hourly"] as Granularity[]).map((g) => (
            <button
              key={g}
              onClick={() => setGranularity(g)}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                granularity === g
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {g === "daily" ? "Per dag" : "Per timme"}
            </button>
          ))}
        </div>

        {/* Metric toggle */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                metric === m.key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Day picker for hourly mode */}
      {granularity === "hourly" && availableDays.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {availableDays.map((day) => (
            <button
              key={day}
              onClick={() => setSelectedDay(day)}
              className={`px-2.5 py-1 text-xs rounded-md transition ${
                selectedDay === day
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white border border-gray-700"
              }`}
            >
              {formatDay(day)}
            </button>
          ))}
        </div>
      )}

      {/* Chart */}
      <div className="rounded-lg bg-gray-900">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={chartData}
            margin={{ top: 4, right: 0, left: -20, bottom: 4 }}
            style={{ backgroundColor: "#111827", borderRadius: "8px" }}
          >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1f2937"
            fill="#111827"
            fillOpacity={1}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            tickFormatter={formatLabel}
            interval={0}
            angle={0}
            textAnchor="middle"
            height={30}
          />
          <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
          <Tooltip content={<CustomTooltip />} cursor={false} />
          <Legend
            wrapperStyle={{ fontSize: "11px", color: "#9ca3af" }}
            iconSize={10}
          />
            {renderBars()}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
