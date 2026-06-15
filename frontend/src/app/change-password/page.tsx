"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { changePassword } from "@/services/auth.service";
import {
  validateChangePassword,
  type ChangePasswordErrors,
} from "@/validations/auth.schema";

export default function ChangePasswordPage() {
  const router = useRouter();

  const [values, setValues] = useState({
    old_password: "",
    new_password: "",
    confirm_password: "",
  });

  const [errors, setErrors] = useState<ChangePasswordErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const set =
    (field: "old_password" | "new_password" | "confirm_password") =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setValues((prev) => ({ ...prev, [field]: e.target.value }));

      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }

      setApiError(null);
      setSuccess(null);
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errs = validateChangePassword(values);

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    setApiError(null);
    setSuccess(null);

    try {
      await changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
        confirm_password: values.confirm_password,
      });

      setSuccess("Đổi mật khẩu thành công. Đang chuyển vào hệ thống...");

      setTimeout(() => {
        router.push("/dashboard");
      }, 700);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Đổi mật khẩu thất bại");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex h-screen items-center justify-center overflow-hidden bg-slate-50 px-4 py-4 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-blue-500/20 blur-3xl dark:bg-blue-500/15" />
      <div className="pointer-events-none absolute bottom-[-140px] right-[-120px] h-[360px] w-[360px] rounded-full bg-violet-500/20 blur-3xl dark:bg-violet-500/15" />
      <div className="pointer-events-none absolute left-[-120px] top-1/3 h-[320px] w-[320px] rounded-full bg-cyan-500/10 blur-3xl" />

      <div
        className="pointer-events-none absolute inset-0 opacity-[0.35] dark:opacity-[0.08]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.16) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,0.16) 1px,transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      <section className="relative grid h-[calc(100vh-32px)] w-full max-w-5xl overflow-hidden rounded-[2rem] border border-slate-200 bg-white/85 shadow-2xl shadow-slate-300/50 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-900/85 dark:shadow-black/40 lg:grid-cols-[0.95fr_1.05fr]">
        {" "}
        <div className="hidden h-full flex-col justify-between bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-700 p-7 text-white lg:flex">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold ring-1 ring-white/20">
              <Sparkles className="h-3.5 w-3.5" />
              First Login Security
            </div>

            <div className="mt-7 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 shadow-lg ring-1 ring-white/20">
              <BarChart3 className="h-7 w-7" strokeWidth={2.2} />
            </div>

            <h1 className="mt-6 max-w-sm text-3xl font-black leading-tight tracking-tight">
              Thiết lập mật khẩu an toàn
            </h1>

            <p className="mt-4 max-w-md text-sm leading-6 text-blue-50/90">
              Vì lý do bảo mật, tài khoản đăng nhập lần đầu cần đổi mật khẩu tạm
              thời trước khi truy cập hệ thống.
            </p>
          </div>

          <div className="grid gap-3">
            <FeatureItem text="Không sử dụng lại mật khẩu tạm thời" />
            <FeatureItem text="Mật khẩu mới nên có ít nhất 8 ký tự" />
            <FeatureItem text="Sau khi đổi mật khẩu sẽ vào Dashboard" />
          </div>
        </div>
        <div className="flex h-full min-h-0 items-center justify-center p-5 sm:p-6">
          {" "}
          <div className="w-full max-w-sm py-4">
            <div className="mb-6 text-center lg:hidden">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-white shadow-lg shadow-blue-500/25">
                <KeyRound className="h-7 w-7" />
              </div>

              <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                Đổi mật khẩu
              </h1>

              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Thiết lập mật khẩu mới cho tài khoản
              </p>
            </div>

            <div className="mb-4 hidden lg:block">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                  <LockKeyhole className="h-5 w-5" />
                </div>

                <div>
                  <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                    Đổi mật khẩu
                  </h2>
                  <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                    Cập nhật mật khẩu trước khi vào hệ thống.
                  </p>
                </div>
              </div>
            </div>

            <AlertBox
              type="info"
              message="Nếu đây là lần đầu đăng nhập, bạn cần đổi mật khẩu tạm thời để tiếp tục sử dụng hệ thống."
            />

            <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-3">
              <Input
                label="Mật khẩu hiện tại"
                type="password"
                placeholder="Nhập mật khẩu hiện tại"
                value={values.old_password}
                onChange={set("old_password")}
                error={errors.old_password}
                required
                autoComplete="current-password"
              />

              <Input
                label="Mật khẩu mới"
                type="password"
                placeholder="Nhập mật khẩu mới"
                value={values.new_password}
                onChange={set("new_password")}
                error={errors.new_password}
                required
                autoComplete="new-password"
              />

              <Input
                label="Nhập lại mật khẩu mới"
                type="password"
                placeholder="Nhập lại mật khẩu mới"
                value={values.confirm_password}
                onChange={set("confirm_password")}
                error={errors.confirm_password}
                required
                autoComplete="new-password"
              />

              {apiError && <AlertBox type="error" message={apiError} />}

              {success && <AlertBox type="success" message={success} />}

              <Button
                type="submit"
                className="h-11 w-full justify-center rounded-2xl"
                loading={loading}
              >
                <span className="inline-flex items-center gap-2">
                  <KeyRound className="h-4 w-4" />
                  Đổi mật khẩu
                </span>
              </Button>

              <button
                type="button"
                onClick={() => router.push("/login")}
                className="flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
              >
                <ArrowLeft className="h-4 w-4" />
                Quay lại đăng nhập
              </button>
            </form>

            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-3 dark:border-slate-700 dark:bg-slate-800/50">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                  <ShieldCheck className="h-4 w-4" />
                </div>

                <div>
                  <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
                    Gợi ý bảo mật
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Dùng ít nhất 8 ký tự, có chữ hoa, chữ thường, số và ký tự
                    đặc biệt.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function FeatureItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white/10 px-4 py-3 ring-1 ring-white/15">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/15">
        <ShieldCheck className="h-4 w-4" />
      </div>

      <p className="text-sm font-semibold text-white/90">{text}</p>
    </div>
  );
}

function AlertBox({
  type,
  message,
}: {
  type: "info" | "error" | "success";
  message: string;
}) {
  const config = {
    info: {
      icon: <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />,
      className:
        "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300",
    },
    error: {
      icon: <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />,
      className:
        "border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300",
    },
    success: {
      icon: <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />,
      className:
        "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300",
    },
  }[type];

  return (
    <div
      className={`flex items-start gap-2.5 rounded-2xl border px-3.5 py-3 text-sm font-medium ${config.className}`}
      role="alert"
    >
      {config.icon}
      <span>{message}</span>
    </div>
  );
}
