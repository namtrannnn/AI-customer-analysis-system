"use client";

import { useState } from "react";
import { Upload, ShieldCheck, Search } from "lucide-react";
import type { VideoAnalysisResult, DetectedPerson } from "@/types/video.type";
import { formatDurationVideo } from "@/services/video.service";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import StatCard from "@/components/common/StatCard";
import CustomerSummaryStats from "@/components/common/CustomerSummaryStats";
import type { SelectOption } from "@/components/ui/Select";

interface VideoAnalysisResultProps {
  result: VideoAnalysisResult;
  onReset: () => void;
}

// ─── Confidence bar ───────────────────────────────────────────────────────────
function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 85
      ? "from-emerald-500 to-teal-500"
      : pct >= 65
        ? "from-blue-500 to-indigo-500"
        : "from-amber-500 to-orange-500";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs font-semibold text-slate-700 dark:text-slate-200">
        {pct}%
      </span>
    </div>
  );
}

// ─── Person row ───────────────────────────────────────────────────────────────
function PersonRow({
  person,
  index,
}: {
  person: DetectedPerson;
  index: number;
}) {
  const isIdentified = person.person_type === "identified";

  return (
    <tr className="group transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-700/30">
      <td className="px-4 py-3 text-xs text-slate-400 dark:text-slate-200">
        {index}
      </td>

      <td className="px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded-lg bg-slate-200 dark:bg-slate-700">
            {person.thumbnail_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={person.thumbnail_url}
                alt={person.anonymous_id}
                className="h-full w-full object-cover"
              />
            )}
          </div>
          <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
            {person.anonymous_id}
          </span>
        </div>
      </td>

      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isIdentified
              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
              : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200"
          }`}
        >
          <div
            className={`h-1.5 w-1.5 rounded-full ${isIdentified ? "bg-blue-500" : "bg-slate-400"}`}
          />
          {isIdentified ? "Định danh" : "Ẩn danh"}
        </span>
      </td>

      <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-200">
        {person.zone ?? "—"}
      </td>

      <td className="px-4 py-3">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-200">
          {person.first_detected_at}
        </span>
      </td>

      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <div className="flex gap-0.5">
            {Array.from({ length: Math.min(person.appearances, 8) }).map(
              (_, i) => (
                <div
                  key={i}
                  className="h-3 w-1 rounded-sm bg-violet-400 dark:bg-violet-500"
                />
              ),
            )}
          </div>
          <span className="text-xs text-slate-600 dark:text-slate-200">
            {person.appearances}x
          </span>
        </div>
      </td>

      <td className="w-36 px-4 py-3">
        <ConfidenceBar value={person.confidence} />
      </td>
    </tr>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function VideoAnalysisResultComponent({
  result,
  onReset,
}: VideoAnalysisResultProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<
    "all" | "identified" | "anonymous"
  >("all");

  const filterOptions: SelectOption<"all" | "identified" | "anonymous">[] = [
    { value: "all", label: "Tất cả" },
    { value: "identified", label: "Đã định danh" },
    { value: "anonymous", label: "Ẩn danh" },
  ];

  const { stats, detected_persons } = result;

  const filtered = detected_persons.filter((p) => {
    const matchSearch =
      !searchTerm ||
      p.anonymous_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.zone?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchType = filterType === "all" || p.person_type === filterType;
    return matchSearch && matchType;
  });

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Phân tích hoàn tất
          </div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {result.video_name}
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-200">
            Xử lý trong {(stats.processing_time_ms / 1000).toFixed(1)}s · Thời
            lượng video {formatDurationVideo(result.duration)}
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={onReset}
          icon={<Upload className="h-4 w-4" />}
        >
          Upload video mới
        </Button>
      </div>

      {/* ── Stat cards ── */}
      <CustomerSummaryStats
        stats={{
          total_customers: stats.total_customers,
          new_customers: stats.new_customers,
          returning_customers: stats.returning_customers,
        }}
        extraCard={
          <StatCard
            label="Độ chính xác TB"
            value={`${Math.round(stats.avg_confidence * 100)}%`}
            sub="AI confidence score"
            gradient="from-amber-500 to-orange-500"
            icon={<ShieldCheck className="h-5 w-5 text-white" />}
          />
        }
      />

      {/* ── Detected persons table ── */}
      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
        {/* Table toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Danh sách khách phát hiện
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-200">
              {filtered.length}
            </span>
          </h3>

          <div className="flex items-center gap-2">
            <Input
              placeholder="Tìm kiếm..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              leftIcon={<Search className="h-4 w-4" />}
            />
            <Select
              value={filterType}
              options={filterOptions}
              onChange={setFilterType}
              ariaLabel="Lọc loại khách"
              className="min-w-[140px]"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:border-slate-700 dark:text-slate-200">
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">ID / Mã KH</th>
                <th className="px-4 py-2.5">Loại</th>
                <th className="px-4 py-2.5">Khu vực</th>
                <th className="px-4 py-2.5">Thời điểm</th>
                <th className="px-4 py-2.5">Lần xuất hiện</th>
                <th className="px-4 py-2.5">Độ chính xác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
              {filtered.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="py-12 text-center text-sm text-slate-400"
                  >
                    Không tìm thấy kết quả
                  </td>
                </tr>
              ) : (
                filtered.map((person, idx) => (
                  <PersonRow key={person.id} person={person} index={idx + 1} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
