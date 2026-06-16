"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {
  UserEditModal,
  UserDeleteModal,
  UserResetPasswordModal,
} from "@/components/users/UserModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getUserById,
  updateUser,
  deleteUser,
  uploadUserAvatar,
  resetUserPassword,
} from "@/services/user.service";
import type { User, UserStatus, UserUpdatePayload } from "@/types/user.type";
import { formatDate, formatDateTime } from "@/utils/formatDate";
import { usePermission } from "@/hooks/usePermission";
import {
  ShieldCheck,
  Camera,
  KeyRound,
  Mail,
  Phone,
  CalendarDays,
  Clock3,
  UserRound,
  BadgeCheck,
  ArrowLeft,
  Copy,
} from "lucide-react";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import { useToast } from "@/components/ui/ToastProvider";

const ROLE_LABEL_MAP: Record<number, string> = {
  1: "Quản trị viên",
  2: "Quản lý",
  3: "Nhân viên",
};

const ROLE_CODE_MAP: Record<number, string> = {
  1: "admin",
  2: "manager",
  3: "staff",
};

const statusConfig: Record<UserStatus, { label: string; className: string }> = {
  active: {
    label: "Hoạt động",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  },
  inactive: {
    label: "Ngừng hoạt động",
    className:
      "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-600",
  },
  deleted: {
    label: "Đã xóa",
    className:
      "bg-red-50 text-red-700 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  },
};

export default function UserDetailPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();

  const canViewUser = hasPermission("user.view");
  const canUpdateUser = hasPermission("user.update");
  const canDeleteUser = hasPermission("user.delete");

  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const userId = Number(id);

  const [resetOpen, setResetOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);

  const [resetLoading, setResetLoading] = useState(false);
  const [resetPasswordResult, setResetPasswordResult] = useState<string | null>(
    null,
  );

  async function fetchUser() {
    if (!canViewUser) {
      setLoading(false);
      return;
    }

    if (Number.isNaN(userId)) {
      setError("ID người dùng không hợp lệ");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getUserById(userId);
      setUser(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Không tải được người dùng");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, canViewUser]);

  async function handleUpdate(payload: UserUpdatePayload) {
    if (!user) return;

    if (!canUpdateUser) {
      toast.error("Bạn không có quyền cập nhật người dùng.");
      return;
    }

    try {
      const updated = await updateUser(user.id, payload);

      setUser(updated);
      setEditOpen(false);
      toast.success("Cập nhật thành công");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Cập nhật thất bại");
      throw e;
    }
  }

  async function handleDelete() {
    if (!user) return;

    if (!canDeleteUser) {
      toast.error("Bạn không có quyền xóa người dùng.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteUser(user.id);
      toast.success(`Đã xóa "${user.full_name}"`);

      setTimeout(() => {
        router.push("/users");
      }, 800);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  async function handleUploadAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    if (!canUpdateUser) {
      toast.error("Bạn không có quyền cập nhật ảnh người dùng.");
      e.target.value = "";
      return;
    }

    const file = e.target.files?.[0];

    if (!file || !user) return;

    if (!file.type.startsWith("image/")) {
      toast.error("Vui lòng chọn file hình ảnh");
      e.target.value = "";
      return;
    }

    if (file.size > 3 * 1024 * 1024) {
      toast.error("Ảnh không được vượt quá 3MB");
      e.target.value = "";
      return;
    }

    setAvatarUploading(true);

    try {
      const updated = await uploadUserAvatar(user.id, file);
      setUser(updated);
      toast.success("Cập nhật ảnh đại diện thành công");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Upload ảnh thất bại");
    } finally {
      setAvatarUploading(false);
      e.target.value = "";
    }
  }

  async function handleResetPassword() {
    if (!user) return;

    if (!canUpdateUser) {
      toast.error("Bạn không có quyền reset mật khẩu người dùng.");
      return;
    }

    setResetLoading(true);
    setResetPasswordResult(null);

    try {
      const result = await resetUserPassword(user.id);

      setResetPasswordResult(result.new_temporary_password);
      setResetOpen(false);
      toast.success("Reset mật khẩu thành công");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Reset mật khẩu thất bại");
    } finally {
      setResetLoading(false);
    }
  }

  async function handleCopyPassword() {
    if (!resetPasswordResult) return;

    try {
      await navigator.clipboard.writeText(resetPasswordResult);
      toast.success("Đã copy mật khẩu");
    } catch {
      toast.error("Không copy được mật khẩu");
    }
  }
  if (!canViewUser) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem chi tiết người dùng. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/users"
        backLabel="Quay lại danh sách"
      />
    );
  }

  if (loading) {
    return (
      <div className="rounded-2xl bg-white p-8 shadow-sm dark:bg-slate-800">
        <Loading text="Đang tải thông tin người dùng..." />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="rounded-2xl bg-white p-8 shadow-sm dark:bg-slate-800">
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300">
            !
          </div>

          <p className="text-sm text-red-500">
            {error ?? "Không tìm thấy người dùng"}
          </p>

          <Link href="/users">
            <Button variant="secondary">← Quay lại</Button>
          </Link>
        </div>
      </div>
    );
  }

  const status = statusConfig[user.status] ?? statusConfig.inactive;
  const roleId = user.role_id;
  const firstChar = user.full_name?.trim()?.charAt(0)?.toUpperCase() || "U";
  console.log("user.role", user);
  // console.log("user.role_id", user.role_id);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <nav className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Link
            href="/users"
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition hover:bg-slate-100 hover:text-blue-600 dark:hover:bg-slate-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Người dùng
          </Link>

          <span>/</span>

          <span className="font-medium text-slate-900 dark:text-slate-100">
            {user.full_name}
          </span>
        </nav>
      </div>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="px-6 py-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-full border-4 border-white bg-slate-200 shadow-xl ring-1 ring-slate-200 dark:border-slate-800 dark:bg-slate-700 dark:ring-slate-600">
                {user.avatar_url ? (
                  <Image
                    src={user.avatar_url}
                    alt={user.full_name}
                    fill
                    className="object-cover"
                    sizes="112px"
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-4xl font-bold text-slate-500 dark:text-slate-300">
                    {firstChar}
                  </span>
                )}

                {avatarUploading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-xs font-semibold text-white">
                    Đang tải...
                  </div>
                )}
              </div>

              <div className="pb-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-slate-950 dark:text-white sm:text-3xl">
                    {user.full_name}
                  </h1>

                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${status.className}`}
                  >
                    {status.label}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <code className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                    @{user.username}
                  </code>

                  {user.role && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                      <ShieldCheck className="h-4 w-4" />
                      {user.role.name ?? "No role"}
                    </span>
                  )}
                </div>

                {canUpdateUser && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">
                      <Camera className="h-4 w-4" />
                      {avatarUploading ? "Đang upload..." : "Đổi ảnh"}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        disabled={avatarUploading}
                        onChange={handleUploadAvatar}
                      />
                    </label>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setResetOpen(true)}
                      loading={resetLoading}
                    >
                      <KeyRound className="mr-1 h-4 w-4" />
                      Reset mật khẩu
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {(canUpdateUser || canDeleteUser) && (
              <div className="flex gap-2">
                {canUpdateUser && (
                  <Button
                    variant="secondary"
                    size="base"
                    onClick={() => setEditOpen(true)}
                  >
                    Chỉnh sửa
                  </Button>
                )}

                {canDeleteUser && (
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

          {resetPasswordResult && (
            <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-bold">Mật khẩu tạm thời mới</p>
                  <p className="mt-1 text-xs opacity-80">
                    Vui lòng lưu lại mật khẩu này. Người dùng cần đổi mật khẩu
                    sau khi đăng nhập.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <code className="rounded-xl bg-white/80 px-3 py-2 font-mono text-sm font-bold text-emerald-900 dark:bg-slate-950/50 dark:text-emerald-200">
                    {resetPasswordResult}
                  </code>

                  <button
                    type="button"
                    onClick={handleCopyPassword}
                    className="inline-flex items-center gap-1 rounded-xl border border-emerald-300 bg-white/70 px-3 py-2 text-xs font-semibold text-emerald-800 transition hover:bg-emerald-100 dark:border-emerald-500/40 dark:bg-slate-900/40 dark:text-emerald-200 dark:hover:bg-emerald-500/20"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800 xl:col-span-2">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Thông tin tài khoản
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Thông tin liên hệ và trạng thái hoạt động của người dùng.
              </p>
            </div>

            <div className="hidden rounded-2xl bg-blue-50 p-3 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300 sm:block">
              <UserRound className="h-5 w-5" />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <InfoCard
              icon={<UserRound className="h-4 w-4" />}
              label="Họ tên"
              value={user.full_name}
            />

            <InfoCard
              icon={<BadgeCheck className="h-4 w-4" />}
              label="Username"
              value={`@${user.username}`}
              mono
            />

            <InfoCard
              icon={<Mail className="h-4 w-4" />}
              label="Email"
              value={user.email ?? "Chưa có email"}
            />

            <InfoCard
              icon={<Phone className="h-4 w-4" />}
              label="Điện thoại"
              value={user.phone ?? "Chưa có SĐT"}
            />

            <InfoCard
              icon={<CalendarDays className="h-4 w-4" />}
              label="Ngày tạo"
              value={formatDate(user.created_at)}
            />

            <InfoCard
              icon={<Clock3 className="h-4 w-4" />}
              label="Cập nhật gần nhất"
              value={user.updated_at ? formatDateTime(user.updated_at) : "—"}
            />

            <div className="md:col-span-2">
              <InfoCard
                icon={<Clock3 className="h-4 w-4" />}
                label="Đăng nhập gần nhất"
                value={
                  user.last_login_at
                    ? formatDateTime(user.last_login_at)
                    : "Chưa đăng nhập"
                }
              />
            </div>
          </div>
        </section>

        <aside className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Nhóm quyền
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Vai trò hiện tại trong hệ thống.
              </p>
            </div>

            <div className="rounded-2xl bg-blue-50 p-3 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </div>

          {!user?.role_id ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-center dark:border-slate-600">
              <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                Chưa gán quyền
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Người dùng này chưa có vai trò trong hệ thống.
              </p>
            </div>
          ) : (
            <div className="rounded-2xl border border-blue-100 bg-blue-50 p-5 dark:border-blue-500/20 dark:bg-blue-500/10">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm">
                  <ShieldCheck className="h-6 w-6" />
                </div>

                <div>
                  <p className="text-base font-bold text-slate-900 dark:text-white">
                    {user.role_name}
                  </p>

                  {/* <code className="mt-1 block text-xs text-slate-500 dark:text-slate-400">
                    {user.role_code} · ID {user.role_id}
                  </code> */}
                </div>
              </div>
            </div>
          )}
        </aside>
      </div>

      {canUpdateUser && (
        <UserEditModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          user={user}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteUser && (
        <UserDeleteModal
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          user={user}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}

      {canUpdateUser && (
        <UserResetPasswordModal
          open={resetOpen}
          onClose={() => setResetOpen(false)}
          user={user}
          onConfirm={handleResetPassword}
          loading={resetLoading}
        />
      )}
    </div>
  );
}

interface InfoCardProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}

function InfoCard({ icon, label, value, mono = false }: InfoCardProps) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/30">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-400">
        <span className="text-slate-500 dark:text-slate-400">{icon}</span>
        {label}
      </div>

      <div
        className={`break-words text-sm font-semibold text-slate-800 dark:text-slate-100 ${
          mono ? "font-mono" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
