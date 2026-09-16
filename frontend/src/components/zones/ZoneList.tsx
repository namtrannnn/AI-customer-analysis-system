"use client";

import type { StoreZone } from "@/types/zone.type";
import { ZONE_TYPE_LABELS } from "@/types/zone.type";
import { formatDuration } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Pencil, Trash2, MapPin, Users } from "lucide-react";

// Mock occupancy — khi có camera thật thay bằng WebSocket data
// TODO: thay bằng data realtime từ camera pipeline
const MOCK_OCCUPANCY: Record<string, number> = {
  // zone_name → số người đang có mặt
  // Sẽ được populate từ camera realtime
};

function getOccupancy(zoneName: string): number | null {
  // Mock: random 0-5 người cho vài zone để demo
  // Khi có cam: lookup từ WebSocket data
  const seed = zoneName.charCodeAt(0) % 6;
  return seed > 2 ? seed - 2 : 0; // 0-3 người
}

interface ZoneListProps {
  zones: StoreZone[];
  selectedId?: number | null;
  onSelect?: (zone: StoreZone) => void;
  onEdit: (zone: StoreZone) => void;
  onDelete: (zone: StoreZone) => void;
  showOccupancy?: boolean; // mặc định false, bật khi có camera
}

export default function ZoneList({
  zones,
  selectedId,
  onSelect,
  onEdit,
  onDelete,
  showOccupancy = true,
}: ZoneListProps) {
  if (zones.length === 0) {
    return (
      <EmptyState
        title="Chưa có vùng nào"
        description="Vẽ polygon trên ảnh để tạo vùng theo dõi đầu tiên."
        icon={<MapPin className="mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />}
      />
    );
  }

  return (
    <div className="space-y-2">
      {zones.map((zone) => {
        const isSelected = zone.id === selectedId;
        const occupancy = showOccupancy ? getOccupancy(zone.zone_name) : null;

        return (
          <div
            key={zone.id}
            onClick={() => onSelect?.(zone)}
            className={`group flex cursor-pointer items-start justify-between gap-3 rounded-xl border p-3 transition-all ${
              isSelected
                ? "border-blue-500/50 bg-blue-50 dark:bg-blue-900/20"
                : "border-transparent hover:border-[var(--border)] hover:bg-[var(--bg-surface-2)]"
            }`}
          >
            <div className="flex items-start gap-3 min-w-0 flex-1">
              {/* Color dot */}
              <div
                className="mt-0.5 h-4 w-4 shrink-0 rounded-full ring-2 ring-white shadow-sm dark:ring-slate-800"
                style={{ backgroundColor: zone.color }}
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">
                    {zone.zone_name}
                  </p>
                  {/* Occupancy badge */}
                  {occupancy !== null && (
                    <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold shrink-0 ${
                      occupancy > 0
                        ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"
                        : "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500"
                    }`}>
                      <Users className="h-2.5 w-2.5" />
                      {occupancy}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {ZONE_TYPE_LABELS[zone.zone_type]} · {zone.polygon.length} điểm
                </p>

                <div className="mt-1.5 flex flex-wrap gap-2">
                  <span className="text-[11px] text-slate-400 dark:text-slate-500">
                    {zone.total_visits} lượt ghé
                  </span>
                  {zone.avg_duration_seconds != null && (
                    <span className="text-[11px] text-slate-400 dark:text-slate-500">
                      TB {formatDuration(zone.avg_duration_seconds)}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="text-slate-450 hover:bg-slate-100 dark:hover:bg-slate-800 dark:text-slate-400"
                onClick={(e) => { e.stopPropagation(); onEdit(zone); }}
                title="Chỉnh sửa"
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                onClick={(e) => { e.stopPropagation(); onDelete(zone); }}
                title="Xóa"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
