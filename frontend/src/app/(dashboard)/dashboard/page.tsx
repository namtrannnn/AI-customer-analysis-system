"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Users, UserPlus, RefreshCw, Clock,
  BarChart2, LineChart, TrendingUp, TrendingDown,
  CalendarDays, Info,
} from "lucide-react";
import StatCard from "@/components/common/StatCard";
import TrendChart from "@/components/dashboard/TrendChart";
import ZoneVisitChart from "@/components/dashboard/ZoneVisitChart";
import AvgDurationChart from "@/components/dashboard/AvgDurationChart";
import {
  MOCK_DATA,
  computeStats,
  getPrevPoints,
  type DashboardStats,
  type DailyStatPoint,
  type RangeKey,
} from "@/components/dashboard/DashboardMockData";
import {
  getDashboardOverview,
  getDashboardTrend,
  getDashboardZoneVisits,
  type DashboardFilters,
  type DashboardOverview,
  type DashboardTrendResponse,
  type DashboardZoneVisitStat,
} from "@/services/dashboard.service";

// ─── Date range tabs ───────────────────────────────────────────────────────────
const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "7d",  label: "7 ngày" },
  { key: "30d", label: "30 ngày" },
  { key: "3m",  label: "3 tháng" },
];

function toISODate(date: Date) {
  return date.toISOString().split("T")[0];
}

function getFiltersForRange(range: RangeKey): DashboardFilters {
  const end = new Date();
  const start = new Date(end);
  if (range === "7d") start.setDate(end.getDate() - 7);
  if (range === "30d") start.setDate(end.getDate() - 30);
  if (range === "3m") start.setDate(end.getDate() - 90);

  return {
    start_date: toISODate(start),
    end_date: toISODate(end),
    group_by: range === "3m" ? "month" : "day",
  };
}

function mapTrendToPoints(
  trend: DashboardTrendResponse,
  overview: DashboardOverview,
): DailyStatPoint[] {
  const avgDurationMinutes = Math.round((overview.avg_duration_seconds || 0) / 60);
  return trend.data.map((point) => ({
    date: point.label,
    total: point.total_visits,
    new_customers: point.new_visitors,
    returning: point.returning_visitors,
    avg_duration: avgDurationMinutes,
  }));
}

function mapOverviewToStats(overview: DashboardOverview): DashboardStats {
  return {
    total_customers: overview.total_visits,
    new_customers: overview.new_visitors,
    returning_customers: overview.returning_visitors,
    avg_duration_minutes: Math.round((overview.avg_duration_seconds || 0) / 60),
    total_change: 0,
    new_change: 0,
    returning_change: 0,
    duration_change: 0,
  };
}

// ─── Trend badge ───────────────────────────────────────────────────────────────
function TrendBadge({ value }: { value: number }) {
  const up = value >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        up
          ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
          : "bg-red-50 text-red-500 dark:bg-red-900/20 dark:text-red-400"
      }`}
    >
      {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {up ? "+" : ""}{value}%
    </span>
  );
}

// ─── Section wrapper ───────────────────────────────────────────────────────────
function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl p-5 ${className}`}
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {children}
    </div>
  );
}

// ─── Mock badge ───────────────────────────────────────────────────────────────
function MockBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
      <Info className="h-3 w-3" />
      Mock data
    </span>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [range, setRange]     = useState<RangeKey>("7d");
  const [chartMode, setChartMode] = useState<"line" | "bar">("line");
  const [apiPoints, setApiPoints] = useState<DailyStatPoint[] | null>(null);
  const [apiStats, setApiStats] = useState<DashboardStats | null>(null);
  const [zoneVisits, setZoneVisits] = useState<DashboardZoneVisitStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [usingFallback, setUsingFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError(null);
      const filters = getFiltersForRange(range);

      try {
        const [overview, trend, zoneVisitData] = await Promise.all([
          getDashboardOverview(filters),
          getDashboardTrend(filters),
          getDashboardZoneVisits(filters),
        ]);
        const mappedPoints = mapTrendToPoints(trend, overview);
        if (cancelled) return;

        setZoneVisits(zoneVisitData);

        if (mappedPoints.length === 0) {
          setApiPoints(null);
          setApiStats(null);
          setUsingFallback(true);
          return;
        }

        setApiPoints(mappedPoints);
        setApiStats(mapOverviewToStats(overview));
        setUsingFallback(false);
      } catch (err) {
        if (cancelled) return;
        console.error("Không thể tải dashboard từ API:", err);
        setApiPoints(null);
        setApiStats(null);
        setZoneVisits([]);
        setUsingFallback(true);
        setError("Không thể tải dữ liệu dashboard từ API, đang hiển thị dữ liệu mẫu.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [range]);

  const points     = apiPoints ?? MOCK_DATA[range];
  const prevPoints = useMemo(() => getPrevPoints(points), [points]);
  const fallbackStats = useMemo(() => computeStats(points, prevPoints), [points, prevPoints]);
  const stats      = apiStats ?? fallbackStats;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Dashboard tổng hợp
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            Theo dõi chỉ số khách hàng và xu hướng hoạt động cửa hàng.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {loading && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-0.5 text-[11px] font-semibold text-sky-600 dark:bg-sky-900/30 dark:text-sky-400">
              Đang tải
            </span>
          )}
          {usingFallback && <MockBadge />}
          {/* Date range picker */}
          <div
            className="flex items-center gap-1 rounded-xl p-1"
            style={{ background: "var(--bg-surface-2)", border: "1px solid var(--border)" }}
          >
            <CalendarDays className="ml-1.5 h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setRange(opt.key)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  range === opt.key
                    ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-700 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-300">
          {error}
        </div>
      )}

      {/* ── Stat cards ── */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Tổng lượt khách"
          value={stats.total_customers.toLocaleString()}
          sub={`So với kỳ trước`}
          gradient="from-indigo-500 to-violet-600"
          icon={<Users className="h-5 w-5 text-white" />}
          trend={{ value: `${stats.total_change > 0 ? "+" : ""}${stats.total_change}%`, up: stats.total_change >= 0 }}
        />
        <StatCard
          label="Khách mới"
          value={stats.new_customers.toLocaleString()}
          sub="Lần đầu ghé thăm"
          gradient="from-emerald-500 to-teal-500"
          icon={<UserPlus className="h-5 w-5 text-white" />}
          trend={{ value: `${stats.new_change > 0 ? "+" : ""}${stats.new_change}%`, up: stats.new_change >= 0 }}
        />
        <StatCard
          label="Khách quay lại"
          value={stats.returning_customers.toLocaleString()}
          sub="Đã từng ghé trước đó"
          gradient="from-amber-500 to-orange-500"
          icon={<RefreshCw className="h-5 w-5 text-white" />}
          trend={{ value: `${stats.returning_change > 0 ? "+" : ""}${stats.returning_change}%`, up: stats.returning_change >= 0 }}
        />
        <StatCard
          label="Thời gian ở lại TB"
          value={`${stats.avg_duration_minutes} phút`}
          sub="Trung bình mỗi lượt"
          gradient="from-sky-500 to-cyan-500"
          icon={<Clock className="h-5 w-5 text-white" />}
          trend={{ value: `${stats.duration_change > 0 ? "+" : ""}${stats.duration_change}%`, up: stats.duration_change >= 0 }}
        />
      </div>

      {/* ── Main chart + Zone pie ── */}
      <div className="grid gap-5 lg:grid-cols-[1fr_280px]">
        {/* Trend chart */}
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Xu hướng khách hàng
              </h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {range === "7d" ? "7 ngày gần nhất" : range === "30d" ? "30 ngày gần nhất" : "3 tháng gần nhất"}
              </p>
            </div>

            {/* Chart mode toggle */}
            <div
              className="flex items-center rounded-lg p-0.5"
              style={{ background: "var(--bg-surface-2)" }}
            >
              <button
                onClick={() => setChartMode("line")}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
                  chartMode === "line"
                    ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
                }`}
              >
                <LineChart className="h-3.5 w-3.5" />
                Line
              </button>
              <button
                onClick={() => setChartMode("bar")}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
                  chartMode === "bar"
                    ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
                }`}
              >
                <BarChart2 className="h-3.5 w-3.5" />
                Bar
              </button>
            </div>
          </div>

          <TrendChart data={points} mode={chartMode} />
        </Card>

        {/* Zone visits pie */}
        <Card>
          <div className="mb-3">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Lượt thăm theo vùng
            </h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Phân bổ khu vực trong kỳ
            </p>
          </div>
          {zoneVisits.length > 0 ? (
            <ZoneVisitChart data={zoneVisits} />
          ) : (
            <div
              className="flex h-[220px] items-center justify-center rounded-xl border border-dashed text-center text-xs font-medium"
              style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
            >
              Chưa có dữ liệu lượt thăm theo vùng
            </div>
          )}
        </Card>
      </div>

      {/* ── Avg duration + summary ── */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Avg duration area chart */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Thời gian ở lại trung bình
              </h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Đơn vị: phút / ngày
              </p>
            </div>
            <div className="flex items-center gap-2 text-2xl font-black" style={{ color: "var(--text-primary)" }}>
              {stats.avg_duration_minutes}
              <span className="text-sm font-normal" style={{ color: "var(--text-muted)" }}>phút</span>
              <TrendBadge value={stats.duration_change} />
            </div>
          </div>
          <AvgDurationChart data={points} />
        </Card>

        {/* Summary table */}
        <Card>
          <div className="mb-3">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Tóm tắt kỳ này
            </h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              So sánh với kỳ trước cùng độ dài
            </p>
          </div>

          <div className="space-y-3">
            {[
              {
                label: "Tổng lượt khách",
                curr: stats.total_customers,
                prev: prevPoints.reduce((s, p) => s + p.total, 0),
                change: stats.total_change,
                color: "text-indigo-500",
              },
              {
                label: "Khách mới",
                curr: stats.new_customers,
                prev: prevPoints.reduce((s, p) => s + p.new_customers, 0),
                change: stats.new_change,
                color: "text-emerald-500",
              },
              {
                label: "Khách quay lại",
                curr: stats.returning_customers,
                prev: prevPoints.reduce((s, p) => s + p.returning, 0),
                change: stats.returning_change,
                color: "text-amber-500",
              },
              {
                label: "Thời gian TB",
                curr: stats.avg_duration_minutes,
                prev: Math.round(prevPoints.reduce((s, p) => s + p.avg_duration, 0) / prevPoints.length),
                change: stats.duration_change,
                color: "text-sky-500",
                unit: " ph",
              },
            ].map((row) => (
              <div
                key={row.label}
                className="flex items-center justify-between rounded-xl px-4 py-2.5"
                style={{ background: "var(--bg-surface-2)" }}
              >
                <div className="flex items-center gap-2">
                  <span className={`text-lg font-black tabular-nums ${row.color}`}>
                    {row.curr.toLocaleString()}{row.unit ?? ""}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {row.label}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    KT: {row.prev.toLocaleString()}{row.unit ?? ""}
                  </span>
                  <TrendBadge value={row.change} />
                </div>
              </div>
            ))}
          </div>

          {/* Returning rate progress */}
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-muted)" }}>Tỷ lệ khách quay lại</span>
              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                {stats.total_customers > 0
                  ? Math.round((stats.returning_customers / stats.total_customers) * 100)
                  : 0}%
              </span>
            </div>
            <div
              className="h-2 overflow-hidden rounded-full"
              style={{ background: "var(--bg-surface-3, var(--bg-surface-2))" }}
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all duration-700"
                style={{
                  width: `${stats.total_customers > 0
                    ? Math.round((stats.returning_customers / stats.total_customers) * 100)
                    : 0}%`,
                }}
              />
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
