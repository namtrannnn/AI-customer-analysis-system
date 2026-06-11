"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { UserEditModal, UserDeleteModal } from "@/components/users/UserModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getUserById,
  updateUser,
  deleteUser,
  uploadUserAvatar,
} from "@/services/user.service";
import type { User, UserStatus, UserUpdatePayload } from "@/types/user.type";
import { formatDate, formatDateTime } from "@/utils/formatDate";
import { ShieldCheck, Camera } from "lucide-react";

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
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  inactive: {
    label: "Ngừng hoạt động",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  },
  deleted: {
    label: "Đã xóa",
    className: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400",
  },
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
  const [avatarUploading, setAvatarUploading] = useState(false);

  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  async function fetchUser() {
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
  }, [userId]);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleUpdate(payload: UserUpdatePayload, roleIds: number[]) {
    if (!user) return;

    try {
      const updated = await updateUser(user.id, {
        ...payload,
        role_ids: roleIds,
      });

      setUser(updated);
      setEditOpen(false);
      showToast("success", "Cập nhật thành công");
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Cập nhật thất bại");
      throw e;
    }
  }

  async function handleDelete() {
    if (!user) return;

    setDeleteLoading(true);

    try {
      await deleteUser(user.id);
      showToast("success", `Đã xóa "${user.full_name}"`);

      setTimeout(() => {
        router.push("/users");
      }, 800);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  async function handleUploadAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];

    if (!file || !user) return;

    if (!file.type.startsWith("image/")) {
      showToast("error", "Vui lòng chọn file hình ảnh");
      e.target.value = "";
      return;
    }

    if (file.size > 3 * 1024 * 1024) {
      showToast("error", "Ảnh không được vượt quá 3MB");
      e.target.value = "";
      return;
    }

    setAvatarUploading(true);

    try {
      const updated = await uploadUserAvatar(user.id, file);
      setUser(updated);
      showToast("success", "Cập nhật ảnh đại diện thành công");
    } catch (e: unknown) {
      showToast(
        "error",
        e instanceof Error ? e.message : "Upload ảnh thất bại",
      );
    } finally {
      setAvatarUploading(false);
      e.target.value = "";
    }
  }

  if (loading) {
    return (
      <div>
        <Loading text="Đang tải thông tin người dùng..." />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div>
        <div className="flex flex-col items-center gap-4 py-20 text-center">
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
  const roleIds = user.role_ids ?? [];
  const firstChar = user.full_name?.trim()?.charAt(0)?.toUpperCase() || "U";

  return (
    <div>
      <nav className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/users" className="hover:text-blue-600">
          Người dùng
        </Link>
        <span>/</span>
        <span className="font-medium text-slate-900 dark:text-slate-100">
          {user.full_name}
        </span>
      </nav>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-slate-200 shadow ring-2 ring-white dark:bg-slate-700 dark:ring-slate-800">
            {user.avatar_url ? (
              <Image
                src={user.avatar_url}
                alt={user.full_name}
                fill
                className="object-cover"
                sizes="64px"
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-2xl font-bold text-slate-500 dark:text-slate-400">
                {firstChar}
              </span>
            )}

            {avatarUploading && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs font-semibold text-white">
                ...
              </div>
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {user.full_name}
              </h1>

              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}
              >
                {status.label}
              </span>
            </div>

            <code className="mt-0.5 block text-sm text-slate-500 dark:text-slate-400">
              @{user.username}
            </code>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700">
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
                disabled
                title="BE chưa có API reset password"
              >
                Reset mật khẩu
              </Button>
            </div>

            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              Reset mật khẩu sẽ bật sau khi backend thêm API.
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setEditOpen(true)}
          >
            Chỉnh sửa
          </Button>

          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteOpen(true)}
          >
            Xóa
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl bg-white p-6 shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Thông tin tài khoản
          </h2>

          <dl className="space-y-3">
            {[
              { label: "Họ tên", value: user.full_name },
              {
                label: "Username",
                value: (
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-700 dark:text-slate-300">
                    {user.username}
                  </code>
                ),
              },
              { label: "Email", value: user.email ?? "—" },
              { label: "Điện thoại", value: user.phone ?? "—" },
              { label: "Ngày tạo", value: formatDate(user.created_at) },
              {
                label: "Cập nhật",
                value: user.updated_at ? formatDateTime(user.updated_at) : "—",
              },
              {
                label: "Đăng nhập gần nhất",
                value: user.last_login_at
                  ? formatDateTime(user.last_login_at)
                  : "Chưa đăng nhập",
              },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="flex items-start justify-between gap-4"
              >
                <dt className="shrink-0 text-xs text-slate-500 dark:text-slate-400">
                  {label}
                </dt>

                <dd className="text-right text-sm text-slate-800 dark:text-slate-200">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded-xl bg-white p-6 shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Nhóm quyền được gán ({roleIds.length})
          </h2>

          {roleIds.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
              Chưa gán nhóm quyền nào
            </p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2">
              {roleIds.map((roleId) => (
                <div
                  key={roleId}
                  className="flex items-center justify-between rounded-lg border border-slate-100 p-3 dark:border-slate-700"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                      <ShieldCheck className="h-4 w-4" />
                    </div>

                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                        {ROLE_LABEL_MAP[roleId] ?? `Role #${roleId}`}
                      </p>

                      <code className="text-xs text-slate-400 dark:text-slate-500">
                        {ROLE_CODE_MAP[roleId] ?? `role_${roleId}`}
                      </code>
                    </div>
                  </div>

                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                    ID {roleId}
                  </span>
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
