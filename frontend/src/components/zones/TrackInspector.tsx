"use client";

import { useState } from "react";
import type { MovementTrack, StoreZone } from "@/types/zone.type";
import { Activity, Users, Clock, MapPin, HelpCircle } from "lucide-react";

interface TrackInspectorProps {
  tracks: MovementTrack[];
  zones: StoreZone[];
  selectedTrackId?: number | null;
  onSelectTrack?: (track: MovementTrack | null) => void;
}

export default function TrackInspector({
  tracks,
  zones,
  selectedTrackId,
  onSelectTrack,
}: TrackInspectorProps) {
  const [limit, setLimit] = useState(6);

  // Calculate General Statistics
  const totalTracks = tracks.length;
  const uniquePersons = new Set(tracks.map((t) => t.person_profile_id)).size;

  const validTracksForDuration = tracks.filter((t) => t.duration_seconds !== null && t.duration_seconds !== undefined);
  const avgDuration =
    validTracksForDuration.length > 0
      ? validTracksForDuration.reduce((s, t) => s + (t.duration_seconds ?? 0), 0) / validTracksForDuration.length
      : 0;

  const avgMinutes = Math.floor(avgDuration / 60);
  const avgSeconds = Math.round(avgDuration % 60);
  const avgDurationText = avgDuration > 0 ? `${avgMinutes}p ${avgSeconds}s` : "—";

  const visitedZoneIds = new Set(tracks.flatMap((t) => t.zones_visited));
  const visitedZonesCount = visitedZoneIds.size;

  const visibleTracks = tracks.slice(0, limit);

  return (
    <div className="flex h-full flex-col justify-between p-5 bg-white dark:bg-slate-900 overflow-y-auto">
      <div className="space-y-6">
        <div>
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Activity className="h-4.5 w-4.5 text-indigo-500 animate-pulse" />
            Thống kê tổng quan
          </h3>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Dữ liệu tổng hợp từ các hành trình đang lọc.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            icon={<Activity className="h-4 w-4 text-indigo-500" />}
            label="Tổng số Routes"
            value={totalTracks}
          />
          <StatCard
            icon={<Users className="h-4 w-4 text-emerald-500" />}
            label="Tổng số Khách"
            value={uniquePersons}
          />
          <StatCard
            icon={<Clock className="h-4 w-4 text-amber-500" />}
            label="Lưu trú TB"
            value={avgDurationText}
          />
          <StatCard
            icon={<MapPin className="h-4 w-4 text-rose-500" />}
            label="Zone đã ghé"
            value={`${visitedZonesCount}/${zones.length}`}
          />
        </div>

        {/* List of Routes */}
        <div className="space-y-3 pt-5 border-t border-slate-100 dark:border-slate-800">
          <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide">
            Danh sách hành trình ({totalTracks})
          </h4>

          {totalTracks === 0 ? (
            <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-4">
              Không tìm thấy hành trình phù hợp
            </p>
          ) : (
            <div className="space-y-2">
              {visibleTracks.map((t) => {
                const isSelected = t.id === selectedTrackId;
                return (
                  <button
                    key={t.id}
                    onClick={() => onSelectTrack?.(isSelected ? null : t)}
                    className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-left transition ${
                      isSelected
                        ? "border-indigo-500 bg-indigo-50/10 dark:bg-indigo-950/20"
                        : "border-slate-100 dark:border-slate-800/40 hover:bg-slate-50 dark:hover:bg-slate-800/20"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className="h-3 w-3 shrink-0 rounded-full shadow-xs"
                        style={{ backgroundColor: t.color }}
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-700 dark:text-slate-350 truncate">
                          {t.customer_name || t.anonymous_id}
                        </p>
                        <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate mt-0.5">
                          Vào: {t.entry_time ? t.entry_time.split("T")[1]?.substring(0, 5) : "—"}
                        </p>
                      </div>
                    </div>
                    {t.duration_seconds !== null && (
                      <span className="text-[10px] font-medium text-slate-450 dark:text-slate-500 shrink-0">
                        {Math.round(t.duration_seconds / 60)} phút
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {tracks.length > limit && (
            <button
              onClick={() => setLimit((prev) => prev + 6)}
              className="w-full text-center text-xs font-semibold text-indigo-650 hover:text-indigo-755 dark:text-indigo-400 dark:hover:text-indigo-300 py-2 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/10 transition mt-2"
            >
              Xem thêm ({tracks.length - limit} hành trình)
            </button>
          )}
        </div>
      </div>

      {/* User Guide Box */}
      <div className="mt-8 rounded-xl border border-dashed border-slate-200 p-4 text-center dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/20">
        <HelpCircle className="mx-auto h-7 w-7 text-slate-400 dark:text-slate-500" />
        <h4 className="mt-1 text-xs font-semibold text-slate-800 dark:text-slate-200">
          Xem chi tiết hành trình
        </h4>
        <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
          Nhấp vào một route trên bản đồ hoặc trong danh sách trên để xem phân tích chi tiết.
        </p>
      </div>
    </div>
  );
}

// ─── Small helper components ───

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs dark:border-slate-800 dark:bg-slate-800/30">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide">
          {label}
        </span>
      </div>
      <p className="mt-2 text-base font-extrabold text-slate-800 dark:text-slate-100">
        {value}
      </p>
    </div>
  );
}
