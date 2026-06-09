"use client";

import { useState, useEffect } from "react";
import type { UserCreatePayload, UserUpdatePayload } from "@/types/user.type";
import type { Role } from "@/types/role.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getRoles } from "@/services/role.service";
import { validateUserCreate, type UserFormErrors } from "@/validations/user.schema";

interface UserFormProps {
  mode: "create" | "edit";
  initialValues?: Partial<UserCreatePayload>;
  initialRoleIds?: number[];
  onSubmit: (payload: UserCreatePayload | UserUpdatePayload, roleIds: number[]) => Promise<void>;
  onCancel: () => void;
}

export default function UserForm({
  mode,
  initialValues = {},
  initialRoleIds = [],
  onSubmit,
  onCancel,
}: UserFormProps) {
  const [values, setValues] = useState<UserCreatePayload>({
    full_name: initialValues.full_name ?? "",
    username: initialValues.username ?? "",
    email: initialValues.email ?? "",
    phone: initialValues.phone ?? "",
    password: "",
    status: initialValues.status ?? "active",
  });

  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>(initialRoleIds);
  const [roles, setRoles] = useState<Role[]>([]);
  const [errors, setErrors] = useState<UserFormErrors>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getRoles({ limit: 100 }).then((r) => setRoles(r.data));
  }, []);

  const set =
    (field: keyof UserCreatePayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setValues((prev) => ({ ...prev, [field]: e.target.value }));
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
    };

  function toggleRole(roleId: number) {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId) ? prev.filter((id) => id !== roleId) : [...prev, roleId]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (mode === "create") {
      const errs = validateUserCreate(values);
      if (Object.keys(errs).length > 0) {
        setErrors(errs);
        return;
      }
    }

    setLoading(true);
    try {
      const payload =
        mode === "edit"
          ? ({
              full_name: values.full_name,
              email: values.email?.trim() || undefined,
              phone: values.phone?.trim() || undefined,
              status: values.status,
            } as UserUpdatePayload)
          : {
              ...values,
              email: values.email?.trim() || undefined,
              phone: values.phone?.trim() || undefined,
            };
      await onSubmit(payload, selectedRoleIds);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Họ và tên"
          value={values.full_name}
          onChange={set("full_name")}
          error={errors.full_name}
          required
          autoFocus
        />
        <Input
          label="Tên đăng nhập"
          value={values.username}
          onChange={set("username")}
          error={errors.username}
          required
          disabled={mode === "edit"}
          hint={mode === "edit" ? "Không thể thay đổi" : undefined}
        />
      </div>

      {mode === "create" && (
        <Input
          label="Mật khẩu"
          type="password"
          value={values.password}
          onChange={set("password")}
          error={errors.password}
          required
          placeholder="Tối thiểu 6 ký tự"
        />
      )}

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Email"
          type="email"
          value={values.email ?? ""}
          onChange={set("email")}
          error={errors.email}
          placeholder="example@company.com"
        />
        <Input
          label="Số điện thoại"
          value={values.phone ?? ""}
          onChange={set("phone")}
          error={errors.phone}
          placeholder="0901234567"
          inputMode="tel"
        />
      </div>

      {/* Status */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Trạng thái <span className="text-red-500">*</span>
        </label>
        <select
          value={values.status ?? "active"}
          onChange={set("status")}
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm text-slate-900 dark:text-slate-200 dark:bg-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        >
          <option value="active">Hoạt động</option>
          <option value="inactive">Ngừng hoạt động</option>
          <option value="locked">Khóa tài khoản</option>
        </select>
      </div>

      {/* Role assignment */}
      {roles.length > 0 && (
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Nhóm quyền
          </label>
          <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 dark:border-slate-600 p-3">
            {roles.map((r) => (
              <label
                key={r.id}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition ${
                  selectedRoleIds.includes(r.id)
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                    : "border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedRoleIds.includes(r.id)}
                  onChange={() => toggleRole(r.id)}
                  className="sr-only"
                />
                <span
                  className={`h-3.5 w-3.5 flex-shrink-0 rounded border ${
                    selectedRoleIds.includes(r.id)
                      ? "border-blue-500 bg-blue-500"
                      : "border-slate-300 dark:border-slate-600"
                  }`}
                >
                  {selectedRoleIds.includes(r.id) && (
                    <svg className="h-3.5 w-3.5 text-white" viewBox="0 0 12 12" fill="currentColor">
                      <path d="M10 3L5 8.5 2 5.5" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                    </svg>
                  )}
                </span>
                {r.role_name}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
          Hủy
        </Button>
        <Button type="submit" loading={loading}>
          {mode === "create" ? "Thêm người dùng" : "Lưu thay đổi"}
        </Button>
      </div>
    </form>
  );
}
