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
import type { DailyStatPoint } from "./DashboardMockData";

interface AvgDurationChartProps {
  data: DailyStatPoint[];
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border px-3 py-2 shadow-xl text-sm"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border)",
        color: "var(--text-primary)",
      }}
    >
      <p className="font-bold">{label}</p>
      <p style={{ color: "var(--text-muted)" }}>
        TB: <span className="font-semibold text-teal-500">{payload[0].value} phút</span>
      </p>
    </div>
  );
}

export default function AvgDurationChart({ data }: AvgDurationChartProps) {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="durGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#14b8a6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--text-muted)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--text-muted)" }}
          axisLine={false}
          tickLine={false}
          unit=" ph"
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="avg_duration"
          stroke="#14b8a6"
          strokeWidth={2}
          fill="url(#durGrad)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
