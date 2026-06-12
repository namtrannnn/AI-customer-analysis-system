"use client";

import { useState, useEffect, useMemo } from "react";
import type { UserCreatePayload, UserUpdatePayload } from "@/types/user.type";
import type { Role } from "@/types/role.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getRoles } from "@/services/role.service";
import {
  validateUserCreate,
  validateUserUpdate,
  type UserFormErrors,
} from "@/validations/user.schema";
import { Check, ShieldCheck, Loader2 } from "lucide-react";

interface UserFormValues {
  full_name: string;
  email: string;
  phone: string;
  status: "active" | "inactive";
}

interface UserFormProps {
  mode: "create" | "edit";
  initialValues?: Partial<UserFormValues>;
  initialRoleIds?: number[];
  onSubmit: (
    payload: UserCreatePayload | UserUpdatePayload,
    roleIds: number[],
  ) => Promise<void>;
  onCancel: () => void;
}

export default function UserForm({
  mode,
  initialValues,
  initialRoleIds,
  onSubmit,
  onCancel,
}: UserFormProps) {
  const safeInitialValues = useMemo(
    () => ({
      full_name: initialValues?.full_name ?? "",
      email: initialValues?.email ?? "",
      phone: initialValues?.phone ?? "",
      status: initialValues?.status ?? "active",
    }),
    [
      initialValues?.full_name,
      initialValues?.email,
      initialValues?.phone,
      initialValues?.status,
    ],
  );

  const initialRoleKey = useMemo(
    () => (initialRoleIds ?? []).join(","),
    [initialRoleIds],
  );

  const [values, setValues] = useState<UserFormValues>(safeInitialValues);

  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>(
    initialRoleIds ?? [],
  );

  const [roles, setRoles] = useState<Role[]>([]);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);

  const [errors, setErrors] = useState<UserFormErrors>({});
  const [roleErrorText, setRoleErrorText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Chỉ reset form khi đổi user edit hoặc đổi mode, không reset mỗi lần gõ
  useEffect(() => {
    setValues(safeInitialValues);
    setSelectedRoleIds(initialRoleIds ?? []);
    setErrors({});
    setRoleErrorText(null);
  }, [mode, safeInitialValues, initialRoleKey]);

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
    (field: keyof UserFormValues) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setValues((prev) => ({
        ...prev,
        [field]: e.target.value,
      }));

      if (errors[field as keyof UserCreatePayload]) {
        setErrors((prev) => ({
          ...prev,
          [field]: undefined,
        }));
      }
    };

  function selectRole(roleId: number) {
    setSelectedRoleIds([roleId]);
    setRoleErrorText(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const cleanFullName = values.full_name.trim();
    const cleanEmail = values.email.trim() || null;
    const cleanPhone = values.phone.trim() || null;

    if (selectedRoleIds.length === 0) {
      setRoleErrorText("Vui lòng chọn ít nhất 1 nhóm quyền");
      return;
    }

    setRoleErrorText(null);

    if (mode === "create") {
      const createPayload: UserCreatePayload = {
        full_name: cleanFullName,
        email: cleanEmail,
        phone: cleanPhone,
        role_ids: selectedRoleIds,
      };

      const errs = validateUserCreate(createPayload);

      if (Object.keys(errs).length > 0) {
        setErrors(errs);
        return;
      }

      setLoading(true);

      try {
        await onSubmit(createPayload, selectedRoleIds);
      } finally {
        setLoading(false);
      }

      return;
    }

    const updatePayload: UserUpdatePayload = {
      full_name: cleanFullName,
      email: cleanEmail,
      phone: cleanPhone,
      status: values.status,
      role_ids: selectedRoleIds,
    };

    const errs = validateUserUpdate(updatePayload);

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setErrors({});

    setLoading(true);

    try {
      await onSubmit(updatePayload, selectedRoleIds);
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
          label="Email"
          type="email"
          value={values.email}
          onChange={set("email")}
          error={errors.email}
          placeholder="example@company.com"
        />
      </div>

      <Input
        label="Số điện thoại"
        value={values.phone}
        onChange={set("phone")}
        error={errors.phone}
        placeholder="0901234567"
        inputMode="tel"
      />

      {mode === "edit" && (
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Trạng thái <span className="text-red-500">*</span>
          </label>

          <select
            value={values.status}
            onChange={set("status")}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:focus:ring-blue-900/40"
          >
            <option value="active">Hoạt động</option>
            <option value="inactive">Ngừng hoạt động</option>
          </select>
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
            <ShieldCheck className="h-4 w-4 text-blue-500" />
            Nhóm quyền <span className="text-red-500">*</span>
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
                      type="radio"
                      name="user-role"
                      checked={checked}
                      onChange={() => selectRole(role.id)}
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

        {roleErrorText && (
          <p className="mt-1.5 text-xs text-red-500">{roleErrorText}</p>
        )}
      </div>

      {mode === "create" && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300">
          Hệ thống sẽ tự động sinh tên đăng nhập và mật khẩu tạm thời sau khi
          tạo người dùng.
        </div>
      )}

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
