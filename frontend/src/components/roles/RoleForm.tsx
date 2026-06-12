"use client";

import { useState, useEffect } from "react";
import type { RoleCreatePayload } from "@/types/role.type";
import type { Permission } from "@/types/permission.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getPermissionsByModule } from "@/services/role.service";
import { validateRole, type RoleFormErrors } from "@/validations/role.schema";

interface RoleFormProps {
  initialValues?: Partial<RoleCreatePayload>;
  initialPermissionIds?: number[];
  onSubmit: (payload: RoleCreatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
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
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
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
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Mô tả
        </label>

        <textarea
          value={values.description ?? ""}
          onChange={set("description")}
          rows={2}
          placeholder="Mô tả về nhóm quyền này..."
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none placeholder-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:placeholder-slate-500"
        />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Phân quyền{" "}
            <span className="ml-1 text-xs text-slate-400 dark:text-slate-500">
              ({selectedIds.length} đã chọn)
            </span>
          </label>

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
              className="text-xs text-blue-600 hover:underline"
            >
              {selectedIds.length > 0 ? "Bỏ chọn tất cả" : "Chọn tất cả"}
            </button>
          )}
        </div>

        {permissionLoading ? (
          <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500 dark:border-slate-600 dark:text-slate-400">
            Đang tải danh sách quyền...
          </div>
        ) : Object.keys(permsByModule).length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-slate-600 dark:text-slate-400">
            Chưa có danh sách quyền. Bạn vẫn có thể tạo nhóm quyền không gán
            permission.
          </div>
        ) : (
          <div className="space-y-3 rounded-lg border border-slate-200 p-3 dark:border-slate-600">
            {Object.entries(permsByModule).map(([module, perms]) => {
              const allChecked = perms.every((permission) =>
                selectedIds.includes(permission.id),
              );
              const someChecked = perms.some((permission) =>
                selectedIds.includes(permission.id),
              );

              return (
                <div key={module}>
                  <label className="mb-1.5 flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                    <input
                      type="checkbox"
                      checked={allChecked}
                      ref={(el) => {
                        if (el) {
                          el.indeterminate = someChecked && !allChecked;
                        }
                      }}
                      onChange={(e) => toggleModule(perms, e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 dark:border-slate-600"
                    />
                    {module}
                  </label>

                  <div className="ml-5 flex flex-wrap gap-2">
                    {perms.map((permission) => {
                      const checked = selectedIds.includes(permission.id);

                      return (
                        <label
                          key={permission.id}
                          className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition ${
                            checked
                              ? "border-blue-400 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                              : "border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-600 dark:text-slate-400 dark:hover:border-slate-500"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => togglePermission(permission.id)}
                            className="sr-only"
                          />
                          {permission.permission_name}
                        </label>
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
