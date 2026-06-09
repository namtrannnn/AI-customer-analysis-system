"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { RoleEditModal, RoleDeleteModal } from "@/components/roles/RoleModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import { getRoleById, updateRole, deleteRole, getRolePermissions, getPermissionsByModule } from "@/services/role.service";
import type { Role, RoleCreatePayload } from "@/types/role.type";
import type { PermissionsByModule } from "@/types/permission.type";
import { formatDate } from "@/utils/formatDate";

export default function RoleDetailPage() {
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
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    if (isNaN(roleId)) return;
    setLoading(true);
    Promise.all([
      getRoleById(roleId),
      getRolePermissions(roleId),
      getPermissionsByModule(),
    ])
      .then(([r, permIds, perms]) => {
        setRole(r);
        setAssignedPermIds(permIds);
        setPermsByModule(perms);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Lỗi"))
      .finally(() => setLoading(false));
  }, [roleId]);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleUpdate(payload: RoleCreatePayload) {
    if (!role) return;
    const updated = await updateRole(role.id, payload);
    setRole(updated);
    setAssignedPermIds(payload.permission_ids ?? assignedPermIds);
    showToast("success", "Cập nhật thành công");
  }

  async function handleDelete() {
    if (!role) return;
    setDeleteLoading(true);
    try {
      await deleteRole(role.id);
      showToast("success", `Đã xóa "${role.role_name}"`);
      setTimeout(() => router.push("/roles"), 1000);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  if (loading) return <DashboardLayout><Loading text="Đang tải thông tin nhóm quyền..." /></DashboardLayout>;

  if (error || !role) return (
    <DashboardLayout>
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-sm text-red-500">{error ?? "Không tìm thấy nhóm quyền"}</p>
        <Link href="/roles"><Button variant="secondary">← Quay lại</Button></Link>
      </div>
    </DashboardLayout>
  );

  return (
    <DashboardLayout>
      <nav className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/roles" className="hover:text-blue-600">Nhóm quyền</Link>
        <span>/</span>
        <span className="font-medium text-slate-900 dark:text-slate-100">{role.role_name}</span>
      </nav>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{role.role_name}</h1>
            <code className="rounded bg-slate-100 dark:bg-slate-700 px-2 py-0.5 text-sm text-slate-600 dark:text-slate-300">{role.role_code}</code>
          </div>
          {role.description && (
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{role.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>Chỉnh sửa</Button>
          <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>Xóa</Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Info */}
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm dark:shadow-slate-900/50">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">Thông tin</h2>
          <dl className="space-y-3">
            {[
              { label: "Tên nhóm", value: role.role_name },
              { label: "Mã", value: <code className="rounded bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-xs dark:text-slate-300">{role.role_code}</code> },
              { label: "Số quyền", value: `${assignedPermIds.length} quyền` },
              { label: "Số user", value: `${role.user_count} người dùng` },
              { label: "Ngày tạo", value: formatDate(role.created_at) },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-start justify-between gap-4">
                <dt className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{label}</dt>
                <dd className="text-right text-sm text-slate-800 dark:text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Permissions */}
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm dark:shadow-slate-900/50 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Quyền hạn ({assignedPermIds.length})
          </h2>
          {assignedPermIds.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Chưa gán quyền nào</p>
          ) : (
            <div className="space-y-4">
              {Object.entries(permsByModule).map(([module, perms]) => {
                const assigned = perms.filter((p) => assignedPermIds.includes(p.id));
                if (assigned.length === 0) return null;
                return (
                  <div key={module}>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {module}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {assigned.map((p) => (
                        <span
                          key={p.id}
                          className="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/30 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400"
                        >
                          {p.permission_name}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <RoleEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        role={role}
        currentPermissionIds={assignedPermIds}
        onSubmit={handleUpdate}
      />
      <RoleDeleteModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        role={role}
        onConfirm={handleDelete}
        loading={deleteLoading}
      />

      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg ${toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white"}`} role="alert">
          <span className="text-sm font-medium">{toast.msg}</span>
        </div>
      )}
    </DashboardLayout>
  );
}
