"use client";

import Link from "next/link";
import type { MovementTrack, StoreZone } from "@/types/zone.type";
import { ZONE_TYPE_LABELS } from "@/types/zone.type";
import { formatDateTime, formatDuration } from "@/utils/formatDate";
import { X, MapPin, Clock, BarChart2, User } from "lucide-react";

interface TrackDetailPopupProps {
  track: MovementTrack;
  zones: StoreZone[];
  onClose: () => void;
}

export default function TrackDetailPopup({
  track,
  zones,
  onClose,
}: TrackDetailPopupProps) {
  const zoneMap = Object.fromEntries(zones.map((z) => [z.id, z]));

  const visitedZones = track.zones_visited
    .map((id) => zoneMap[id])
    .filter(Boolean);

  const isIdentified = !!track.customer_id;

  return (
    <div
      className="absolute right-4 top-4 z-30 w-80 max-h-[calc(100%-32px)] overflow-hidden rounded-2xl border shadow-2xl flex flex-col bg-white/95 dark:bg-slate-900/95 backdrop-blur-md"
      style={{ borderColor: "var(--border)" }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-4 py-3"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-3">
          {/* Avatar Thumbnail */}
          <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-full border bg-slate-100 dark:bg-slate-800 dark:border-slate-700 flex items-center justify-center">
            {track.customer_avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={track.customer_avatar}
                alt="Avatar"
                className="h-full w-full object-cover"
              />
            ) : (
              <User className="h-5 w-5 text-slate-400" />
            )}
          </div>

          <div className="min-w-0">
            {isIdentified ? (
              <Link
                href={`/customers/${track.customer_id}`}
                className="block truncate text-sm font-bold text-indigo-650 hover:text-indigo-750 dark:text-indigo-400 dark:hover:text-indigo-300 hover:underline transition cursor-pointer"
                title="Xem chi tiết khách hàng"
              >
                {track.customer_name}
              </Link>
            ) : (
              <span className="block truncate text-sm font-bold text-slate-800 dark:text-slate-200">
                {track.anonymous_id}
              </span>
            )}
            <span className="block font-mono text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
              {isIdentified ? `ID: ${track.anonymous_id}` : "Khách ẩn danh"}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
          title="Đóng"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Info Grid */}
        <div className="grid grid-cols-2 gap-2">
          <InfoCard
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Vào"
            value={formatDateTime(track.entry_time).split(" ")[1] ?? "—"}
          />
          <InfoCard
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Ra"
            value={
              track.exit_time
                ? (formatDateTime(track.exit_time).split(" ")[1] ?? "—")
                : "Chưa rời"
            }
          />
          <div className="col-span-2">
            <InfoCard
              icon={<BarChart2 className="h-3.5 w-3.5" />}
              label="Thời lượng"
              value={formatDuration(track.duration_seconds)}
            />
          </div>
        </div>

        {/* Zones Visited */}
        {visitedZones.length > 0 && (
          <div>
            <p
              className="mb-2 text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}
            >
              Vùng đã ghé ({visitedZones.length})
            </p>
            <div className="space-y-1.5">
              {visitedZones.map((zone, idx) => (
                <div
                  key={`${zone.id}-${idx}`}
                  className="flex items-center gap-2 rounded-lg px-2.5 py-1.5"
                  style={{ background: "var(--bg-surface-2)" }}
                >
                  <div
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: zone.color }}
                  />
                  <span
                    className="flex-1 truncate text-xs font-semibold text-slate-700 dark:text-slate-300"
                  >
                    {zone.zone_name}
                  </span>
                  <span
                    className="text-[10px] bg-white dark:bg-slate-805 px-1.5 py-0.5 rounded border dark:border-slate-700 text-slate-450 dark:text-slate-400"
                  >
                    {ZONE_TYPE_LABELS[zone.zone_type]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Journey Timeline */}
        {track.zones_visited.length > 0 && (
          <div>
            <p
              className="mb-2 text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}
            >
              Hành trình di chuyển
            </p>
            <div className="relative border-l border-slate-200 dark:border-slate-700 pl-4 py-1.5 space-y-4">
              {track.zones_visited.map((zid, i) => {
                const z = zoneMap[zid];
                if (!z) return null;
                return (
                  <div key={i} className="relative flex items-center gap-2.5">
                    {/* Node Dot */}
                    <div
                      className="absolute -left-[21px] flex h-2.5 w-2.5 items-center justify-center rounded-full border bg-white dark:bg-slate-900"
                      style={{ borderColor: z.color }}
                    >
                      <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: z.color }} />
                    </div>

                    <span className="text-xs font-medium text-slate-800 dark:text-slate-200 bg-slate-100/70 dark:bg-slate-800/70 px-2 py-1 rounded">
                      {z.zone_name}
                    </span>
                    {i < track.zones_visited.length - 1 && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        di chuyển đến
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div
      className="flex flex-col gap-0.5 rounded-lg p-2.5"
      style={{ background: "var(--bg-surface-2)" }}
    >
      <div
        className="flex items-center gap-1"
        style={{ color: "var(--text-muted)" }}
      >
        {icon}
        <span className="text-[10px]">{label}</span>
      </div>
      <span
        className="text-xs font-semibold text-slate-800 dark:text-slate-200"
      >
        {value}
      </span>
    </div>
  );
}
