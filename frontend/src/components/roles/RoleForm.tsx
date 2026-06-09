"use client";

import { useState, useEffect } from "react";
import type { RoleCreatePayload } from "@/types/role.type";
import type { Permission } from "@/types/permission.type";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { getPermissionsByModule } from "@/services/permission.service";
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

  const [permsByModule, setPermsByModule] = useState<Record<string, Permission[]>>({});
  const [errors, setErrors] = useState<RoleFormErrors>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getPermissionsByModule().then(setPermsByModule);
  }, []);

  const selectedIds = values.permission_ids ?? [];

  function togglePermission(id: number) {
    setValues((prev) => ({
      ...prev,
      permission_ids: selectedIds.includes(id)
        ? selectedIds.filter((p) => p !== id)
        : [...selectedIds, id],
    }));
  }

  function toggleModule(perms: Permission[], checked: boolean) {
    const ids = perms.map((p) => p.id);
    setValues((prev) => ({
      ...prev,
      permission_ids: checked
        ? [...new Set([...selectedIds, ...ids])]
        : selectedIds.filter((id) => !ids.includes(id)),
    }));
  }

  const set =
    (field: keyof RoleCreatePayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const val = field === "role_code" ? e.target.value.toUpperCase() : e.target.value;
      setValues((prev) => ({ ...prev, [field]: val }));
      if (errors[field as keyof RoleFormErrors])
        setErrors((prev) => ({ ...prev, [field]: undefined }));
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateRole(values);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setLoading(true);
    try {
      await onSubmit({
        ...values,
        description: values.description?.trim() || undefined,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Mã nhóm quyền"
          placeholder="VD: ADMIN, STAFF_01"
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
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">Mô tả</label>
        <textarea
          value={values.description ?? ""}
          onChange={set("description")}
          rows={2}
          placeholder="Mô tả về nhóm quyền này..."
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm text-slate-900 dark:text-slate-200 dark:bg-slate-700 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
      </div>

      {/* Permissions matrix */}
      {Object.keys(permsByModule).length > 0 && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Phân quyền{" "}
              <span className="ml-1 text-xs text-slate-400 dark:text-slate-500">
                ({selectedIds.length} đã chọn)
              </span>
            </label>
            <button
              type="button"
              onClick={() =>
                setValues((prev) => ({
                  ...prev,
                  permission_ids:
                    selectedIds.length > 0
                      ? []
                      : Object.values(permsByModule).flat().map((p) => p.id),
                }))
              }
              className="text-xs text-blue-600 hover:underline"
            >
              {selectedIds.length > 0 ? "Bỏ chọn tất cả" : "Chọn tất cả"}
            </button>
          </div>

          <div className="space-y-3 rounded-lg border border-slate-200 dark:border-slate-600 p-3">
            {Object.entries(permsByModule).map(([module, perms]) => {
              const allChecked = perms.every((p) => selectedIds.includes(p.id));
              const someChecked = perms.some((p) => selectedIds.includes(p.id));

              return (
                <div key={module}>
                  {/* Module header */}
                  <label className="mb-1.5 flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                    <input
                      type="checkbox"
                      checked={allChecked}
                      ref={(el) => {
                        if (el) el.indeterminate = someChecked && !allChecked;
                      }}
                      onChange={(e) => toggleModule(perms, e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-slate-300 dark:border-slate-600 text-blue-600"
                    />
                    {module}
                  </label>
                  {/* Permissions */}
                  <div className="ml-5 flex flex-wrap gap-2">
                    {perms.map((p) => (
                      <label
                        key={p.id}
                        className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition ${
                          selectedIds.includes(p.id)
                            ? "border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                            : "border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(p.id)}
                          onChange={() => togglePermission(p.id)}
                          className="sr-only"
                        />
                        {p.permission_name}
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
