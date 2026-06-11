"use client";

import {
  CustomerFilterParams,
  CustomerStatus,
  CustomerGender,
} from "@/types/customer.type";
import Input from "@/components/ui/Input";
import { Search, X } from "lucide-react";

interface CustomerFilterProps {
  params: CustomerFilterParams;
  onChange: (params: Partial<CustomerFilterParams>) => void;
  onReset: () => void;
}

const statusOptions: { value: CustomerStatus | ""; label: string }[] = [
  { value: "", label: "Tất cả trạng thái" },
  { value: "active", label: "Đang hoạt động" },
  { value: "inactive", label: "Ngừng hoạt động" },
];

const genderOptions: { value: CustomerGender | ""; label: string }[] = [
  { value: "", label: "Tất cả giới tính" },
  { value: "male", label: "Nam" },
  { value: "female", label: "Nữ" },
  { value: "other", label: "Khác" },
];

export default function CustomerFilter({
  params,
  onChange,
  onReset,
}: CustomerFilterProps) {
  const hasFilter = !!params.search || !!params.status || !!params.gender;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* Search */}
      <div className="min-w-[220px] flex-1">
        <Input
          placeholder="Tìm theo tên, SĐT, mã KH..."
          value={params.search ?? ""}
          onChange={(e) => onChange({ search: e.target.value, page: 1 })}
          leftIcon={<Search className="h-4 w-4" />}
        />
      </div>

      {/* Status filter */}
      <div>
        <select
          value={params.status ?? ""}
          onChange={(e) =>
            onChange({
              status: e.target.value as CustomerStatus | "",
              page: 1,
            })
          }
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          aria-label="Lọc trạng thái"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Gender filter */}
      <div>
        <select
          value={params.gender ?? ""}
          onChange={(e) =>
            onChange({
              gender: e.target.value as CustomerGender | "",
              page: 1,
            })
          }
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          aria-label="Lọc giới tính"
        >
          {genderOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Reset */}
      {hasFilter && (
        <button
          type="button"
          onClick={onReset}
          className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700/50"
        >
          <X className="h-4 w-4" />
          Xóa bộ lọc
        </button>
      )}
    </div>
  );
}
