/**
 * Trang báo cáo Thống kê khách theo ngày (PB06)
 * Dùng Recharts cho biểu đồ, Lucide cho icon.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  TrendingUp, Users, UserPlus, UserCheck, Clock, ShoppingBag,
  DollarSign, Percent, Calendar, Download, RefreshCw,
  ChevronLeft, ChevronRight, Info, FileSpreadsheet, FileText, Loader2,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

import { formatDuration } from "@/utils/formatDate";
import {
  getDailyStats,
  getStatsSummary,
  syncStats,
  getExportUrl,
  type DailyStatisticItem,
  type DailyStatisticsSummary,
  type StatsFilters,
} from "@/services/statistics.service";

export default function DailyStatsPage() {
  // ─── State ──────────────────────────────────────────────
  const [filters, setFilters] = useState<StatsFilters>({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    end_date: new Date().toISOString().split("T")[0],
    group_by: "day",
  });

  const [summary, setSummary] = useState<DailyStatisticsSummary | null>(null);
  const [dailyList, setDailyList] = useState<DailyStatisticItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const limit = 15;

  // Export state
  const [exportRange, setExportRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    end: new Date().toISOString().split("T")[0],
  });
  const [exportingExcel, setExportingExcel] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // ─── Fetch dữ liệu ──────────────────────────────────────
  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      getStatsSummary(filters),
      getDailyStats(filters, (page - 1) * limit, limit),
    ])
      .then(([summaryData, listData]) => {
        setSummary(summaryData);
        setDailyList(listData);
      })
      .catch((err) => {
        console.error("Lỗi tải thống kê:", err);
        setError("Không thể tải dữ liệu thống kê. Vui lòng kiểm tra kết nối.");
      })
      .finally(() => setLoading(false));
  }, [filters, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── Handlers ───────────────────────────────────────────
  const handleFilterChange = (key: keyof StatsFilters, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value === "" ? undefined : value }));
    setPage(1);
  };

  const handleSync = async () => {
    if (!filters.start_date || !filters.end_date) return;
    setSyncing(true);
    setSyncMessage("");
    try {
      const result = await syncStats(filters.start_date, filters.end_date);
      setSyncMessage(`✅ Đồng bộ thành công ${result.synced_count} ngày`);
      fetchData(); // Reload data
    } catch (err) {
      setSyncMessage("❌ Đồng bộ thất bại. Vui lòng thử lại.");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMessage(""), 4000);
    }
  };

  const handleExport = () => {
    const url = getExportUrl(filters);
    window.open(url, "_blank");
  };

  // Validate export range
  function validateExportRange(): string | null {
    if (!exportRange.start || !exportRange.end) return "Vui lòng chọn đầy đủ ngày bắt đầu và kết thúc";
    if (exportRange.start > exportRange.end) return "Ngày bắt đầu không thể sau ngày kết thúc";
    const start = new Date(exportRange.start);
    const end = new Date(exportRange.end);
    const diffDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays > 365) return "Khoảng thời gian không được vượt quá 365 ngày";
    return null;
  }

  async function handleExportExcel() {
    const err = validateExportRange();
    if (err) { setExportError(err); return; }
    setExportError(null);
    setExportingExcel(true);
    try {
      // Khi BE sẵn sàng: gọi API /api/reports/export/excel?start_date=...&end_date=...
      // Tạm thời dùng CSV export hiện có
      const url = getExportUrl({ start_date: exportRange.start, end_date: exportRange.end });
      const a = document.createElement("a");
      a.href = url;
      a.download = `store_report_${exportRange.start}_${exportRange.end}.xlsx`;
      a.click();
    } catch {
      setExportError("Xuất Excel thất bại. Vui lòng thử lại.");
    } finally {
      setExportingExcel(false);
    }
  }

  async function handleExportPdf() {
    const err = validateExportRange();
    if (err) { setExportError(err); return; }
    setExportError(null);
    setExportingPdf(true);
    try {
      // Khi BE sẵn sàng: gọi API /api/reports/export/pdf?start_date=...&end_date=...
      // TODO: replace với real PDF API khi BE xong
      await new Promise((r) => setTimeout(r, 800)); // simulate
      setExportError("⚙️ Tính năng xuất PDF đang được phát triển. Vui lòng dùng Excel.");
    } finally {
      setExportingPdf(false);
    }
  }

  // ─── KPI Card Component ─────────────────────────────────
  const KpiCard = ({
    icon: Icon, label, value, sub, color,
  }: {
    icon: any; label: string; value: string; sub?: string; color: string;
  }) => (
    <div className="relative overflow-hidden rounded-2xl border border-slate-100 dark:border-slate-700/60 bg-white dark:bg-slate-800 p-5 shadow-2xs group hover:shadow-md transition-shadow">
      <div className={`absolute -right-4 -top-4 h-20 w-20 rounded-full bg-gradient-to-br ${color} opacity-10 group-hover:opacity-20 transition`} />
      <div className="flex items-center gap-3 mb-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${color} shadow-lg`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-extrabold text-slate-800 dark:text-white">{value}</p>
      {sub && <p className="text-[11px] font-semibold text-slate-400 mt-1">{sub}</p>}
    </div>
  );

  // ─── Render ─────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight flex items-center gap-2.5">
            <TrendingUp className="h-7 w-7 text-cyan-500" />
            Thống kê khách hàng
          </h1>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            Báo cáo lượng khách, khách mới, khách quay lại và hiệu suất kinh doanh theo thời gian
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Đang đồng bộ..." : "Đồng bộ dữ liệu"}
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 transition"
          >
            <Download className="h-3.5 w-3.5" />
            Xuất CSV
          </button>
        </div>
      </div>

      {/* Sync message */}
      {syncMessage && (
        <div className="px-4 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-900/30 text-sm font-semibold text-indigo-700 dark:text-indigo-300">
          {syncMessage}
        </div>
      )}

      {/* Bộ lọc */}
      <div className="flex flex-wrap items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <label className="text-xs font-bold text-slate-500 uppercase">Từ</label>
          <input
            type="date"
            value={filters.start_date || ""}
            onChange={(e) => handleFilterChange("start_date", e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-cyan-500/30 outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-slate-500 uppercase">Đến</label>
          <input
            type="date"
            value={filters.end_date || ""}
            onChange={(e) => handleFilterChange("end_date", e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-cyan-500/30 outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-slate-500 uppercase">Nhóm theo</label>
          <select
            value={filters.group_by || "day"}
            onChange={(e) => handleFilterChange("group_by", e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-cyan-500/30 outline-none"
          >
            <option value="day">Theo ngày</option>
            <option value="week">Theo tuần</option>
            <option value="month">Theo tháng</option>
          </select>
        </div>
      </div>

      {/* ── Export Section (RPT-05) ── */}
      <div
        className="rounded-2xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <div className="mb-4 flex items-center gap-2">
          <Download className="h-4 w-4 text-emerald-500" />
          <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            Xuất báo cáo hoạt động cửa hàng
          </h3>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          {/* Date range */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                Từ ngày
              </label>
              <input
                type="date"
                value={exportRange.start}
                max={exportRange.end}
                onChange={(e) => { setExportRange((p) => ({ ...p, start: e.target.value })); setExportError(null); }}
                className="rounded-lg border px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface-2)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                Đến ngày
              </label>
              <input
                type="date"
                value={exportRange.end}
                min={exportRange.start}
                max={new Date().toISOString().split("T")[0]}
                onChange={(e) => { setExportRange((p) => ({ ...p, end: e.target.value })); setExportError(null); }}
                className="rounded-lg border px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface-2)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
          </div>

          {/* Export buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleExportExcel}
              disabled={exportingExcel || exportingPdf}
              className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-60"
            >
              {exportingExcel
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <FileSpreadsheet className="h-4 w-4" />
              }
              {exportingExcel ? "Đang tạo..." : "Xuất Excel"}
            </button>
            <button
              onClick={handleExportPdf}
              disabled={exportingExcel || exportingPdf}
              className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700 disabled:opacity-60"
            >
              {exportingPdf
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <FileText className="h-4 w-4" />
              }
              {exportingPdf ? "Đang tạo..." : "Xuất PDF"}
            </button>
          </div>
        </div>

        {/* Preview filename */}
        {exportRange.start && exportRange.end && (
          <p className="mt-3 text-[11px]" style={{ color: "var(--text-muted)" }}>
            Tên file: <span className="font-mono font-semibold">
              store_report_{exportRange.start}_{exportRange.end}.xlsx / .pdf
            </span>
          </p>
        )}

        {/* Error/info message */}
        {exportError && (
          <div className={`mt-3 rounded-lg px-3 py-2 text-xs font-semibold ${
            exportError.startsWith("⚙️")
              ? "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
              : "bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400"
          }`}>
            {exportError}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-sm font-semibold text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-2xl" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            icon={Users}
            label="Tổng khách"
            value={summary.total_visitors.toLocaleString()}
            sub={`${summary.new_visitors} mới · ${summary.returning_visitors} quay lại`}
            color="from-cyan-500 to-blue-600"
          />
          <KpiCard
            icon={UserPlus}
            label="Tỷ lệ khách mới"
            value={summary.total_visitors > 0 ? `${Math.round((summary.new_visitors / summary.total_visitors) * 100)}%` : "0%"}
            sub={`${summary.new_visitors} / ${summary.total_visitors} khách`}
            color="from-emerald-500 to-teal-600"
          />
          <KpiCard
            icon={Clock}
            label="TB thời gian ở lại"
            value={formatDuration(summary.avg_duration_seconds)}
            sub={`${summary.avg_duration_seconds}s`}
            color="from-violet-500 to-purple-600"
          />
          <KpiCard
            icon={ShoppingBag}
            label="Đơn hàng & Doanh thu"
            value={`${summary.total_orders} đơn`}
            sub={`${summary.total_revenue.toLocaleString()}đ · CR ${summary.avg_conversion_rate}%`}
            color="from-amber-500 to-orange-600"
          />
        </div>
      ) : null}

      {/* Biểu đồ xu hướng (Recharts Line Chart) */}
      <div className="p-6 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2 mb-4">
          <TrendingUp className="h-4 w-4 text-cyan-500" />
          Biến động lượng khách theo thời gian
        </h3>

        {loading ? (
          <div className="h-72 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-xl" />
        ) : !summary || summary.trend.length === 0 ? (
          <div className="h-72 flex items-center justify-center text-xs text-slate-400">
            Không có dữ liệu. Hãy nhấn &quot;Đồng bộ dữ liệu&quot; để bắt đầu tính toán.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={summary.trend.map((t) => ({ ...t, date: t.date.length > 7 ? t.date.slice(5) : t.date }))}>
              <defs>
                <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} width={35} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "none", borderRadius: 10, fontSize: 12, color: "#fff" }}
                labelStyle={{ color: "#94a3b8", fontWeight: 600 }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, fontWeight: 600 }}
                iconType="circle"
                iconSize={8}
              />
              <Line
                type="monotone"
                dataKey="total_visitors"
                name="Tổng khách"
                stroke="#06b6d4"
                strokeWidth={2.5}
                dot={{ r: 3, fill: "#fff", stroke: "#06b6d4", strokeWidth: 2 }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="new_visitors"
                name="Khách mới"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ r: 3, fill: "#fff", stroke: "#10b981", strokeWidth: 2 }}
                strokeDasharray="5 3"
              />
              <Line
                type="monotone"
                dataKey="returning_visitors"
                name="Khách quay lại"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 3, fill: "#fff", stroke: "#8b5cf6", strokeWidth: 2 }}
                strokeDasharray="5 3"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Bảng danh sách chi tiết */}
      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700/60 rounded-2xl overflow-hidden shadow-2xs">
        <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
            <Info className="h-4 w-4 text-cyan-500" />
            Chi tiết thống kê theo ngày
          </h3>
        </div>

        {loading ? (
          <div className="p-6">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-lg mb-2" />
            ))}
          </div>
        ) : dailyList.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-400">
            Chưa có dữ liệu. Hãy nhấn &quot;Đồng bộ dữ liệu&quot; để bắt đầu.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 dark:text-slate-500 bg-slate-50/50 dark:bg-slate-900/30">
                    <th className="px-5 py-3 font-bold">Ngày</th>
                    <th className="px-4 py-3 font-bold text-center">Tổng khách</th>
                    <th className="px-4 py-3 font-bold text-center">Khách mới</th>
                    <th className="px-4 py-3 font-bold text-center">Quay lại</th>
                    <th className="px-4 py-3 font-bold text-center">Đã định danh</th>
                    <th className="px-4 py-3 font-bold text-center">TB thời gian</th>
                    <th className="px-4 py-3 font-bold text-center">Đơn hàng</th>
                    <th className="px-4 py-3 font-bold text-right">Doanh thu</th>
                    <th className="px-4 py-3 font-bold text-center">CR %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                  {dailyList.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-750/30 transition">
                      <td className="px-5 py-3 font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">
                        {row.statistic_date}
                      </td>
                      <td className="px-4 py-3 text-center font-bold text-cyan-600 dark:text-cyan-400">
                        {row.total_visitors}
                      </td>
                      <td className="px-4 py-3 text-center text-emerald-600 dark:text-emerald-400 font-semibold">
                        {row.new_visitors}
                      </td>
                      <td className="px-4 py-3 text-center text-violet-600 dark:text-violet-400 font-semibold">
                        {row.returning_visitors}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-500">
                        {row.identified_visitors}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-500">
                        {formatDuration(row.avg_duration_seconds)}
                      </td>
                      <td className="px-4 py-3 text-center font-semibold text-amber-600 dark:text-amber-400">
                        {row.total_orders}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">
                        {row.total_revenue.toLocaleString()}đ
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          row.conversion_rate > 10
                            ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                            : row.conversion_rate > 0
                            ? "bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400"
                            : "bg-slate-50 text-slate-400 dark:bg-slate-900/30"
                        }`}>
                          {row.conversion_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Phân trang */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 dark:border-slate-700/60">
              <span className="text-xs font-semibold text-slate-400">
                Trang {page}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-50 dark:bg-slate-900/30 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 transition"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={dailyList.length < limit}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-50 dark:bg-slate-900/30 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 transition"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
