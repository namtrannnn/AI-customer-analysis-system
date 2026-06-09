"use client";

import { useState, useRef } from "react";
import { CustomerCreatePayload, CustomerGender, CustomerStatus } from "@/types/customer.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";

interface CustomerFormProps {
  initialValues?: Partial<CustomerCreatePayload>;
  onSubmit: (payload: CustomerCreatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

type FormErrors = Partial<Record<keyof CustomerCreatePayload, string>>;

export default function CustomerForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Lưu",
}: CustomerFormProps) {
  const [values, setValues] = useState<CustomerCreatePayload>({
    full_name: initialValues.full_name ?? "",
    phone: initialValues.phone ?? "",
    email: initialValues.email ?? "",
    gender: initialValues.gender ?? undefined,
    status: initialValues.status ?? "active",
    note: initialValues.note ?? "",
    avatar_url: initialValues.avatar_url ?? "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  function validate(): boolean {
    const errs: FormErrors = {};

    if (!values.full_name?.trim()) {
      errs.full_name = "Tên khách hàng không được để trống";
    }

    if (values.phone && !/^(0[3-9]\d{8})$/.test(values.phone)) {
      errs.phone = "Số điện thoại không hợp lệ (VD: 0901234567)";
    }

    if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      errs.email = "Email không hợp lệ";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  const set = (field: keyof CustomerCreatePayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      setValues((prev) => ({ ...prev, [field]: e.target.value }));
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      // Strip empty strings → undefined
      const payload: CustomerCreatePayload = {
        ...values,
        phone: values.phone?.trim() || undefined,
        email: values.email?.trim() || undefined,
        note: values.note?.trim() || undefined,
        avatar_url: values.avatar_url?.trim() || undefined,
      };
      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate className="space-y-4">
      {/* Full name */}
      <Input
        label="Họ và tên"
        placeholder="Nguyễn Văn A"
        value={values.full_name}
        onChange={set("full_name")}
        error={errors.full_name}
        required
        autoFocus
      />

      {/* Phone + Email */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Số điện thoại"
          placeholder="0901234567"
          value={values.phone ?? ""}
          onChange={set("phone")}
          error={errors.phone}
          inputMode="tel"
        />
        <Input
          label="Email"
          placeholder="example@email.com"
          type="email"
          value={values.email ?? ""}
          onChange={set("email")}
          error={errors.email}
        />
      </div>

      {/* Gender + Status */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Giới tính
          </label>
          <select
            value={values.gender ?? ""}
            onChange={set("gender")}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm text-slate-900 dark:text-slate-200 dark:bg-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value="">Không xác định</option>
            <option value="male">Nam</option>
            <option value="female">Nữ</option>
            <option value="other">Khác</option>
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Trạng thái <span className="text-red-500">*</span>
          </label>
          <select
            value={values.status ?? "active"}
            onChange={set("status")}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm text-slate-900 dark:text-slate-200 dark:bg-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value="active">Đang hoạt động</option>
            <option value="inactive">Ngừng hoạt động</option>
            <option value="vip">VIP</option>
          </select>
        </div>
      </div>

      {/* Note */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Ghi chú
        </label>
        <textarea
          value={values.note ?? ""}
          onChange={set("note")}
          rows={3}
          placeholder="Ghi chú về khách hàng..."
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm text-slate-900 dark:text-slate-200 dark:bg-slate-700 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
          Hủy
        </Button>
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
