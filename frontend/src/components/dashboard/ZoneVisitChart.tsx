"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ZoneVisitStat } from "./DashboardMockData";

interface ZoneVisitChartProps {
  data: ZoneVisitStat[];
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as ZoneVisitStat;
  const total = payload[0].payload.__total as number;
  return (
    <div
      className="rounded-xl border px-4 py-2.5 shadow-xl text-sm"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border)",
        color: "var(--text-primary)",
      }}
    >
      <p className="font-bold">{d.zone}</p>
      <p style={{ color: "var(--text-muted)" }}>
        {d.visits} lượt ({total > 0 ? Math.round((d.visits / total) * 100) : 0}%)
      </p>
    </div>
  );
}

export default function ZoneVisitChart({ data }: ZoneVisitChartProps) {
  const total = data.reduce((s, d) => s + d.visits, 0);
  const enriched = data.map((d) => ({ ...d, __total: total }));

  return (
    <div className="flex flex-col gap-4">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={enriched}
            dataKey="visits"
            nameKey="zone"
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={3}
            strokeWidth={0}
          >
            {enriched.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend list */}
      <div className="space-y-2">
        {data.map((d) => (
          <div key={d.zone} className="flex items-center gap-2">
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: d.color }}
            />
            <span className="flex-1 truncate text-xs" style={{ color: "var(--text-secondary)" }}>
              {d.zone}
            </span>
            <span className="text-xs font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {d.visits}
            </span>
            <span className="w-10 text-right text-[11px]" style={{ color: "var(--text-muted)" }}>
              {total > 0 ? Math.round((d.visits / total) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
