"use client";

import { useState } from "react";
import type { VideoAnalysisResult, DetectedPerson } from "@/types/video.type";
import { formatDurationVideo } from "@/services/video.service";

interface VideoAnalysisResultProps {
  result: VideoAnalysisResult;
  onReset: () => void;
}

// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, gradient, icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  gradient: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
      <div className={`absolute -right-3 -top-3 h-16 w-16 rounded-full opacity-10 ${gradient}`} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            {value}
          </p>
          {sub && <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-sm`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

// ─── Confidence bar ───────────────────────────────────────────────────────────
function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 85 ? "from-emerald-500 to-teal-500" :
    pct >= 65 ? "from-blue-500 to-indigo-500" :
                "from-amber-500 to-orange-500";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">
        {pct}%
      </span>
    </div>
  );
}

// ─── Person row ───────────────────────────────────────────────────────────────
function PersonRow({ person, index }: { person: DetectedPerson; index: number }) {
  const isIdentified = person.person_type === "identified";

  return (
    <tr className="group transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-700/30">
      <td className="px-4 py-3 text-xs text-slate-400 dark:text-slate-500">{index}</td>

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
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          isIdentified
            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
            : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400"
        }`}>
          <div className={`h-1.5 w-1.5 rounded-full ${isIdentified ? "bg-blue-500" : "bg-slate-400"}`} />
          {isIdentified ? "Định danh" : "Ẩn danh"}
        </span>
      </td>

      <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-400">
        {person.zone ?? "—"}
      </td>

      <td className="px-4 py-3">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-300">
          {person.first_detected_at}
        </span>
      </td>

      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <div className="flex gap-0.5">
            {Array.from({ length: Math.min(person.appearances, 8) }).map((_, i) => (
              <div key={i} className="h-3 w-1 rounded-sm bg-violet-400 dark:bg-violet-500" />
            ))}
          </div>
          <span className="text-xs text-slate-600 dark:text-slate-400">{person.appearances}x</span>
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
  const [filterType, setFilterType] = useState<"all" | "identified" | "anonymous">("all");

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
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Xử lý trong {(stats.processing_time_ms / 1000).toFixed(1)}s ·{" "}
            Thời lượng video {formatDurationVideo(result.duration)}
          </p>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Upload video mới
        </button>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Tổng khách phát hiện"
          value={stats.total_customers}
          gradient="from-violet-500 to-purple-600"
          icon={
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
        <StatCard
          label="Khách mới"
          value={stats.new_customers}
          sub={`${Math.round((stats.new_customers / stats.total_customers) * 100)}% tổng số`}
          gradient="from-emerald-500 to-teal-500"
          icon={
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          }
        />
        <StatCard
          label="Khách quay lại"
          value={stats.returning_customers}
          sub={`${Math.round((stats.returning_customers / stats.total_customers) * 100)}% tổng số`}
          gradient="from-blue-500 to-indigo-500"
          icon={
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          }
        />
        <StatCard
          label="Độ chính xác TB"
          value={`${Math.round(stats.avg_confidence * 100)}%`}
          sub="AI confidence score"
          gradient="from-amber-500 to-orange-500"
          icon={
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          }
        />
      </div>

      {/* ── Detected persons table ── */}
      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
        {/* Table toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Danh sách khách phát hiện
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-400">
              {filtered.length}
            </span>
          </h3>

          <div className="flex items-center gap-2">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
              </svg>
              <input
                type="text"
                placeholder="Tìm kiếm..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-700 outline-none focus:border-violet-400 focus:bg-white focus:ring-2 focus:ring-violet-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:focus:bg-slate-800"
              />
            </div>

            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as typeof filterType)}
              className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              <option value="all">Tất cả</option>
              <option value="identified">Đã định danh</option>
              <option value="anonymous">Ẩn danh</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:border-slate-700 dark:text-slate-500">
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
                  <td colSpan={7} className="py-12 text-center text-sm text-slate-400">
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
