"use client";

import { useState, useEffect } from "react";
import type { RoleCreatePayload } from "@/types/role.type";
import type { Permission } from "@/types/permission.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getPermissionsByModule } from "@/services/role.service";
import { validateRole, type RoleFormErrors } from "@/validations/role.schema";
import { Check, Loader2, ShieldCheck } from "lucide-react";

interface RoleFormProps {
  initialValues?: Partial<RoleCreatePayload>;
  initialPermissionIds?: number[];
  onSubmit: (payload: RoleCreatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

function CustomCheck({ checked }: { checked: boolean }) {
  return (
    <span
      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-md border transition-all ${
        checked
          ? "border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-600/20"
          : "border-slate-300 bg-white text-transparent dark:border-slate-600 dark:bg-slate-900"
      }`}
    >
      <Check className="h-3 w-3" />
    </span>
  );
}

function ModuleCheck({
  checked,
  indeterminate,
}: {
  checked: boolean;
  indeterminate: boolean;
}) {
  return (
    <span
      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-md border transition-all ${
        checked || indeterminate
          ? "border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-600/20"
          : "border-slate-300 bg-white text-transparent dark:border-slate-600 dark:bg-slate-900"
      }`}
    >
      {indeterminate && !checked ? (
        <span className="h-0.5 w-2 rounded-full bg-white" />
      ) : (
        <Check className="h-3 w-3" />
      )}
    </span>
  );
}

export default function RoleForm({
  initialValues = {},
  initialPermissionIds = [],
  onSubmit,
  onCancel,
  submitLabel = "Lưu",
}: RoleFormProps) {
  const [values, setValues] = useState<RoleCreatePayload>({
    role_code: initialValues.role_code ?? "",
    role_name: initialValues.role_name ?? "",
    description: initialValues.description ?? "",
    permission_ids: initialPermissionIds,
  });

  const [permsByModule, setPermsByModule] = useState<
    Record<string, Permission[]>
  >({});
  const [errors, setErrors] = useState<RoleFormErrors>({});
  const [loading, setLoading] = useState(false);
  const [permissionLoading, setPermissionLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function fetchPermissions() {
      setPermissionLoading(true);

      try {
        const data = await getPermissionsByModule();
        if (mounted) setPermsByModule(data);
      } finally {
        if (mounted) setPermissionLoading(false);
      }
    }

    fetchPermissions();

    return () => {
      mounted = false;
    };
  }, []);

  const selectedIds = values.permission_ids ?? [];

  function togglePermission(id: number) {
    setValues((prev) => {
      const currentIds = prev.permission_ids ?? [];

      return {
        ...prev,
        permission_ids: currentIds.includes(id)
          ? currentIds.filter((permissionId) => permissionId !== id)
          : [...currentIds, id],
      };
    });
  }

  function toggleModule(perms: Permission[], checked: boolean) {
    const ids = perms.map((permission) => permission.id);

    setValues((prev) => {
      const currentIds = prev.permission_ids ?? [];

      return {
        ...prev,
        permission_ids: checked
          ? [...new Set([...currentIds, ...ids])]
          : currentIds.filter((id) => !ids.includes(id)),
      };
    });
  }

  const set =
    (field: keyof RoleCreatePayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const val =
        field === "role_code" ? e.target.value.toLowerCase() : e.target.value;

      setValues((prev) => ({ ...prev, [field]: val }));

      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const submitValues: RoleCreatePayload = {
      role_code: values.role_code.trim().toLowerCase(),
      role_name: values.role_name.trim(),
      description: values.description?.trim() || null,
      permission_ids: values.permission_ids ?? [],
    };

    const errs = validateRole(submitValues);

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setLoading(true);

    try {
      await onSubmit(submitValues);
    } finally {
      setLoading(false);
    }
  }

  const allPermissionIds = Object.values(permsByModule)
    .flat()
    .map((permission) => permission.id);

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Mã nhóm quyền"
          placeholder="VD: admin, staff_01"
          value={values.role_code}
          onChange={set("role_code")}
          error={errors.role_code}
          required
          autoFocus
        />

        <Input
          label="Tên nhóm quyền"
          placeholder="VD: Quản trị viên"
          value={values.role_name}
          onChange={set("role_name")}
          error={errors.role_name}
          required
        />
      </div>

      <div>
        <label
          className="mb-1.5 block text-sm font-medium"
          style={{ color: "var(--text-secondary)" }}
        >
          Mô tả
        </label>

        <textarea
          value={values.description ?? ""}
          onChange={set("description")}
          rows={2}
          placeholder="Mô tả về nhóm quyền này..."
          className="
            w-full resize-none rounded-xl border px-3 py-2 text-sm outline-none transition-all duration-150
            placeholder-[color:var(--text-muted)]
            [background:var(--bg-surface)]
            [border-color:var(--border)]
            [color:var(--text-primary)]
            focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
            disabled:cursor-not-allowed disabled:opacity-50
          "
        />
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <label
              className="text-sm font-semibold"
              style={{ color: "var(--text-secondary)" }}
            >
              Phân quyền
            </label>

            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
              Đã chọn{" "}
              <span className="font-bold text-blue-600 dark:text-blue-300">
                {selectedIds.length}
              </span>{" "}
              quyền
            </p>
          </div>

          {allPermissionIds.length > 0 && (
            <button
              type="button"
              onClick={() =>
                setValues((prev) => ({
                  ...prev,
                  permission_ids:
                    selectedIds.length > 0 ? [] : allPermissionIds,
                }))
              }
              className="rounded-xl px-3 py-1.5 text-xs font-bold text-blue-600 transition hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-500/10"
            >
              {selectedIds.length > 0 ? "Bỏ chọn tất cả" : "Chọn tất cả"}
            </button>
          )}
        </div>

        {permissionLoading ? (
          <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Đang tải danh sách quyền...
          </div>
        ) : Object.keys(permsByModule).length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-400">
            Chưa có danh sách quyền. Bạn vẫn có thể tạo nhóm quyền không gán
            permission.
          </div>
        ) : (
          <div className="max-h-[420px] space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-950/30">
            {Object.entries(permsByModule).map(([module, perms]) => {
              const allChecked = perms.every((permission) =>
                selectedIds.includes(permission.id),
              );
              const someChecked = perms.some((permission) =>
                selectedIds.includes(permission.id),
              );
              const indeterminate = someChecked && !allChecked;

              return (
                <div
                  key={module}
                  className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
                >
                  <button
                    type="button"
                    onClick={() => toggleModule(perms, !allChecked)}
                    className="mb-3 flex w-full items-center justify-between gap-3 rounded-xl px-2 py-1.5 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800/70"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <ModuleCheck
                        checked={allChecked}
                        indeterminate={indeterminate}
                      />

                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                        <ShieldCheck className="h-4 w-4" />
                      </span>

                      <span>
                        <span className="block truncate text-sm font-bold text-slate-800 dark:text-slate-100">
                          {module}
                        </span>
                        <span className="block text-xs text-slate-400 dark:text-slate-500">
                          {
                            perms.filter((permission) =>
                              selectedIds.includes(permission.id),
                            ).length
                          }
                          /{perms.length} quyền đã chọn
                        </span>
                      </span>
                    </span>
                  </button>

                  <div className="flex flex-wrap gap-2 pl-1">
                    {perms.map((permission) => {
                      const checked = selectedIds.includes(permission.id);

                      return (
                        <button
                          key={permission.id}
                          type="button"
                          onClick={() => togglePermission(permission.id)}
                          className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all ${
                            checked
                              ? "border-blue-200 bg-blue-50 text-blue-700 shadow-sm dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300"
                              : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50/60 hover:text-blue-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:border-blue-500/30 dark:hover:bg-blue-500/10 dark:hover:text-blue-300"
                          }`}
                        >
                          <CustomCheck checked={checked} />
                          <span>{permission.permission_name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
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
