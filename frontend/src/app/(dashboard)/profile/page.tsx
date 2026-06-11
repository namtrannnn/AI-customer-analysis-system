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
} from "lucide-react";

import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import { getCurrentUser } from "@/services/auth.service";
import { getUserById, updateUser } from "@/services/user.service";
import { formatDateTime } from "@/utils/formatDate";
import type { AuthUser } from "@/types/auth.type";
import type { User, UserUpdatePayload } from "@/types/user.type";

const statusConfig = {
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

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const initials = useMemo(() => {
    if (!user?.full_name) return "?";

    return user.full_name
      .split(" ")
      .map((word) => word[0])
      .slice(-2)
      .join("")
      .toUpperCase();
  }, [user?.full_name]);

  useEffect(() => {
    const currentUser = getCurrentUser();

    if (!currentUser?.id) {
      router.push("/login");
      return;
    }

    setAuthUser(currentUser);

    const fetchProfile = async () => {
      try {
        setLoading(true);

        const data = await getUserById(currentUser.id);

        setUser(data);
        setFullName(data.full_name ?? "");
        setEmail(data.email ?? "");
        setPhone(data.phone ?? "");
      } catch (error) {
        console.error(error);
        alert("Không thể tải thông tin tài khoản");
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [router]);

  const handleSubmitProfile = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!user) return;

    const payload: UserUpdatePayload = {
      full_name: fullName.trim(),
      email: email.trim() || null,
      phone: phone.trim() || null,
    };

    try {
      setSavingProfile(true);

      const updated = await updateUser(user.id, payload);

      setUser(updated);

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

      alert("Cập nhật thông tin thành công");
    } catch (error) {
      console.error(error);
      alert("Cập nhật thông tin thất bại");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSubmitPassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!currentPassword.trim()) {
      alert("Vui lòng nhập mật khẩu hiện tại");
      return;
    }

    if (newPassword.length < 6) {
      alert("Mật khẩu mới phải có ít nhất 6 ký tự");
      return;
    }

    if (newPassword !== confirmPassword) {
      alert("Xác nhận mật khẩu không khớp");
      return;
    }

    try {
      setSavingPassword(true);

      // TODO:
      // Sau khi BE có API đổi mật khẩu, gọi service ở đây.
      // Ví dụ:
      // await changeMyPassword({
      //   current_password: currentPassword,
      //   new_password: newPassword,
      // });

      alert("Chưa có API đổi mật khẩu. UI đã sẵn sàng để gắn API.");

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      console.error(error);
      alert("Đổi mật khẩu thất bại");
    } finally {
      setSavingPassword(false);
    }
  };

  const handleCancel = () => {
    if (!user) return;

    setFullName(user.full_name ?? "");
    setEmail(user.email ?? "");
    setPhone(user.phone ?? "");
  };

  if (loading) {
    return <Loading />;
  }

  if (!user) {
    return (
      <div className="rounded-[2rem] border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-white/[0.08] dark:bg-slate-900">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
          Không tìm thấy thông tin tài khoản.
        </p>
      </div>
    );
  }

  const currentStatus = statusConfig[user.status];

  return (
    <div className="space-y-6 pb-24">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/[0.08] dark:bg-slate-900">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="relative h-28 w-28 shrink-0">
              {user.avatar_url ? (
                <Image
                  src={user.avatar_url}
                  alt={user.full_name}
                  width={112}
                  height={112}
                  className="h-28 w-28 rounded-3xl object-cover shadow-lg ring-1 ring-slate-200 dark:ring-white/[0.08]"
                />
              ) : (
                <div className="flex h-28 w-28 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-3xl font-black text-white shadow-lg shadow-blue-500/25">
                  {initials}
                </div>
              )}

              <button
                type="button"
                className="absolute -bottom-1 -right-1 flex h-9 w-9 items-center justify-center rounded-2xl border border-slate-200 bg-white text-blue-600 shadow-md transition hover:bg-blue-50 dark:border-white/[0.08] dark:bg-slate-800 dark:text-blue-300 dark:hover:bg-white/[0.06]"
              >
                <Camera className="h-4 w-4" />
              </button>
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  {user.full_name}
                </h1>

                <CheckCircle2 className="h-5 w-5 text-blue-500" />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm font-medium text-slate-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-1.5">
                  <AtSign className="h-4 w-4" />
                  {user.username}
                </span>

                <span className="inline-flex items-center gap-1.5">
                  <Mail className="h-4 w-4" />
                  {user.email ?? "Chưa cập nhật email"}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ring-1 ${currentStatus.className}`}
                >
                  {currentStatus.label}
                </span>

                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                  User ID #{user.id}
                </span>

                <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-bold text-violet-700 ring-1 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20">
                  {authUser?.roles?.[0] ?? "Member"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row lg:items-center">
            <button
              type="button"
              onClick={handleCancel}
              className="inline-flex h-11 items-center justify-center rounded-2xl border border-slate-200 bg-white px-5 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-200 dark:hover:bg-white/[0.07]"
            >
              Hủy bỏ
            </button>

            <Button form="profile-form" type="submit" disabled={savingProfile}>
              <Save className="mr-2 h-4 w-4" />
              {savingProfile ? "Đang lưu..." : "Lưu thay đổi"}
            </Button>
          </div>
        </div>
      </section>

      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/[0.08] dark:bg-slate-900">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-black text-slate-900 dark:text-white">
              Thông tin cá nhân
            </h2>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Cập nhật thông tin cơ bản của tài khoản đang đăng nhập.
            </p>
          </div>

          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
            <UserRound className="h-5 w-5" />
          </div>
        </div>

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
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-100 dark:focus:bg-white/[0.06]"
                placeholder="Nhập họ và tên"
              />
            </FormField>

            <FormField label="Email" icon={<Mail className="h-4 w-4" />}>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-100 dark:focus:bg-white/[0.06]"
                placeholder="Nhập email"
              />
            </FormField>

            <FormField
              label="Số điện thoại"
              icon={<Phone className="h-4 w-4" />}
            >
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-100 dark:focus:bg-white/[0.06]"
                placeholder="Nhập số điện thoại"
              />
            </FormField>

            <FormField
              label="Tên đăng nhập"
              icon={<AtSign className="h-4 w-4" />}
            >
              <input
                value={user.username}
                disabled
                className="h-12 w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-4 text-sm font-semibold text-slate-500 outline-none dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-slate-400"
              />
            </FormField>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <FormField
              label="Ngày tạo tài khoản"
              icon={<CalendarDays className="h-4 w-4" />}
            >
              <input
                value={formatDateTime(user.created_at)}
                disabled
                className="h-12 w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-4 text-sm font-semibold text-slate-500 outline-none dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-slate-400"
              />
            </FormField>

            <FormField
              label="Đăng nhập gần nhất"
              icon={<ShieldCheck className="h-4 w-4" />}
            >
              <input
                value={
                  user.last_login_at
                    ? formatDateTime(user.last_login_at)
                    : "Chưa có dữ liệu"
                }
                disabled
                className="h-12 w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-4 text-sm font-semibold text-slate-500 outline-none dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-slate-400"
              />
            </FormField>
          </div>
        </form>
      </section>

      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/[0.08] dark:bg-slate-900">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-black text-slate-900 dark:text-white">
              Đổi mật khẩu
            </h2>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Cập nhật mật khẩu đăng nhập để bảo vệ tài khoản của bạn.
            </p>
          </div>

          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300">
            <LockKeyhole className="h-5 w-5" />
          </div>
        </div>

        <form onSubmit={handleSubmitPassword} className="space-y-5">
          <div className="grid gap-5 md:grid-cols-3">
            <PasswordField
              label="Mật khẩu hiện tại"
              value={currentPassword}
              onChange={setCurrentPassword}
              show={showCurrentPassword}
              onToggleShow={() => setShowCurrentPassword((v) => !v)}
              placeholder="Nhập mật khẩu hiện tại"
            />

            <PasswordField
              label="Mật khẩu mới"
              value={newPassword}
              onChange={setNewPassword}
              show={showNewPassword}
              onToggleShow={() => setShowNewPassword((v) => !v)}
              placeholder="Nhập mật khẩu mới"
            />

            <PasswordField
              label="Xác nhận mật khẩu"
              value={confirmPassword}
              onChange={setConfirmPassword}
              show={showConfirmPassword}
              onToggleShow={() => setShowConfirmPassword((v) => !v)}
              placeholder="Nhập lại mật khẩu mới"
            />
          </div>

          <div className="flex flex-col gap-3 rounded-3xl bg-slate-50 p-4 dark:bg-white/[0.04] md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                <KeyRound className="h-4 w-4" />
              </div>

              <div>
                <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  Lưu ý bảo mật
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Mật khẩu mới nên có ít nhất 6 ký tự. Sau này có thể nâng lên
                  yêu cầu chữ hoa, số và ký tự đặc biệt.
                </p>
              </div>
            </div>

            <Button type="submit" disabled={savingPassword}>
              {savingPassword ? "Đang đổi..." : "Đổi mật khẩu"}
            </Button>
          </div>
        </form>
      </section>
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
      <label className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <span className="text-blue-500 dark:text-blue-300">{icon}</span>
        {label}
      </label>

      {children}
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
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggleShow: () => void;
  placeholder: string;
}) {
  return (
    <FormField label={label} icon={<LockKeyhole className="h-4 w-4" />}>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 pr-12 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-100 dark:focus:bg-white/[0.06]"
          placeholder={placeholder}
        />

        <button
          type="button"
          onClick={onToggleShow}
          className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/[0.06] dark:hover:text-slate-200"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </FormField>
  );
}
