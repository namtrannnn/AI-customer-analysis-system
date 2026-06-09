"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { UserEditModal, UserDeleteModal } from "@/components/users/UserModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import { getUserById, updateUser, deleteUser } from "@/services/user.service";
import type { User, UserStatus, UserUpdatePayload } from "@/types/user.type";
import { formatDate, formatDateTime } from "@/utils/formatDate";

const statusConfig: Record<UserStatus, { label: string; className: string }> = {
  active:   { label: "Hoạt động",      className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" },
  inactive: { label: "Ngừng hoạt động", className: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300" },
  locked:   { label: "Bị khóa",         className: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" },
};

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const userId = Number(id);

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    if (isNaN(userId)) return;
    setLoading(true);
    getUserById(userId)
      .then(setUser)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Lỗi"))
      .finally(() => setLoading(false));
  }, [userId]);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleUpdate(payload: UserUpdatePayload, _roleIds: number[]) {
    if (!user) return;
    const updated = await updateUser(user.id, payload);
    setUser(updated);
    showToast("success", "Cập nhật thành công");
  }

  async function handleDelete() {
    if (!user) return;
    setDeleteLoading(true);
    try {
      await deleteUser(user.id);
      showToast("success", `Đã xóa "${user.full_name}"`);
      setTimeout(() => router.push("/users"), 1000);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  if (loading) return <DashboardLayout><Loading text="Đang tải thông tin người dùng..." /></DashboardLayout>;

  if (error || !user) return (
    <DashboardLayout>
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-sm text-red-500">{error ?? "Không tìm thấy người dùng"}</p>
        <Link href="/users"><Button variant="secondary">← Quay lại</Button></Link>
      </div>
    </DashboardLayout>
  );

  const status = statusConfig[user.status];

  return (
    <DashboardLayout>
      <nav className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/users" className="hover:text-blue-600">Người dùng</Link>
        <span>/</span>
        <span className="font-medium text-slate-900 dark:text-slate-100">{user.full_name}</span>
      </nav>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ring-2 ring-white dark:ring-slate-800 shadow">
            {user.avatar_url ? (
              <Image src={user.avatar_url} alt={user.full_name} fill className="object-cover" sizes="64px" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-2xl font-bold text-slate-500 dark:text-slate-400">
                {user.full_name.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{user.full_name}</h1>
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}>
                {status.label}
              </span>
            </div>
            <code className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">@{user.username}</code>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>Chỉnh sửa</Button>
          <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>Xóa</Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Info */}
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm dark:shadow-slate-900/50">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">Thông tin tài khoản</h2>
          <dl className="space-y-3">
            {[
              { label: "Họ tên", value: user.full_name },
              { label: "Username", value: <code className="rounded bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-xs dark:text-slate-300">{user.username}</code> },
              { label: "Email", value: user.email ?? "—" },
              { label: "Điện thoại", value: user.phone ?? "—" },
              { label: "Ngày tạo", value: formatDate(user.created_at) },
              { label: "Đăng nhập gần nhất", value: user.last_login_at ? formatDateTime(user.last_login_at) : "Chưa đăng nhập" },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-start justify-between gap-4">
                <dt className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{label}</dt>
                <dd className="text-right text-sm text-slate-800 dark:text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Roles */}
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm dark:shadow-slate-900/50 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Nhóm quyền được gán ({user.roles.length})
          </h2>
          {user.roles.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Chưa gán nhóm quyền nào</p>
          ) : (
            <div className="space-y-2">
              {user.roles.map((r) => (
                <div
                  key={r.role_id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 dark:border-slate-700 p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{r.role_name}</p>
                    <code className="text-xs text-slate-400 dark:text-slate-500">{r.role_code}</code>
                  </div>
                  <p className="text-xs text-slate-400 dark:text-slate-500">Gán lúc {formatDate(r.assigned_at)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <UserEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        user={user}
        onSubmit={handleUpdate}
      />
      <UserDeleteModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        user={user}
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
