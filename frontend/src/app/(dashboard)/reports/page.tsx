"use client";

import { useState } from "react";
import {
  FileDown, FileSpreadsheet, FileText,
  Loader2, CheckCircle2, AlertTriangle,
  Calendar, BarChart3, Users, Clock,
  ShoppingBag, TrendingUp, Info,
} from "lucide-react";
import { getExportUrl } from "@/services/statistics.service";

// ─── Helpers ──────────────────────────────────────────────────────────────────
function today() {
  return new Date().toISOString().split("T")[0];
}
function daysAgo(n: number) {
  return new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
}

const QUICK_RANGES = [
  { label: "7 ngày qua",   start: daysAgo(7),  end: today() },
  { label: "30 ngày qua",  start: daysAgo(30), end: today() },
  { label: "90 ngày qua",  start: daysAgo(90), end: today() },
];

// ─── Report type config ────────────────────────────────────────────────────────
const REPORT_TYPES = [
  {
    id: "summary",
    label: "Báo cáo tổng hợp",
    desc: "Bao gồm tất cả: lượt khách, doanh thu, đơn hàng, thời gian lưu trú — tổng quan toàn diện nhất",
    icon: TrendingUp,
    color: "from-rose-500 to-pink-600",
    fields: ["Tổng lượt khách", "Khách mới & quay lại", "Doanh thu", "Đơn hàng", "Thời gian lưu trú", "Phân nhóm khách"],
    badge: "Khuyến nghị",
  },
  {
    id: "activity",
    label: "Báo cáo hoạt động",
    desc: "Tổng hợp lượt khách, khách mới, quay lại và thời gian lưu trú theo ngày",
    icon: BarChart3,
    color: "from-sky-500 to-blue-600",
    fields: ["Tổng lượt khách", "Khách mới", "Khách quay lại", "Thời gian lưu trú TB"],
    badge: null,
  },
  {
    id: "customer",
    label: "Báo cáo khách hàng",
    desc: "Danh sách khách hàng, lịch sử ghé thăm và phân loại theo nhóm",
    icon: Users,
    color: "from-violet-500 to-purple-600",
    fields: ["Danh sách khách hàng", "Lịch sử ghé thăm", "Phân nhóm AI"],
    badge: null,
  },
  {
    id: "revenue",
    label: "Báo cáo doanh thu",
    desc: "Thống kê đơn hàng, doanh thu và tỷ lệ chuyển đổi theo khoảng thời gian",
    icon: ShoppingBag,
    color: "from-emerald-500 to-teal-600",
    fields: ["Tổng đơn hàng", "Tổng doanh thu", "Tỷ lệ chuyển đổi", "Doanh thu theo ngày"],
    badge: null,
  },
];

type ExportState = "idle" | "loading" | "success" | "error";

// ─── Report Card ──────────────────────────────────────────────────────────────
function ReportCard({
  report,
  selected,
  onClick,
}: {
  report: (typeof REPORT_TYPES)[0];
  selected: boolean;
  onClick: () => void;
}) {
  const Icon = report.icon;
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-emerald-500 ring-2 ring-emerald-500/20 dark:border-emerald-400"
          : ""
      }`}
      style={{
        background: "var(--bg-surface)",
        borderColor: selected ? undefined : "var(--border)",
      }}
    >
      <div className="flex items-start gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${report.color} shadow-md`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              {report.label}
            </p>
            {report.badge && (
              <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-600 dark:bg-rose-500/20 dark:text-rose-400">
                {report.badge}
              </span>
            )}
            {selected && <CheckCircle2 className="h-4 w-4 text-emerald-500 ml-auto" />}
          </div>
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {report.desc}
          </p>
          <div className="mt-2 flex flex-wrap gap-1">
            {report.fields.map((f) => (
              <span
                key={f}
                className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                style={{ background: "var(--bg-surface-2)", color: "var(--text-muted)" }}
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      </div>
    </button>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function ReportsPage() {
  const [selectedType, setSelectedType] = useState("summary");
  const [startDate, setStartDate] = useState(daysAgo(30));
  const [endDate, setEndDate] = useState(today());
  const [excelState, setExcelState] = useState<ExportState>("idle");
  const [pdfState, setPdfState] = useState<ExportState>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  function validate(): string | null {
    if (!startDate || !endDate) return "Vui lòng chọn đầy đủ khoảng ngày";
    if (startDate > endDate) return "Ngày bắt đầu không thể sau ngày kết thúc";
    const diff = (new Date(endDate).getTime() - new Date(startDate).getTime()) / (1000 * 60 * 60 * 24);
    if (diff > 365) return "Khoảng thời gian không được vượt quá 365 ngày";
    return null;
  }

  async function handleExcelExport() {
    const err = validate();
    if (err) { setErrorMsg(err); return; }
    setErrorMsg(null);
    setExcelState("loading");
    try {
      // Dùng CSV export hiện có — khi BE xong RPT-02 thì đổi sang /api/reports/export/excel
      const url = getExportUrl({ start_date: startDate, end_date: endDate });
      const link = document.createElement("a");
      link.href = url;
      link.download = `store_report_${startDate}_${endDate}.xlsx`;
      link.click();
      setExcelState("success");
      setTimeout(() => setExcelState("idle"), 3000);
    } catch {
      setExcelState("error");
      setErrorMsg("Xuất Excel thất bại. Vui lòng thử lại.");
      setTimeout(() => setExcelState("idle"), 3000);
    }
  }

  async function handlePdfExport() {
    const err = validate();
    if (err) { setErrorMsg(err); return; }
    setErrorMsg(null);
    setPdfState("loading");
    // TODO: gọi /api/reports/export/pdf khi BE hoàn thiện RPT-03
    await new Promise((r) => setTimeout(r, 800));
    setPdfState("idle");
    setErrorMsg("⚙️ Tính năng xuất PDF đang được phát triển. Vui lòng dùng Excel.");
  }

  const fileName = startDate && endDate
    ? `store_report_${startDate}_${endDate}`
    : "store_report";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
          <FileDown className="h-3 w-3" />
          Xuất báo cáo
        </div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          Báo cáo
        </h1>
        <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
          Xuất báo cáo hoạt động cửa hàng theo khoảng thời gian tùy chọn.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Left: Chọn loại báo cáo + cấu hình */}
        <div className="space-y-5">
          {/* Loại báo cáo */}
          <div
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="mb-4 text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              1. Chọn loại báo cáo
            </h2>
            <div className="space-y-3">
              {REPORT_TYPES.map((r) => (
                <ReportCard
                  key={r.id}
                  report={r}
                  selected={selectedType === r.id}
                  onClick={() => setSelectedType(r.id)}
                />
              ))}
            </div>
          </div>

          {/* Khoảng ngày */}
          <div
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="mb-4 text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              2. Chọn khoảng thời gian
            </h2>

            {/* Quick ranges */}
            <div className="mb-4 flex flex-wrap gap-2">
              {QUICK_RANGES.map((q) => (
                <button
                  key={q.label}
                  onClick={() => { setStartDate(q.start); setEndDate(q.end); setErrorMsg(null); }}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    startDate === q.start && endDate === q.end
                      ? "bg-emerald-600 text-white"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                  style={startDate === q.start && endDate === q.end ? {} : {
                    background: "var(--bg-surface-2)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {q.label}
                </button>
              ))}
            </div>

            {/* Custom date range */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                  <Calendar className="h-3.5 w-3.5" />
                  Từ ngày
                </label>
                <input
                  type="date"
                  value={startDate}
                  max={endDate}
                  onChange={(e) => { setStartDate(e.target.value); setErrorMsg(null); }}
                  className="h-10 w-full rounded-xl border px-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--bg-surface-2)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>
              <div>
                <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                  <Calendar className="h-3.5 w-3.5" />
                  Đến ngày
                </label>
                <input
                  type="date"
                  value={endDate}
                  min={startDate}
                  max={today()}
                  onChange={(e) => { setEndDate(e.target.value); setErrorMsg(null); }}
                  className="h-10 w-full rounded-xl border px-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--bg-surface-2)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>
            </div>

            {/* Duration hint */}
            {startDate && endDate && startDate <= endDate && (
              <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                Khoảng:{" "}
                <span className="font-semibold" style={{ color: "var(--text-secondary)" }}>
                  {Math.round((new Date(endDate).getTime() - new Date(startDate).getTime()) / (1000 * 60 * 60 * 24) + 1)} ngày
                </span>
              </p>
            )}
          </div>
        </div>

        {/* Right: Export panel */}
        <div className="space-y-4">
          {/* Preview */}
          <div
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="mb-4 text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              3. Xuất báo cáo
            </h2>

            {/* Summary */}
            <div
              className="mb-4 rounded-xl p-4 space-y-2"
              style={{ background: "var(--bg-surface-2)" }}
            >
              <div className="flex justify-between text-xs">
                <span style={{ color: "var(--text-muted)" }}>Loại báo cáo</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {REPORT_TYPES.find((r) => r.id === selectedType)?.label}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span style={{ color: "var(--text-muted)" }}>Từ ngày</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {startDate || "—"}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span style={{ color: "var(--text-muted)" }}>Đến ngày</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {endDate || "—"}
                </span>
              </div>
              <div className="border-t pt-2" style={{ borderColor: "var(--border)" }}>
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>Tên file:</p>
                <p className="mt-0.5 break-all font-mono text-[11px] font-semibold" style={{ color: "var(--text-secondary)" }}>
                  {fileName}.xlsx / .pdf
                </p>
              </div>
            </div>

            {/* Error */}
            {errorMsg && (
              <div className={`mb-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-xs font-semibold ${
                errorMsg.startsWith("⚙️")
                  ? "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
                  : "bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400"
              }`}>
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {errorMsg}
              </div>
            )}

            {/* Export buttons */}
            <div className="space-y-2.5">
              <button
                onClick={handleExcelExport}
                disabled={excelState === "loading" || pdfState === "loading"}
                className="flex w-full items-center justify-center gap-2.5 rounded-xl py-3 text-sm font-bold text-white shadow-md transition hover:opacity-90 disabled:opacity-60"
                style={{ background: "linear-gradient(135deg, #16a34a, #15803d)" }}
              >
                {excelState === "loading" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : excelState === "success" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <FileSpreadsheet className="h-4 w-4" />
                )}
                {excelState === "loading" ? "Đang tạo file..." :
                 excelState === "success" ? "Đã tải xuống!" : "Xuất Excel (.xlsx)"}
              </button>

              <button
                onClick={handlePdfExport}
                disabled={excelState === "loading" || pdfState === "loading"}
                className="flex w-full items-center justify-center gap-2.5 rounded-xl py-3 text-sm font-bold text-white shadow-md transition hover:opacity-90 disabled:opacity-60"
                style={{ background: "linear-gradient(135deg, #dc2626, #b91c1c)" }}
              >
                {pdfState === "loading" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : pdfState === "success" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <FileText className="h-4 w-4" />
                )}
                {pdfState === "loading" ? "Đang tạo file..." :
                 pdfState === "success" ? "Đã tải xuống!" : "Xuất PDF (.pdf)"}
              </button>
            </div>
          </div>

          {/* Info box */}
          <div
            className="rounded-2xl p-4"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <div className="flex items-start gap-2.5">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-500" />
              <div className="text-xs space-y-1" style={{ color: "var(--text-muted)" }}>
                <p className="font-semibold" style={{ color: "var(--text-secondary)" }}>Lưu ý:</p>
                <p>• File Excel có thể mở bằng Microsoft Excel hoặc LibreOffice</p>
                <p>• Xuất PDF hỗ trợ tiếng Việt đầy đủ</p>
                <p>• Khoảng thời gian tối đa 365 ngày</p>
                <p>• Dữ liệu lấy từ thống kê đã được đồng bộ</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
