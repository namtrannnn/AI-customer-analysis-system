"use client";

import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { DailyStatPoint } from "./DashboardMockData";

interface TrendChartProps {
  data: DailyStatPoint[];
  mode: "line" | "bar";
}

// Custom tooltip
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border px-4 py-3 shadow-xl text-sm"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border)",
        color: "var(--text-primary)",
      }}
    >
      <p className="mb-2 font-bold">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 py-0.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: entry.color }}
          />
          <span style={{ color: "var(--text-muted)" }}>{entry.name}:</span>
          <span className="font-semibold">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function TrendChart({ data, mode }: TrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--border)"
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, color: "var(--text-muted)", paddingTop: 12 }}
        />

        {mode === "bar" ? (
          <>
            <Bar dataKey="new_customers" name="Khách mới"    fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="returning"     name="Quay lại"     fill="#22c55e" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </>
        ) : (
          <>
            <Line
              type="monotone"
              dataKey="total"
              name="Tổng khách"
              stroke="#6366f1"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="new_customers"
              name="Khách mới"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
              strokeDasharray="5 3"
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="returning"
              name="Quay lại"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              strokeDasharray="5 3"
              activeDot={{ r: 4 }}
            />
          </>
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
