"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  AtSign,
  CalendarDays,
  Camera,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  UserRound,
  BadgeCheck,
  Pencil,
  X,
} from "lucide-react";

import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import { getCurrentUser } from "@/services/auth.service";
import {
  getUserById,
  updateUser,
  uploadUserAvatar,
} from "@/services/user.service";
import { formatDateTime } from "@/utils/formatDate";
import type { AuthUser } from "@/types/auth.type";
import type { User, UserStatus, UserUpdatePayload } from "@/types/user.type";

const ROLE_LABEL_MAP: Record<number, string> = {
  1: "Quản trị viên",
  2: "Quản lý",
  3: "Nhân viên",
};

const statusConfig: Record<UserStatus, { label: string; className: string }> = {
  active: {
    label: "Đang hoạt động",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  },
  inactive: {
    label: "Tạm khóa",
    className:
      "bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
  },
  deleted: {
    label: "Đã xóa",
    className:
      "bg-red-50 text-red-700 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  },
};

export default function ProfilePage() {
  const router = useRouter();

  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isEditingPassword, setIsEditingPassword] = useState(false);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const initials = useMemo(() => {
    if (!user?.full_name) return "?";

    return user.full_name
      .trim()
      .split(" ")
      .filter(Boolean)
      .map((word) => word[0])
      .slice(-2)
      .join("")
      .toUpperCase();
  }, [user?.full_name]);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  useEffect(() => {
    const currentUser = getCurrentUser();

    if (!currentUser?.id) {
      router.push("/login");
      return;
    }

    const currentUserId = currentUser.id;

    setAuthUser(currentUser);

    async function fetchProfile() {
      try {
        setLoading(true);

        const data = await getUserById(currentUserId);

        setUser(data);
        setFullName(data.full_name ?? "");
        setEmail(data.email ?? "");
        setPhone(data.phone ?? "");
      } catch (error) {
        console.error(error);
        showToast("error", "Không thể tải thông tin tài khoản");
      } finally {
        setLoading(false);
      }
    }

    fetchProfile();
  }, [router]);

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
    } catch (error) {
      console.error(error);
      showToast("error", "Upload ảnh thất bại");
    } finally {
      setAvatarUploading(false);
      e.target.value = "";
    }
  }
  async function handleSubmitProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!user) return;

    const payload: UserUpdatePayload = {
      full_name: fullName.trim(),
      email: email.trim() || null,
      phone: phone.trim() || null,
      role_id: user.role_id ?? null,
    };

    try {
      setSavingProfile(true);

      const updated = await updateUser(user.id, payload);

      setUser(updated);
      setFullName(updated.full_name ?? "");
      setEmail(updated.email ?? "");
      setPhone(updated.phone ?? "");

      const oldUser = getCurrentUser();

      if (oldUser) {
        localStorage.setItem(
          "user",
          JSON.stringify({
            ...oldUser,
            full_name: updated.full_name,
            email: updated.email,
            username: updated.username,
          }),
        );
      }

      setIsEditingProfile(false);
      showToast("success", "Cập nhật thông tin thành công");
    } catch (error) {
      console.error(error);
      showToast("error", "Cập nhật thông tin thất bại");
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSubmitPassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!currentPassword.trim()) {
      showToast("error", "Vui lòng nhập mật khẩu hiện tại");
      return;
    }

    if (newPassword.length < 8) {
      showToast("error", "Mật khẩu mới phải có ít nhất 8 ký tự");
      return;
    }

    if (newPassword !== confirmPassword) {
      showToast("error", "Xác nhận mật khẩu không khớp");
      return;
    }

    try {
      setSavingPassword(true);

      // TODO: gắn API đổi mật khẩu ở đây
      // await changePassword({
      //   old_password: currentPassword,
      //   new_password: newPassword,
      //   confirm_password: confirmPassword,
      // });

      showToast("error", "Chưa gắn API đổi mật khẩu");

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      console.error(error);
      showToast("error", "Đổi mật khẩu thất bại");
    } finally {
      setSavingPassword(false);
    }
  }

  function handleCancelProfile() {
    if (!user) return;

    setFullName(user.full_name ?? "");
    setEmail(user.email ?? "");
    setPhone(user.phone ?? "");
    setIsEditingProfile(false);
  }

  function handleCancelPassword() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setShowCurrentPassword(false);
    setShowNewPassword(false);
    setShowConfirmPassword(false);
    setIsEditingPassword(false);
  }

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <Loading text="Đang tải thông tin cá nhân..." />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
          Không tìm thấy thông tin tài khoản.
        </p>
      </div>
    );
  }

  const currentStatus = statusConfig[user.status] ?? statusConfig.inactive;
  const roleLabel = user.role_id
    ? (ROLE_LABEL_MAP[user.role_id] ?? `Role #${user.role_id}`)
    : (authUser?.roles?.[0] ?? "Chưa gán quyền");

  return (
    <div className="space-y-6 pb-24">
      {/* Header */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-full border-4 border-white bg-slate-100 shadow-lg ring-1 ring-slate-200 dark:border-slate-800 dark:bg-slate-700 dark:ring-slate-600">
              {user.avatar_url ? (
                <Image
                  src={user.avatar_url}
                  alt={user.full_name}
                  fill
                  className="object-cover"
                  sizes="96px"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-slate-100 text-3xl font-bold text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                  {initials}
                </div>
              )}

              {avatarUploading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/45 text-xs font-semibold text-white">
                  Đang tải...
                </div>
              )}

              <label
                className={`absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-blue-600 shadow-md transition hover:bg-blue-50 dark:border-slate-600 dark:bg-slate-800 dark:text-blue-300 dark:hover:bg-slate-700 ${
                  avatarUploading
                    ? "cursor-not-allowed opacity-70"
                    : "cursor-pointer"
                }`}
                title="Đổi ảnh đại diện"
              >
                <Camera className="h-4 w-4" />

                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={avatarUploading}
                  onChange={handleUploadAvatar}
                />
              </label>
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white sm:text-3xl">
                  {user.full_name}
                </h1>

                <CheckCircle2 className="h-5 w-5 text-blue-500" />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  <AtSign className="h-4 w-4" />
                  {user.username}
                </span>

                <span
                  className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ${currentStatus.className}`}
                >
                  {currentStatus.label}
                </span>

                <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                  <ShieldCheck className="h-4 w-4" />
                  {roleLabel}
                </span>
              </div>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500 dark:text-slate-400">
                Quản lý thông tin cá nhân, thông tin liên hệ và mật khẩu đăng
                nhập của tài khoản đang sử dụng.
              </p>
            </div>
          </div>

          {!isEditingProfile ? (
            <button
              type="button"
              onClick={() => setIsEditingProfile(true)}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
            >
              <Pencil className="h-4 w-4" />
              Chỉnh sửa thông tin
            </button>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row lg:items-center">
              <button
                type="button"
                onClick={handleCancelProfile}
                disabled={savingProfile}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                <X className="h-4 w-4" />
                Hủy
              </button>

              <Button
                form="profile-form"
                type="submit"
                disabled={savingProfile}
              >
                <Save className="mr-2 h-4 w-4" />
                {savingProfile ? "Đang lưu..." : "Lưu thay đổi"}
              </Button>
            </div>
          )}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Profile form */}
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800 xl:col-span-2">
          <SectionHeader
            title="Thông tin cá nhân"
            description={
              isEditingProfile
                ? "Bạn đang chỉnh sửa thông tin cá nhân."
                : "Thông tin cá nhân hiện tại của tài khoản."
            }
            icon={<UserRound className="h-5 w-5" />}
            action={
              !isEditingProfile ? (
                <button
                  type="button"
                  onClick={() => setIsEditingProfile(true)}
                  className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Chỉnh sửa
                </button>
              ) : null
            }
          />

          <form
            id="profile-form"
            onSubmit={handleSubmitProfile}
            className="space-y-5"
          >
            <div className="grid gap-5 md:grid-cols-2">
              <FormField
                label="Họ và tên"
                icon={<UserRound className="h-4 w-4" />}
              >
                <TextInput
                  value={fullName}
                  onChange={setFullName}
                  placeholder="Nhập họ và tên"
                  disabled={!isEditingProfile || savingProfile}
                />
              </FormField>

              <FormField label="Email" icon={<Mail className="h-4 w-4" />}>
                <TextInput
                  value={email}
                  onChange={setEmail}
                  placeholder="Nhập email"
                  type="email"
                  disabled={!isEditingProfile || savingProfile}
                />
              </FormField>

              <FormField
                label="Số điện thoại"
                icon={<Phone className="h-4 w-4" />}
              >
                <TextInput
                  value={phone}
                  onChange={setPhone}
                  placeholder="Nhập số điện thoại"
                  disabled={!isEditingProfile || savingProfile}
                />
              </FormField>

              <FormField
                label="Tên đăng nhập"
                icon={<AtSign className="h-4 w-4" />}
              >
                <ReadOnlyInput value={`@${user.username}`} />
              </FormField>
            </div>

            {isEditingProfile && (
              <div className="flex justify-end gap-2 border-t border-slate-100 pt-5 dark:border-slate-700">
                <button
                  type="button"
                  onClick={handleCancelProfile}
                  disabled={savingProfile}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  Hủy
                </button>

                <Button type="submit" disabled={savingProfile}>
                  <Save className="mr-2 h-4 w-4" />
                  {savingProfile ? "Đang lưu..." : "Lưu thông tin"}
                </Button>
              </div>
            )}
          </form>
        </section>

        {/* Account summary */}
        <aside className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <SectionHeader
            title="Tài khoản"
            description="Thông tin hệ thống của tài khoản."
            icon={<BadgeCheck className="h-5 w-5" />}
          />

          <div className="space-y-3">
            <InfoItem
              icon={<CalendarDays className="h-4 w-4" />}
              label="Ngày tạo"
              value={formatDateTime(user.created_at)}
            />

            <InfoItem
              icon={<ShieldCheck className="h-4 w-4" />}
              label="Nhóm quyền"
              value={roleLabel}
            />

            <InfoItem
              icon={<KeyRound className="h-4 w-4" />}
              label="User ID"
              value={`#${user.id}`}
            />

            <InfoItem
              icon={<CalendarDays className="h-4 w-4" />}
              label="Cập nhật gần nhất"
              value={user.updated_at ? formatDateTime(user.updated_at) : "—"}
            />

            <InfoItem
              icon={<ShieldCheck className="h-4 w-4" />}
              label="Đăng nhập gần nhất"
              value={
                user.last_login_at
                  ? formatDateTime(user.last_login_at)
                  : "Chưa đăng nhập"
              }
            />
          </div>
        </aside>
      </div>

      {/* Password */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <SectionHeader
          title="Đổi mật khẩu"
          description={
            isEditingPassword
              ? "Nhập mật khẩu hiện tại và mật khẩu mới để cập nhật."
              : "Mật khẩu được ẩn để bảo vệ tài khoản. Bấm đổi mật khẩu để cập nhật."
          }
          icon={<LockKeyhole className="h-5 w-5" />}
          action={
            !isEditingPassword ? (
              <button
                type="button"
                onClick={() => setIsEditingPassword(true)}
                className="inline-flex h-9 items-center gap-2 rounded-xl bg-blue-600 px-3 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700"
              >
                <Pencil className="h-3.5 w-3.5" />
                Đổi mật khẩu
              </button>
            ) : null
          }
        />

        {!isEditingPassword ? (
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-900/40">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                <KeyRound className="h-4 w-4" />
              </div>

              <div>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                  Mật khẩu đăng nhập
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Vì lý do bảo mật, mật khẩu hiện tại không được hiển thị. Bạn
                  có thể đổi mật khẩu khi cần.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmitPassword} className="space-y-5">
            <div className="grid gap-5 md:grid-cols-3">
              <PasswordField
                label="Mật khẩu hiện tại"
                value={currentPassword}
                onChange={setCurrentPassword}
                show={showCurrentPassword}
                onToggleShow={() => setShowCurrentPassword((v) => !v)}
                placeholder="Nhập mật khẩu hiện tại"
                disabled={savingPassword}
              />

              <PasswordField
                label="Mật khẩu mới"
                value={newPassword}
                onChange={setNewPassword}
                show={showNewPassword}
                onToggleShow={() => setShowNewPassword((v) => !v)}
                placeholder="Nhập mật khẩu mới"
                disabled={savingPassword}
              />

              <PasswordField
                label="Xác nhận mật khẩu"
                value={confirmPassword}
                onChange={setConfirmPassword}
                show={showConfirmPassword}
                onToggleShow={() => setShowConfirmPassword((v) => !v)}
                placeholder="Nhập lại mật khẩu mới"
                disabled={savingPassword}
              />
            </div>

            <div className="flex flex-col gap-4 rounded-2xl bg-slate-50 p-4 dark:bg-slate-900/40 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                  <KeyRound className="h-4 w-4" />
                </div>

                <div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                    Lưu ý bảo mật
                  </p>
                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    Mật khẩu mới nên có ít nhất 8 ký tự. Nên dùng chữ hoa, chữ
                    thường, số và ký tự đặc biệt.
                  </p>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleCancelPassword}
                  disabled={savingPassword}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  Hủy
                </button>

                <Button type="submit" disabled={savingPassword}>
                  {savingPassword ? "Đang đổi..." : "Lưu mật khẩu"}
                </Button>
              </div>
            </div>
          </form>
        )}
      </section>

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-2xl px-4 py-3 text-sm font-medium text-white shadow-xl ${
            toast.type === "success" ? "bg-emerald-600" : "bg-red-600"
          }`}
          role="alert"
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function SectionHeader({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
          {title}
        </h2>

        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {description}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {action}

        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
          {icon}
        </div>
      </div>
    </div>
  );
}

function FormField({
  label,
  icon,
  children,
}: {
  label: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <span className="text-blue-500 dark:text-blue-300">{icon}</span>
        {label}
      </label>

      {children}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  type = "text",
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <input
      type={type}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={`h-12 w-full rounded-2xl border px-4 text-sm font-semibold outline-none transition ${
        disabled
          ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400"
          : "border-slate-200 bg-slate-50 text-slate-800 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-100 dark:focus:bg-slate-900"
      }`}
      placeholder={placeholder}
    />
  );
}

function ReadOnlyInput({ value }: { value: string }) {
  return (
    <input
      value={value}
      disabled
      className="h-12 w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-4 text-sm font-semibold text-slate-500 outline-none dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400"
    />
  );
}

function InfoItem({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/30">
      <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-400">
        <span className="text-blue-500 dark:text-blue-300">{icon}</span>
        {label}
      </div>

      <div className="break-words text-sm font-semibold text-slate-800 dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  show,
  onToggleShow,
  placeholder,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggleShow: () => void;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <FormField label={label} icon={<LockKeyhole className="h-4 w-4" />}>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={`h-12 w-full rounded-2xl border px-4 pr-12 text-sm font-semibold outline-none transition ${
            disabled
              ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400"
              : "border-slate-200 bg-slate-50 text-slate-800 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-100 dark:focus:bg-slate-900"
          }`}
          placeholder={placeholder}
        />

        <button
          type="button"
          onClick={onToggleShow}
          disabled={disabled}
          className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </FormField>
  );
}
