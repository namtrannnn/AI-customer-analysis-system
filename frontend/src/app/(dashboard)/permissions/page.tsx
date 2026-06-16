"use client";

import { Fragment, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Users,
  XCircle,
  LockKeyhole,
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
import { usePermission } from "@/hooks/usePermission";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import { useToast } from "@/components/ui/ToastProvider";

export default function PermissionsPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();

  const canViewPermission = hasPermission("permission.view");
  const canUpdatePermission = hasPermission("permission.update");

  const [matrix, setMatrix] = useState<RolePermissionMatrix[]>([]);
  const [permsByModule, setPermsByModule] = useState<PermissionsByModule>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [localMatrix, setLocalMatrix] = useState<Record<number, Set<number>>>(
    {},
  );

  useEffect(() => {
    if (!canViewPermission) {
      setLoading(false);
      return;
    }

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
  }, [canViewPermission]);

  function toggleCell(roleId: number, permId: number) {
    if (!canUpdatePermission) {
      toast.error("Bạn không có quyền cập nhật phân quyền.");
      return;
    }

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
    if (!canUpdatePermission) {
      toast.error("Bạn không có quyền lưu phân quyền.");
      return;
    }

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
    if (!canUpdatePermission) {
      toast.error("Bạn không có quyền hủy thay đổi phân quyền.");
      return;
    }

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
    if (!canUpdatePermission) {
      toast.error("Bạn không có quyền lưu phân quyền.");
      return;
    }

    setSaving(true);

    try {
      await bulkUpdatePermissionMatrix(
        matrix.map((item) => ({
          role_id: item.role.id,
          permission_ids: Array.from(localMatrix[item.role.id] ?? []),
        })),
      );

      setDirty(false);
      toast.success("Lưu phân quyền thành công");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (!canUpdatePermission) {
      toast.error("Bạn không có quyền hủy thay đổi phân quyền.");
      return;
    }

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

  if (!canViewPermission) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem ma trận phân quyền. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/dashboard"
        backLabel="Về Dashboard"
        showHomeButton={false}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
        <div className="bg-gradient-to-r from-blue-50 via-white to-indigo-50 px-6 py-4 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm shadow-blue-500/20">
                <ShieldCheck className="h-4 w-4" />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  Phân quyền
                </h1>

                <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  Ma trận phân quyền
                </span>

                {!canUpdatePermission && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    Chỉ xem
                  </span>
                )}
              </div>
            </div>

            {canUpdatePermission && (
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
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 border-t border-slate-100 p-3 dark:border-slate-700 lg:grid-cols-4">
          <StatCard
            icon={<Users className="h-5 w-5" />}
            label="Nhóm quyền"
            value={matrix.length}
          />

          <StatCard
            icon={<SlidersHorizontal className="h-5 w-5" />}
            label="Phân hệ"
            value={moduleCount}
          />

          <StatCard
            icon={<ShieldCheck className="h-5 w-5" />}
            label="Quyền"
            value={allPerms.length}
          />

          <StatCard
            icon={<CheckCircle2 className="h-5 w-5" />}
            label="Đang cấp"
            value={assignedCount}
          />
        </div>
      </div>

      {dirty && canUpdatePermission && (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm">
            Có thay đổi chưa được lưu. Bấm{" "}
            <span className="font-semibold">Lưu phân quyền</span> để áp dụng.
          </p>
        </div>
      )}

      {!canUpdatePermission && (
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
          <LockKeyhole className="h-5 w-5 shrink-0" />
          <p className="text-sm">
            Bạn chỉ có quyền xem ma trận phân quyền, không thể chỉnh sửa hoặc
            lưu thay đổi.
          </p>
        </div>
      )}

      {loading ? (
        <div className="rounded-3xl bg-white p-10 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <Loading text="Đang tải ma trận phân quyền..." />
        </div>
      ) : error ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-4 rounded-3xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
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
        <div className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3 dark:border-slate-700">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Ma trận quyền
            </h2>

            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              {allPerms.length} quyền • {matrix.length} nhóm
            </div>
          </div>
          <div className="max-h-[calc(100vh-230px)] overflow-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="sticky top-0 z-20">
                <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                  <th className="sticky left-0 z-30 min-w-[360px] bg-slate-50 px-5 py-2.5 text-left text-xs font-bold uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
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
                        className="min-w-[150px] px-4 py-2 text-center"
                      >
                        <div className="flex flex-col items-center gap-1">
                          <p className="line-clamp-1 max-w-[140px] text-center text-xs font-bold leading-4 text-slate-800 dark:text-slate-100">
                            {item.role.role_name}
                          </p>

                          <label
                            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold transition-all ${
                              allChecked
                                ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300"
                                : "border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
                            } ${
                              canUpdatePermission
                                ? "cursor-pointer hover:border-blue-300 hover:bg-blue-50/70 dark:hover:border-blue-500/30 dark:hover:bg-blue-500/10"
                                : "cursor-not-allowed opacity-60"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={allChecked}
                              disabled={!canUpdatePermission}
                              onChange={(e) =>
                                toggleRoleAll(
                                  item.role.id,
                                  allPerms.map((permission) => permission.id),
                                  e.target.checked,
                                )
                              }
                              className="sr-only"
                            />

                            <TinyCheckbox checked={allChecked} />

                            <span>Tất cả</span>
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
                              <label
                                className={`relative inline-flex items-center ${
                                  canUpdatePermission
                                    ? "cursor-pointer"
                                    : "cursor-not-allowed opacity-60"
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={allRolesHave}
                                  disabled={!canUpdatePermission}
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
                                  disabled={!canUpdatePermission}
                                  onClick={() =>
                                    toggleCell(item.role.id, permission.id)
                                  }
                                  className={`inline-flex h-8 w-8 items-center justify-center rounded-xl border transition disabled:cursor-not-allowed ${
                                    checked
                                      ? "border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                                      : "border-slate-200 bg-white text-slate-300 hover:border-blue-300 hover:text-blue-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-500"
                                  } ${
                                    !canUpdatePermission
                                      ? "opacity-70 hover:border-slate-200 hover:text-slate-300 dark:hover:border-slate-600"
                                      : ""
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
    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/30">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
            {label}
          </p>

          <p className="mt-1 text-xl font-black leading-none text-slate-900 dark:text-slate-100">
            {value}
          </p>
        </div>

        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-blue-600 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:text-blue-300 dark:ring-slate-700">
          {icon}
        </div>
      </div>
    </div>
  );
}

function TinyCheckbox({ checked }: { checked: boolean }) {
  return (
    <span
      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-md border transition-all ${
        checked
          ? "border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-500/20"
          : "border-slate-300 bg-white text-transparent dark:border-slate-600 dark:bg-slate-900"
      }`}
    >
      <Check className="h-3 w-3" />
    </span>
  );
}
