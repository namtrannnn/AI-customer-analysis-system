"use client";

import { useState, useRef } from "react";
import { CustomerCreatePayload } from "@/types/customer.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import {
  customerCreateSchema,
  customerUpdateSchema,
} from "@/validations/customer.schema";
interface CustomerFormProps {
  initialValues?: Partial<CustomerCreatePayload>;
  onSubmit: (payload: CustomerCreatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
  showStatus?: boolean;
}

type FormErrors = Partial<Record<keyof CustomerCreatePayload, string>>;

export default function CustomerForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Lưu",
  showStatus = true,
}: CustomerFormProps) {
  const [values, setValues] = useState<CustomerCreatePayload>({
    full_name: initialValues.full_name ?? "",
    phone: initialValues.phone ?? "",
    email: initialValues.email ?? "",
    gender: initialValues.gender ?? "male",
    status: initialValues.status ?? "active",
    note: initialValues.note ?? "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  function validate(): boolean {
    const schema = showStatus ? customerUpdateSchema : customerCreateSchema;

    const result = schema.safeParse(values);

    if (result.success) {
      setErrors({});
      return true;
    }

    const errs: FormErrors = {};

    for (const issue of result.error.issues) {
      const field = issue.path[0] as keyof CustomerCreatePayload;

      if (field && !errs[field]) {
        errs[field] = issue.message;
      }
    }

    setErrors(errs);
    return false;
  }
  const set =
    (field: keyof CustomerCreatePayload) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >,
    ) => {
      setValues((prev) => ({
        ...prev,
        [field]: e.target.value,
      }));

      if (errors[field]) {
        setErrors((prev) => ({
          ...prev,
          [field]: undefined,
        }));
      }
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!validate()) return;

    setLoading(true);

    try {
      const payload: CustomerCreatePayload = {
        full_name: values.full_name.trim(),
        phone: values.phone?.trim() || undefined,
        email: values.email?.trim() || undefined,
        note: values.note?.trim() || undefined,
        gender: values.gender ?? "male",
      };

      // Chỉ gửi status khi form edit bật showStatus
      if (showStatus) {
        payload.status = values.status ?? "active";
      }

      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      noValidate
      className="space-y-4"
    >
      <Input
        label="Họ và tên"
        placeholder="Nguyễn Văn A"
        value={values.full_name}
        onChange={set("full_name")}
        error={errors.full_name}
        required
        autoFocus
      />

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

      <div
        className={`grid gap-4 ${showStatus ? "grid-cols-2" : "grid-cols-1"}`}
      >
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Giới tính <span className="text-red-500">*</span>
          </label>

          <select
            value={values.gender ?? "male"}
            onChange={set("gender")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          >
            <option value="male">Nam</option>
            <option value="female">Nữ</option>
            <option value="other">Khác</option>
          </select>
        </div>

        {showStatus && (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Trạng thái <span className="text-red-500">*</span>
            </label>

            <select
              value={values.status ?? "active"}
              onChange={set("status")}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
            >
              <option value="active">Đang hoạt động</option>
              <option value="inactive">Ngừng hoạt động</option>
            </select>
          </div>
        )}
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Ghi chú
        </label>

        <textarea
          value={values.note ?? ""}
          onChange={set("note")}
          rows={3}
          placeholder="Ghi chú về khách hàng..."
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:placeholder-slate-500"
        />
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={loading}
        >
          Hủy
        </Button>

        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
