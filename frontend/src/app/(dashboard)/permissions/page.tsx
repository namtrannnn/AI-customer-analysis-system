"use client";

import { useState, useEffect } from "react";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getRolePermissionMatrix,
  getPermissionsByModule,
  updateRolePermissions,
} from "@/services/permission.service";
import type {
  RolePermissionMatrix,
  PermissionsByModule,
} from "@/types/permission.type";

export default function PermissionsPage() {
  const [matrix, setMatrix] = useState<RolePermissionMatrix[]>([]);
  const [permsByModule, setPermsByModule] = useState<PermissionsByModule>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  // Local editable copy: roleId → Set<permissionId>
  const [localMatrix, setLocalMatrix] = useState<Record<number, Set<number>>>(
    {},
  );

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [mat, perms] = await Promise.all([
          getRolePermissionMatrix(),
          getPermissionsByModule(),
        ]);
        setMatrix(mat);
        setPermsByModule(perms);

        // Init local copy
        const local: Record<number, Set<number>> = {};
        mat.forEach((m) => {
          local[m.role.id] = new Set(m.permission_ids);
        });
        setLocalMatrix(local);
        setDirty(false);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  function toggleCell(roleId: number, permId: number) {
    setLocalMatrix((prev) => {
      const next = { ...prev };
      const set = new Set(next[roleId] ?? []);
      if (set.has(permId)) {
        set.delete(permId);
      } else {
        set.add(permId);
      }
      next[roleId] = set;
      return next;
    });
    setDirty(true);
  }

  function toggleRoleAll(
    roleId: number,
    allPermIds: number[],
    checked: boolean,
  ) {
    setLocalMatrix((prev) => {
      const next = { ...prev };
      const set = new Set(next[roleId] ?? []);
      if (checked) {
        allPermIds.forEach((id) => set.add(id));
      } else {
        allPermIds.forEach((id) => set.delete(id));
      }
      next[roleId] = set;
      return next;
    });
    setDirty(true);
  }

  function togglePermAll(permId: number, checked: boolean) {
    setLocalMatrix((prev) => {
      const next = { ...prev };
      matrix.forEach((m) => {
        const set = new Set(next[m.role.id] ?? []);
        if (checked) set.add(permId);
        else set.delete(permId);
        next[m.role.id] = set;
      });
      return next;
    });
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await Promise.all(
        matrix.map((m) =>
          updateRolePermissions({
            role_id: m.role.id,
            permission_ids: Array.from(localMatrix[m.role.id] ?? []),
          }),
        ),
      );
      setDirty(false);
      showToast("success", "Lưu phân quyền thành công");
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    const local: Record<number, Set<number>> = {};
    matrix.forEach((m) => {
      local[m.role.id] = new Set(m.permission_ids);
    });
    setLocalMatrix(local);
    setDirty(false);
  }

  const allPerms = Object.values(permsByModule).flat();

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Phân quyền
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Gán quyền chức năng cho từng nhóm người dùng.
          </p>
        </div>

        {dirty && (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleReset}
              disabled={saving}
            >
              Hủy thay đổi
            </Button>
            <Button size="sm" loading={saving} onClick={handleSave}>
              Lưu phân quyền
            </Button>
          </div>
        )}
      </div>

      {loading ? (
        <Loading text="Đang tải ma trận phân quyền..." />
      ) : error ? (
        <div className="flex flex-col items-center gap-3 py-20 text-center">
          <p className="text-sm text-red-500">{error}</p>
        </div>
      ) : (
        <div className="rounded-xl bg-white dark:bg-slate-800 shadow-sm dark:shadow-slate-900/50 overflow-hidden">
          {dirty && (
            <div className="flex items-center gap-2 border-b border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30 px-4 py-2.5">
              <svg
                className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Có thay đổi chưa được lưu. Nhấn <strong>Lưu phân quyền</strong>{" "}
                để áp dụng.
              </p>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/50">
                  <th className="sticky left-0 z-10 bg-slate-50 dark:bg-slate-700/50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    Chức năng / Module
                  </th>
                  {matrix.map((m) => {
                    const rolePerms = localMatrix[m.role.id] ?? new Set();
                    const allChecked =
                      allPerms.length > 0 &&
                      allPerms.every((p) => rolePerms.has(p.id));

                    return (
                      <th
                        key={m.role.id}
                        className="min-w-[120px] px-3 py-3 text-center"
                      >
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            {m.role.role_name}
                          </span>
                          <span className="text-xs text-slate-400 dark:text-slate-500">
                            {m.role.role_code}
                          </span>
                          <label className="flex cursor-pointer items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <input
                              type="checkbox"
                              checked={allChecked}
                              onChange={(e) =>
                                toggleRoleAll(
                                  m.role.id,
                                  allPerms.map((p) => p.id),
                                  e.target.checked,
                                )
                              }
                              className="h-3 w-3 rounded border-slate-300 dark:border-slate-600 text-blue-600"
                            />
                            Tất cả
                          </label>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>

              <tbody>
                {Object.entries(permsByModule).map(([module, perms]) => (
                  <>
                    {/* Module header row */}
                    <tr
                      key={`module-${module}`}
                      className="bg-slate-50 dark:bg-slate-700/30"
                    >
                      <td
                        colSpan={matrix.length + 1}
                        className="sticky left-0 border-y border-slate-100 dark:border-slate-700 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
                      >
                        {module}
                      </td>
                    </tr>

                    {/* Permission rows */}
                    {perms.map((perm) => {
                      const allRolesHave = matrix.every((m) =>
                        localMatrix[m.role.id]?.has(perm.id),
                      );

                      return (
                        <tr
                          key={perm.id}
                          className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                        >
                          <td className="sticky left-0 bg-white dark:bg-slate-800 px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-700/40">
                            <div className="flex items-center gap-2">
                              <label className="flex cursor-pointer items-center gap-1.5 text-sm text-slate-700 dark:text-slate-300">
                                <input
                                  type="checkbox"
                                  checked={allRolesHave}
                                  onChange={(e) =>
                                    togglePermAll(perm.id, e.target.checked)
                                  }
                                  className="h-3.5 w-3.5 rounded border-slate-300 dark:border-slate-600 text-blue-600"
                                  title="Áp dụng cho tất cả nhóm"
                                />
                                {perm.permission_name}
                              </label>
                              <code className="rounded bg-slate-100 dark:bg-slate-700 px-1 text-xs text-slate-400 dark:text-slate-500">
                                {perm.permission_code}
                              </code>
                            </div>
                          </td>

                          {matrix.map((m) => {
                            const checked =
                              localMatrix[m.role.id]?.has(perm.id) ?? false;
                            return (
                              <td
                                key={m.role.id}
                                className="px-3 py-2.5 text-center"
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() =>
                                    toggleCell(m.role.id, perm.id)
                                  }
                                  className="h-4 w-4 cursor-pointer rounded border-slate-300 dark:border-slate-600 text-blue-600 focus:ring-blue-500"
                                  aria-label={`${m.role.role_name} – ${perm.permission_name}`}
                                />
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
          role="alert"
        >
          <span className="text-sm font-medium">{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
