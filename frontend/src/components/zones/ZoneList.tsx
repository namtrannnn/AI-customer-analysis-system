"use client";

import type { StoreZone } from "@/types/zone.type";
import { ZONE_TYPE_LABELS } from "@/types/zone.type";
import { formatDuration } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Pencil, Trash2, MapPin } from "lucide-react";

interface ZoneListProps {
  zones: StoreZone[];
  selectedId?: number | null;
  onSelect?: (zone: StoreZone) => void;
  onEdit: (zone: StoreZone) => void;
  onDelete: (zone: StoreZone) => void;
}

export default function ZoneList({
  zones,
  selectedId,
  onSelect,
  onEdit,
  onDelete,
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
            <div className="flex items-start gap-3">
              {/* Color dot */}
              <div
                className="mt-0.5 h-4 w-4 shrink-0 rounded-full ring-2 ring-white shadow-sm dark:ring-slate-800"
                style={{ backgroundColor: zone.color }}
              />

              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {zone.zone_name}
                </p>
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

            <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <Button
                variant="ghost"
                size="sm"
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
