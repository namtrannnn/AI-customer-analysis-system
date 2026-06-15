"use client";

import {
  CustomerFilterParams,
  CustomerStatus,
  CustomerGender,
} from "@/types/customer.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
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
        onChange={(value) =>
          onChange({
            status: value,
            page: 1,
          })
        }
      />

      <Select<CustomerGender | "">
        value={params.gender ?? ""}
        options={genderOptions}
        ariaLabel="Lọc giới tính"
        onChange={(value) =>
          onChange({
            gender: value,
            page: 1,
          })
        }
      />

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
