"use client";

import {
  CustomerFilterParams,
  CustomerStatus,
  CustomerGender,
} from "@/types/customer.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import { Search, X, MapPin } from "lucide-react";

// Import MOCK_PRESENCE để biết IDs đang có mặt
// Khi có cam: đây sẽ là data từ WebSocket
import { PRESENCE_IDS } from "@/components/customers/CustomerTable";

interface CustomerFilterProps {
  params: CustomerFilterParams;
  onChange: (params: Partial<CustomerFilterParams>) => void;
  onReset: () => void;
  onFilterPresence?: () => void; // callback khi click "Đang ở đây"
  isFilteringPresence?: boolean;
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
  onFilterPresence,
  isFilteringPresence = false,
}: CustomerFilterProps) {
  const hasFilter = !!params.search || !!params.status || !!params.gender || isFilteringPresence;
  const presenceCount = PRESENCE_IDS.length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-[240px] flex-1">
        <Input
          placeholder="Tìm theo tên, SĐT, mã KH..."
          value={params.search ?? ""}
          onChange={(e) => onChange({ search: e.target.value, page: 1 })}
          leftIcon={<Search className="h-4 w-4" />}
        />
      </div>

      <Select<CustomerStatus | "">
        value={params.status ?? ""}
        options={statusOptions}
        ariaLabel="Lọc trạng thái"
        onChange={(value) => onChange({ status: value, page: 1 })}
      />

      <Select<CustomerGender | "">
        value={params.gender ?? ""}
        options={genderOptions}
        ariaLabel="Lọc giới tính"
        onChange={(value) => onChange({ gender: value, page: 1 })}
      />

      {/* Filter "Đang ở đây" */}
      {presenceCount > 0 && (
        <button
          type="button"
          onClick={onFilterPresence}
          className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-bold transition ${
            isFilteringPresence
              ? "border-emerald-500 bg-emerald-500 text-white"
              : "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
          <MapPin className="h-3.5 w-3.5" />
          Đang ở đây ({presenceCount})
        </button>
      )}

      {hasFilter && (
        <Button
          type="button"
          variant="secondary"
          size="base"
          icon={<X className="h-4 w-4" />}
          onClick={onReset}
          className="h-10 rounded-xl"
        >
          Xóa bộ lọc
        </Button>
      )}
    </div>
  );
}
