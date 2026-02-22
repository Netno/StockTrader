"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  date: string;
  rsi: number;
}

export default function RsiChart({ data, ticker }: { data: DataPoint[]; ticker: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-2">RSI (14) — {ticker}</p>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#6b7280", fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151" }}
            itemStyle={{ color: "#a78bfa" }}
          />
          <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "70", fill: "#ef4444", fontSize: 10 }} />
          <ReferenceLine y={35} stroke="#22c55e" strokeDasharray="4 2" label={{ value: "35", fill: "#22c55e", fontSize: 10 }} />
          <Line type="monotone" dataKey="rsi" stroke="#a78bfa" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
