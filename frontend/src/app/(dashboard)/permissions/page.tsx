"use client";

import { Fragment, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Users,
  XCircle,
} from "lucide-react";

import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getRolePermissionMatrix,
  getPermissionsByModule,
  bulkUpdatePermissionMatrix,
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

        const local: Record<number, Set<number>> = {};
        mat.forEach((item) => {
          local[item.role.id] = new Set(item.permission_ids);
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

      matrix.forEach((item) => {
        const set = new Set(next[item.role.id] ?? []);

        if (checked) {
          set.add(permId);
        } else {
          set.delete(permId);
        }

        next[item.role.id] = set;
      });

      return next;
    });

    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);

    try {
      await bulkUpdatePermissionMatrix(
        matrix.map((item) => ({
          role_id: item.role.id,
          permission_ids: Array.from(localMatrix[item.role.id] ?? []),
        })),
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

    matrix.forEach((item) => {
      local[item.role.id] = new Set(item.permission_ids);
    });

    setLocalMatrix(local);
    setDirty(false);
  }

  const allPerms = Object.values(permsByModule).flat();
  const moduleCount = Object.keys(permsByModule).length;

  const assignedCount = matrix.reduce((total, item) => {
    return total + (localMatrix[item.role.id]?.size ?? 0);
  }, 0);

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
        <div className="bg-gradient-to-r from-blue-50 via-white to-indigo-50 px-6 py-6 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm shadow-blue-500/20">
                <ShieldCheck className="h-7 w-7" />
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                    Phân quyền
                  </h1>

                  <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    Permission Matrix
                  </span>
                </div>

                <p className="mt-2 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
                  Quản lý quyền chức năng theo từng nhóm người dùng. Tick vào ô
                  tương ứng để cấp hoặc thu hồi quyền.
                </p>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleReset}
                disabled={saving || !dirty}
              >
                <span className="inline-flex items-center gap-2">
                  <RotateCcw className="h-4 w-4" />
                  Hủy thay đổi
                </span>
              </Button>

              <Button
                size="sm"
                loading={saving}
                onClick={handleSave}
                disabled={!dirty}
              >
                <span className="inline-flex items-center gap-2">
                  <Save className="h-4 w-4" />
                  Lưu phân quyền
                </span>
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 border-t border-slate-100 p-4 dark:border-slate-700 sm:grid-cols-4">
          <StatCard
            icon={<Users className="h-5 w-5" />}
            label="Nhóm quyền"
            value={matrix.length}
          />

          <StatCard
            icon={<SlidersHorizontal className="h-5 w-5" />}
            label="Module"
            value={moduleCount}
          />

          <StatCard
            icon={<ShieldCheck className="h-5 w-5" />}
            label="Permission"
            value={allPerms.length}
          />

          <StatCard
            icon={<CheckCircle2 className="h-5 w-5" />}
            label="Đang cấp"
            value={assignedCount}
          />
        </div>
      </div>

      {dirty && (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm">
            Có thay đổi chưa được lưu. Bấm{" "}
            <span className="font-semibold">Lưu phân quyền</span> để áp dụng.
          </p>
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl bg-white p-10 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <Loading text="Đang tải ma trận phân quyền..." />
        </div>
      ) : error ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-4 rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-500 dark:bg-red-500/10">
            <XCircle className="h-7 w-7" />
          </div>

          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Không tải được phân quyền
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {error}
            </p>
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 dark:border-slate-700">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Ma trận quyền
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Hàng là permission, cột là nhóm quyền.
              </p>
            </div>

            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              {allPerms.length} quyền • {matrix.length} nhóm
            </div>
          </div>

          <div className="max-h-[calc(100vh-300px)] overflow-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="sticky top-0 z-20">
                <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                  <th className="sticky left-0 z-30 min-w-[360px] bg-slate-50 px-5 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    Chức năng / Module
                  </th>

                  {matrix.map((item) => {
                    const rolePerms = localMatrix[item.role.id] ?? new Set();
                    const allChecked =
                      allPerms.length > 0 &&
                      allPerms.every((permission) =>
                        rolePerms.has(permission.id),
                      );

                    return (
                      <th
                        key={item.role.id}
                        className="min-w-[150px] px-4 py-4 text-center"
                      >
                        <div className="flex flex-col items-center gap-2">
                          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                            {item.role.role_name.charAt(0).toUpperCase()}
                          </div>

                          <div>
                            <p className="line-clamp-1 text-xs font-semibold text-slate-800 dark:text-slate-100">
                              {item.role.role_name}
                            </p>
                            <p className="mt-0.5 text-[11px] text-slate-400 dark:text-slate-500">
                              {item.role.role_code}
                            </p>
                          </div>

                          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-white px-2 py-1 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700">
                            <input
                              type="checkbox"
                              checked={allChecked}
                              onChange={(e) =>
                                toggleRoleAll(
                                  item.role.id,
                                  allPerms.map((permission) => permission.id),
                                  e.target.checked,
                                )
                              }
                              className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-slate-600"
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
                {Object.entries(permsByModule).map(([module, permissions]) => (
                  <Fragment key={module}>
                    <tr className="bg-slate-50/80 dark:bg-slate-900/70">
                      <td
                        colSpan={matrix.length + 1}
                        className="sticky left-0 z-10 border-y border-slate-100 bg-slate-50/95 px-5 py-3 text-xs font-bold uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400"
                      >
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                            <ShieldCheck className="h-3.5 w-3.5" />
                          </span>
                          {module}
                          <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-400 ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700">
                            {permissions.length}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {permissions.map((permission) => {
                      const allRolesHave = matrix.every((item) =>
                        localMatrix[item.role.id]?.has(permission.id),
                      );

                      return (
                        <tr
                          key={permission.id}
                          className="group border-b border-slate-100 transition-colors hover:bg-blue-50/40 dark:border-slate-700 dark:hover:bg-slate-700/30"
                        >
                          <td className="sticky left-0 z-10 bg-white px-5 py-3.5 group-hover:bg-blue-50 dark:bg-slate-800 dark:group-hover:bg-slate-700">
                            <div className="flex items-center gap-3">
                              <label className="relative inline-flex cursor-pointer items-center">
                                <input
                                  type="checkbox"
                                  checked={allRolesHave}
                                  onChange={(e) =>
                                    togglePermAll(
                                      permission.id,
                                      e.target.checked,
                                    )
                                  }
                                  className="peer sr-only"
                                  title="Áp dụng cho tất cả nhóm"
                                />
                                <span className="flex h-5 w-5 items-center justify-center rounded-md border border-slate-300 bg-white text-white transition peer-checked:border-blue-600 peer-checked:bg-blue-600 dark:border-slate-600 dark:bg-slate-900">
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                </span>
                              </label>

                              <div className="min-w-0">
                                <p className="font-medium text-slate-800 dark:text-slate-100">
                                  {permission.permission_name}
                                </p>
                                <code className="mt-1 inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                                  {permission.permission_code}
                                </code>
                              </div>
                            </div>
                          </td>

                          {matrix.map((item) => {
                            const checked =
                              localMatrix[item.role.id]?.has(permission.id) ??
                              false;

                            return (
                              <td
                                key={item.role.id}
                                className="px-4 py-3.5 text-center"
                              >
                                <button
                                  type="button"
                                  onClick={() =>
                                    toggleCell(item.role.id, permission.id)
                                  }
                                  className={`inline-flex h-8 w-8 items-center justify-center rounded-xl border transition ${
                                    checked
                                      ? "border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                                      : "border-slate-200 bg-white text-slate-300 hover:border-blue-300 hover:text-blue-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-500"
                                  }`}
                                  aria-label={`${item.role.role_name} – ${permission.permission_name}`}
                                >
                                  {checked ? (
                                    <CheckCircle2 className="h-4 w-4" />
                                  ) : (
                                    <span className="h-2 w-2 rounded-full bg-current" />
                                  )}
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </Fragment>
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
          {toast.type === "success" ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : (
            <XCircle className="h-5 w-5" />
          )}
          <span className="text-sm font-medium">{toast.msg}</span>
        </div>
      )}
    </div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
}

function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/30">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {label}
          </p>
          <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
            {value}
          </p>
        </div>

        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-blue-600 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:text-blue-300 dark:ring-slate-700">
          {icon}
        </div>
      </div>
    </div>
  );
}
