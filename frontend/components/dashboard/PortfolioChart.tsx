"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  date: string;
  value: number;
}

export default function PortfolioChart({ data }: { data: DataPoint[] }) {
  if (!data?.length) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
        Ingen portföljdata ännu.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 11 }} />
        <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151" }}
          labelStyle={{ color: "#9ca3af" }}
          itemStyle={{ color: "#60a5fa" }}
          formatter={(v: number | undefined) => [`${(v ?? 0).toFixed(0)} kr`, "Portfölj"]}
        />
        <Area type="monotone" dataKey="value" stroke="#3b82f6" fill="url(#grad)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
