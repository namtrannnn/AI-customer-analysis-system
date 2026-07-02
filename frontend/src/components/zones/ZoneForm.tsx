"use client";

import { useState } from "react";
import type { ZoneCreatePayload, ZoneType, Point } from "@/types/zone.type";
import { ZONE_TYPE_LABELS, ZONE_COLORS } from "@/types/zone.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";

interface ZoneFormProps {
  initialValues?: Partial<ZoneCreatePayload>;
  polygon: Point[];
  onSubmit: (payload: ZoneCreatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

export default function ZoneForm({
  initialValues = {},
  polygon,
  onSubmit,
  onCancel,
  submitLabel = "Lưu vùng",
}: ZoneFormProps) {
  const [name, setName] = useState(initialValues.zone_name ?? "");
  const [type, setType] = useState<ZoneType>(initialValues.zone_type ?? "other");
  const [desc, setDesc] = useState(initialValues.description ?? "");
  const [color, setColor] = useState(initialValues.color ?? ZONE_COLORS[0]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Tên vùng không được để trống"); return; }
    if (polygon.length < 3) { setError("Vui lòng vẽ vùng theo dõi trên ảnh trước"); return; }

    setLoading(true);
    try {
      await onSubmit({ zone_name: name.trim(), zone_type: type, description: desc.trim() || undefined, polygon, color });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Tên vùng"
        placeholder="VD: Khu trưng bày A"
        value={name}
        onChange={(e) => { setName(e.target.value); setError(""); }}
        error={error || undefined}
        required
        autoFocus
      />

      {/* Type */}
      <div>
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Loại vùng
        </label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as ZoneType)}
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20 [background:var(--bg-surface)] [border-color:var(--border)] [color:var(--text-primary)]"
        >
          {(Object.entries(ZONE_TYPE_LABELS) as [ZoneType, string][]).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Color picker */}
      <div>
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Màu vùng
        </label>
        <div className="flex flex-wrap gap-2">
          {ZONE_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setColor(c)}
              className={`h-8 w-8 rounded-full ring-offset-2 transition-transform hover:scale-110 ${color === c ? "ring-2 ring-blue-500" : ""}`}
              style={{ backgroundColor: c }}
              title={c}
            />
          ))}
          <input
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="h-8 w-8 cursor-pointer rounded-full border-0"
            title="Chọn màu khác"
          />
        </div>
      </div>

      {/* Desc */}
      <div>
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Mô tả
        </label>
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={2}
          placeholder="Mô tả về vùng này..."
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20 [background:var(--bg-surface)] [border-color:var(--border)] [color:var(--text-primary)] placeholder:text-[color:var(--text-muted)]"
        />
      </div>

      {/* Polygon status */}
      <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
        polygon.length >= 3
          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
          : "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
      }`}>
        <div className={`h-2 w-2 rounded-full ${polygon.length >= 3 ? "bg-emerald-500" : "bg-amber-500"}`} />
        {polygon.length >= 3
          ? `Đã vẽ vùng — ${polygon.length} điểm`
          : "Chưa vẽ vùng — vẽ polygon trên ảnh trước"}
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>Hủy</Button>
        <Button type="submit" loading={loading}>{submitLabel}</Button>
      </div>
    </form>
  );
}
