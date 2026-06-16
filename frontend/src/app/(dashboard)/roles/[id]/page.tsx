"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { RoleEditModal, RoleDeleteModal } from "@/components/roles/RoleModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getRoleById,
  updateRole,
  deleteRole,
  getPermissionsByModule,
} from "@/services/role.service";
import type { Role, RoleUpdatePayload } from "@/types/role.type";
import type { PermissionsByModule } from "@/types/permission.type";
import { formatDate } from "@/utils/formatDate";
import { usePermission } from "@/hooks/usePermission";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import { useToast } from "@/components/ui/ToastProvider";

export default function RoleDetailPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();
  const canViewRole = hasPermission("role.view");
  const canUpdateRole = hasPermission("role.update");
  const canDeleteRole = hasPermission("role.delete");

  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const roleId = Number(id);

  const [role, setRole] = useState<Role | null>(null);
  const [permsByModule, setPermsByModule] = useState<PermissionsByModule>({});
  const [assignedPermIds, setAssignedPermIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (!canViewRole) {
      setLoading(false);
      return;
    }

    if (Number.isNaN(roleId)) {
      setError("ID nhóm quyền không hợp lệ");
      setLoading(false);
      return;
    }

    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        const [roleData, permissionsData] = await Promise.all([
          getRoleById(roleId),
          getPermissionsByModule(),
        ]);

        const permIds =
          roleData.permission_ids ??
          roleData.permissions?.map((permission) => permission.id) ??
          [];

        setRole(roleData);
        setAssignedPermIds(permIds);
        setPermsByModule(permissionsData);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Lỗi tải nhóm quyền");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [roleId, canViewRole]);
  useEffect(() => {
    async function fetchRole() {
      const res = await getRoleById(roleId);

      setRole(res);
    }

    fetchRole();
  }, [roleId]);
  async function handleUpdate(payload: RoleUpdatePayload) {
    if (!role) return;

    if (!canUpdateRole) {
      toast.error("Bạn không có quyền cập nhật nhóm quyền.");
      return;
    }

    try {
      const updated = await updateRole(role.id, payload);

      const nextPermIds =
        updated.permission_ids ??
        updated.permissions?.map((permission) => permission.id) ??
        payload.permission_ids ??
        assignedPermIds;

      setRole({
        ...role,
        ...updated,
        permission_ids: nextPermIds,
      });

      setAssignedPermIds(nextPermIds);
      setEditOpen(false);
      toast.success("Cập nhật nhóm quyền thành công");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Cập nhật thất bại");
      throw e;
    }
  }

  async function handleDelete() {
    if (!role) return;

    if (!canDeleteRole) {
      toast.error("Bạn không có quyền xóa nhóm quyền.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteRole(role.id);
      toast.success(`Đã xóa "${role.role_name}"`);
      setTimeout(() => router.push("/roles"), 800);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  if (!canViewRole) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem chi tiết nhóm quyền. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/roles"
        backLabel="Quay lại danh sách"
      />
    );
  }

  if (loading) {
    return <Loading text="Đang tải thông tin nhóm quyền..." />;
  }

  if (error || !role) {
    return (
      <div className="flex min-h-[420px] flex-col items-center justify-center gap-4 rounded-2xl bg-white p-8 text-center shadow-sm dark:bg-slate-800">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-500 dark:bg-red-500/10">
          <svg
            className="h-7 w-7"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01M4.93 19h14.14c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.2 16c-.77 1.33.19 3 1.73 3z"
            />
          </svg>
        </div>

        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Không tải được nhóm quyền
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {error ?? "Không tìm thấy nhóm quyền"}
          </p>
        </div>

        <Link href="/roles">
          <Button variant="secondary">← Quay lại danh sách</Button>
        </Link>
      </div>
    );
  }

  const userCount = role.user_count ?? 0;

  const assignedModules = Object.entries(permsByModule)
    .map(([module, permissions]) => ({
      module,
      permissions: permissions.filter((permission) =>
        assignedPermIds.includes(permission.id),
      ),
    }))
    .filter((item) => item.permissions.length > 0);

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/roles" className="hover:text-blue-600">
          Nhóm quyền
        </Link>

        <span>/</span>

        <span className="font-medium text-slate-900 dark:text-slate-100">
          {role.role_name}
        </span>
      </nav>

      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
        <div className="border-b border-slate-100 bg-gradient-to-r from-blue-50 via-white to-purple-50 p-6 dark:border-slate-700 dark:from-slate-800 dark:via-slate-800 dark:to-slate-800">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-lg font-bold text-white shadow-sm">
                {role.role_name.charAt(0).toUpperCase()}
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                    {role.role_name}
                  </h1>

                  <code className="rounded-full bg-slate-900/5 px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-600">
                    {role.role_code}
                  </code>
                </div>

                <p className="mt-2 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
                  {role.description || "Nhóm quyền này chưa có mô tả."}
                </p>

                <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                  Ngày tạo: {formatDate(role.created_at)}
                </p>
              </div>
            </div>

            {(canUpdateRole || canDeleteRole) && (
              <div className="flex gap-2">
                {canUpdateRole && (
                  <Button
                    variant="secondary"
                    size="base"
                    onClick={() => setEditOpen(true)}
                  >
                    Chỉnh sửa
                  </Button>
                )}

                {canDeleteRole && (
                  <Button
                    variant="danger"
                    size="base"
                    onClick={() => setDeleteOpen(true)}
                  >
                    Xóa
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/30">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Tổng quyền
            </p>
            <p className="mt-2 text-2xl font-bold text-purple-600 dark:text-purple-400">
              {assignedPermIds.length}
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/30">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Người dùng
            </p>
            <p className="mt-2 text-2xl font-bold text-blue-600 dark:text-blue-400">
              {userCount}
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/30">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Module được cấp
            </p>
            <p className="mt-2 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {assignedModules.length}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Thông tin nhóm quyền
          </h2>

          <dl className="mt-4 space-y-4">
            <InfoRow label="Tên nhóm" value={role.role_name} />
            <InfoRow label="Mã nhóm" value={role.role_code} isCode />
            <InfoRow
              label="Số quyền"
              value={`${assignedPermIds.length} quyền`}
            />
            <InfoRow label="Số người dùng" value={`${userCount} người dùng`} />
            <InfoRow label="Ngày tạo" value={formatDate(role.created_at)} />
          </dl>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700 lg:col-span-2">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Quyền hạn được cấp
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Danh sách permission mà nhóm quyền này đang sở hữu.
              </p>
            </div>

            <span className="rounded-full bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700 ring-1 ring-purple-100 dark:bg-purple-500/10 dark:text-purple-300 dark:ring-purple-500/20">
              {assignedPermIds.length} quyền
            </span>
          </div>

          {assignedPermIds.length === 0 ? (
            <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 p-6 text-center dark:border-slate-600">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-700">
                <svg
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 11c1.657 0 3-1.343 3-3V6a3 3 0 10-6 0v2c0 1.657 1.343 3 3 3z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 11h14v9H5z"
                  />
                </svg>
              </div>

              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Chưa gán quyền nào
              </p>

              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {canUpdateRole
                  ? "Bấm “Chỉnh sửa” để cấp quyền cho nhóm này."
                  : "Bạn không có quyền cập nhật nhóm quyền này."}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {assignedModules.map(({ module, permissions }) => (
                <div
                  key={module}
                  className="rounded-xl border border-slate-100 p-4 dark:border-slate-700"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                      {module}
                    </p>

                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                      {permissions.length} quyền
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {permissions.map((permission) => (
                      <div
                        key={permission.id}
                        className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 dark:border-blue-500/20 dark:bg-blue-500/10"
                      >
                        <p className="text-xs font-medium text-blue-700 dark:text-blue-300">
                          {permission.permission_name}
                        </p>
                        <p className="mt-0.5 text-[11px] text-blue-500/80 dark:text-blue-300/70">
                          {permission.permission_code}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {canUpdateRole && (
        <RoleEditModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          role={role}
          currentPermissionIds={assignedPermIds}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteRole && (
        <RoleDeleteModal
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          role={role}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}

interface InfoRowProps {
  label: string;
  value: string;
  isCode?: boolean;
}

function InfoRow({ label, value, isCode = false }: InfoRowProps) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0 dark:border-slate-700">
      <dt className="shrink-0 text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </dt>

      <dd className="text-right text-sm font-medium text-slate-800 dark:text-slate-200">
        {isCode ? (
          <code className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-300">
            {value}
          </code>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}
