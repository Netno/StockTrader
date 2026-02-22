"use client";

import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  date: string;
  price: number;
  upper: number;
  lower: number;
  mid: number;
}

export default function BollingerChart({ data, ticker }: { data: DataPoint[]; ticker: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-2">Bollinger Bands — {ticker}</p>
      <ResponsiveContainer width="100%" height={120}>
        <ComposedChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} />
          <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151" }}
            itemStyle={{ fontSize: 11 }}
          />
          <Area
            dataKey="upper"
            fill="#3b82f620"
            stroke="transparent"
            name="Övre band"
          />
          <Area
            dataKey="lower"
            fill="#3b82f620"
            stroke="transparent"
            name="Undre band"
          />
          <Line dataKey="mid" stroke="#6b7280" dot={false} strokeDasharray="4 2" name="Mitten" />
          <Line dataKey="price" stroke="#f59e0b" dot={false} strokeWidth={2} name="Pris" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
