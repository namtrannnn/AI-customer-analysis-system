"use client";

import type { MovementTrack, StoreZone } from "@/types/zone.type";
import { ZONE_TYPE_LABELS } from "@/types/zone.type";
import { formatDateTime, formatDuration } from "@/utils/formatDate";
import { X, MapPin, Clock, BarChart2 } from "lucide-react";

interface TrackDetailPopupProps {
  track: MovementTrack;
  zones: StoreZone[];
  onClose: () => void;
}

export default function TrackDetailPopup({ track, zones, onClose }: TrackDetailPopupProps) {
  const zoneMap = Object.fromEntries(zones.map((z) => [z.id, z]));

  const visitedZones = track.zones_visited
    .map((id) => zoneMap[id])
    .filter(Boolean);

  return (
    <div
      className="absolute right-4 top-4 z-30 w-72 overflow-hidden rounded-2xl border shadow-2xl"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border)",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="h-3 w-3 rounded-full shadow-sm"
            style={{ backgroundColor: track.color }}
          />
          <span className="font-mono text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            {track.anonymous_id}
          </span>
        </div>
        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-3 p-4">
        {/* Time info */}
        <div className="grid grid-cols-2 gap-2">
          <InfoCard
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Vào"
            value={formatDateTime(track.entry_time).split(" ")[1] ?? "—"}
          />
          <InfoCard
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Ra"
            value={track.exit_time ? (formatDateTime(track.exit_time).split(" ")[1] ?? "—") : "Chưa rời"}
          />
          <InfoCard
            icon={<BarChart2 className="h-3.5 w-3.5" />}
            label="Thời gian"
            value={formatDuration(track.duration_seconds)}
          />
          <InfoCard
            icon={<MapPin className="h-3.5 w-3.5" />}
            label="Điểm đi"
            value={`${track.points.length} bước`}
          />
        </div>

        {/* Zones visited */}
        {visitedZones.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Vùng đã ghé ({visitedZones.length})
            </p>
            <div className="space-y-1.5">
              {visitedZones.map((zone) => (
                <div
                  key={zone.id}
                  className="flex items-center gap-2 rounded-lg px-2.5 py-1.5"
                  style={{ background: "var(--bg-surface-2)" }}
                >
                  <div
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: zone.color }}
                  />
                  <span className="flex-1 truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                    {zone.zone_name}
                  </span>
                  <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {ZONE_TYPE_LABELS[zone.zone_type]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Route visualization (mini) */}
        <div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
            Hành trình
          </p>
          <div className="flex items-center gap-1 flex-wrap">
            {track.zones_visited.map((zid, i) => {
              const z = zoneMap[zid];
              if (!z) return null;
              return (
                <div key={i} className="flex items-center gap-1">
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                    style={{ backgroundColor: z.color }}
                  >
                    {z.zone_name}
                  </span>
                  {i < track.zones_visited.length - 1 && (
                    <span className="text-slate-400 dark:text-slate-600">→</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div
      className="flex flex-col gap-0.5 rounded-lg p-2.5"
      style={{ background: "var(--bg-surface-2)" }}
    >
      <div className="flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
        {icon}
        <span className="text-[10px]">{label}</span>
      </div>
      <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
        {value}
      </span>
    </div>
  );
}
