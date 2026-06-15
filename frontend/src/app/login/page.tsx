"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  BarChart3,
  LockKeyhole,
  LogIn,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { login } from "@/services/auth.service";
import { validateLogin } from "@/validations/auth.schema";
import type { LoginErrors } from "@/validations/auth.schema";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  const [values, setValues] = useState({ username: "", password: "" });
  const [errors, setErrors] = useState<LoginErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const set =
    (field: "username" | "password") =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setValues((prev) => ({ ...prev, [field]: e.target.value }));

      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }

      setApiError(null);
    };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errs = validateLogin(values);

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    setApiError(null);

    try {
      const response = await login(values);

      if (response.is_first_login) {
        router.push("/change-password");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 px-4 py-10 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
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

      <section className="relative grid w-full max-w-5xl overflow-hidden rounded-[2rem] border border-slate-200 bg-white/85 shadow-2xl shadow-slate-300/50 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-900/85 dark:shadow-black/40 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="hidden min-h-[560px] flex-col justify-between bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-700 p-8 text-white lg:flex">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold ring-1 ring-white/20">
              <Sparkles className="h-3.5 w-3.5" />
              AI Customer Analysis
            </div>

            <div className="mt-8 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 shadow-lg ring-1 ring-white/20">
              <BarChart3 className="h-7 w-7" strokeWidth={2.2} />
            </div>

            <h1 className="mt-6 max-w-sm text-4xl font-black leading-tight tracking-tight">
              Hệ thống phân tích khách hàng bằng AI
            </h1>

            <p className="mt-4 max-w-md text-sm leading-6 text-blue-50/90">
              Quản lý khách hàng, người dùng, nhóm quyền và dữ liệu phân tích
              trong một hệ thống tập trung.
            </p>
          </div>

          <div className="grid gap-3">
            <FeatureItem text="Quản lý khách hàng và lịch sử tương tác" />
            <FeatureItem text="Phân quyền người dùng theo vai trò" />
            <FeatureItem text="Theo dõi dữ liệu vận hành qua dashboard" />
          </div>
        </div>

        <div className="flex min-h-[560px] items-center justify-center p-6 sm:p-8">
          <div className="w-full max-w-sm">
            <div className="mb-8 text-center lg:hidden">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-white shadow-lg shadow-blue-500/25">
                <BarChart3 className="h-7 w-7" />
              </div>

              <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                AI Customer
              </h1>

              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Hệ thống phân tích khách hàng
              </p>
            </div>

            <div className="mb-6 hidden lg:block">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                  <LockKeyhole className="h-5 w-5" />
                </div>

                <div>
                  <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                    Đăng nhập
                  </h2>
                  <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                    Nhập tài khoản để truy cập hệ thống.
                  </p>
                </div>
              </div>
            </div>

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <Input
                label="Tên đăng nhập"
                placeholder="Nhập tên đăng nhập"
                value={values.username}
                onChange={set("username")}
                error={errors.username}
                required
                autoFocus
                autoComplete="username"
              />

              <Input
                label="Mật khẩu"
                type="password"
                placeholder="Nhập mật khẩu"
                value={values.password}
                onChange={set("password")}
                error={errors.password}
                required
                autoComplete="current-password"
              />

              {reason === "unauthorized" && (
                <AlertBox
                  type="warning"
                  message="Bạn cần đăng nhập để truy cập trang này."
                />
              )}

              {apiError && <AlertBox type="error" message={apiError} />}

              <Button
                type="submit"
                className="h-11 w-full justify-center rounded-2xl"
                loading={loading}
              >
                <span className="inline-flex items-center gap-2">
                  <LogIn className="h-4 w-4" />
                  Đăng nhập
                </span>
              </Button>
            </form>

            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-800/50">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300">
                  <ShieldCheck className="h-4 w-4" />
                </div>

                <div>
                  <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
                    Tài khoản hệ thống
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Tài khoản được cấp bởi quản trị viên. Nếu quên mật khẩu, vui
                    lòng liên hệ người quản trị để được hỗ trợ.
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
  type: "warning" | "error";
  message: string;
}) {
  const config = {
    warning: {
      className:
        "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300",
    },
    error: {
      className:
        "border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300",
    },
  }[type];

  return (
    <div
      className={`flex items-start gap-2.5 rounded-2xl border px-3.5 py-3 text-sm font-medium ${config.className}`}
      role="alert"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
          <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm font-semibold text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            Đang tải đăng nhập...
          </div>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
