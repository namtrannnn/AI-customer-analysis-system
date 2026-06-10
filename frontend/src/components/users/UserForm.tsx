"use client";

import { useState, useEffect } from "react";
import type { UserCreatePayload, UserUpdatePayload } from "@/types/user.type";
import type { Role } from "@/types/role.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getRoles } from "@/services/role.service";
import {
  validateUserCreate,
  type UserFormErrors,
} from "@/validations/user.schema";
import { Check, ShieldCheck, Loader2 } from "lucide-react";

interface UserFormProps {
  mode: "create" | "edit";
  initialValues?: Partial<UserCreatePayload>;
  initialRoleIds?: number[];
  onSubmit: (
    payload: UserCreatePayload | UserUpdatePayload,
    roleIds: number[],
  ) => Promise<void>;
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

  const [selectedRoleIds, setSelectedRoleIds] =
    useState<number[]>(initialRoleIds);

  const [roles, setRoles] = useState<Role[]>([]);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);

  const [errors, setErrors] = useState<UserFormErrors>({});
  const [loading, setLoading] = useState(false);

  // Sync lại form khi mở edit user khác
  useEffect(() => {
    setValues({
      full_name: initialValues.full_name ?? "",
      username: initialValues.username ?? "",
      email: initialValues.email ?? "",
      phone: initialValues.phone ?? "",
      password: "",
      status: initialValues.status ?? "active",
    });

    setSelectedRoleIds(initialRoleIds);
    setErrors({});
  }, [
    initialValues.full_name,
    initialValues.username,
    initialValues.email,
    initialValues.phone,
    initialValues.status,
    initialRoleIds,
  ]);

  useEffect(() => {
    async function fetchRoles() {
      setRoleLoading(true);
      setRoleError(null);

      try {
        const res = await getRoles({ limit: 100 });
        setRoles(res.data);
      } catch (e: unknown) {
        setRoleError(
          e instanceof Error ? e.message : "Không tải được danh sách quyền",
        );
      } finally {
        setRoleLoading(false);
      }
    }

    fetchRoles();
  }, []);

  const set =
    (field: keyof UserCreatePayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setValues((prev) => ({ ...prev, [field]: e.target.value }));

      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
    };

  function toggleRole(roleId: number) {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId],
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
              full_name: values.full_name.trim(),
              email: values.email?.trim() || undefined,
              phone: values.phone?.trim() || undefined,
              status: values.status,
            } as UserUpdatePayload)
          : ({
              ...values,
              full_name: values.full_name.trim(),
              username: values.username.trim(),
              email: values.email?.trim() || undefined,
              phone: values.phone?.trim() || undefined,
            } as UserCreatePayload);

      await onSubmit(payload, selectedRoleIds);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Họ và tên"
          value={values.full_name}
          onChange={set("full_name")}
          error={errors.full_name}
          required
          autoFocus
          placeholder="Nguyễn Văn A"
        />

        <Input
          label="Tên đăng nhập"
          value={values.username}
          onChange={set("username")}
          error={errors.username}
          required
          disabled={mode === "edit"}
          hint={
            mode === "edit" ? "Không thể thay đổi tên đăng nhập" : undefined
          }
          placeholder="nguyenvana"
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

      <div className="grid gap-4 md:grid-cols-2">
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
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:focus:ring-blue-900/40"
        >
          <option value="active">Hoạt động</option>
          <option value="inactive">Ngừng hoạt động</option>
          <option value="locked">Khóa tài khoản</option>
        </select>
      </div>

      {/* Role assignment */}
      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
            <ShieldCheck className="h-4 w-4 text-blue-500" />
            Nhóm quyền
          </label>

          {selectedRoleIds.length > 0 && (
            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              Đã chọn {selectedRoleIds.length}
            </span>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-600 dark:bg-slate-900/30">
          {roleLoading ? (
            <div className="flex items-center gap-2 py-3 text-sm text-slate-500 dark:text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Đang tải nhóm quyền...
            </div>
          ) : roleError ? (
            <p className="py-2 text-sm text-red-500">{roleError}</p>
          ) : roles.length === 0 ? (
            <p className="py-2 text-sm text-slate-500 dark:text-slate-400">
              Chưa có nhóm quyền nào.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {roles.map((role) => {
                const checked = selectedRoleIds.includes(role.id);

                return (
                  <label
                    key={role.id}
                    className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                      checked
                        ? "border-blue-500 bg-blue-50 text-blue-700 shadow-sm dark:bg-blue-900/30 dark:text-blue-300"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400 dark:hover:border-slate-500"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRole(role.id)}
                      className="sr-only"
                    />

                    <span
                      className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border ${
                        checked
                          ? "border-blue-500 bg-blue-500 text-white"
                          : "border-slate-300 dark:border-slate-500"
                      }`}
                    >
                      {checked && <Check className="h-3 w-3" />}
                    </span>

                    <span className="font-medium">{role.role_name}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-slate-700">
        <Button
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={loading}
        >
          Hủy
        </Button>

        <Button type="submit" loading={loading}>
          {mode === "create" ? "Thêm người dùng" : "Lưu thay đổi"}
        </Button>
      </div>
    </form>
  );
}
