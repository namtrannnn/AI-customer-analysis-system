"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
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
    <div
      className="flex min-h-screen items-center justify-center px-4 transition-colors"
      style={{ background: "var(--bg-page)" }}
    >
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-blue-600">AI Customer</h1>
          <p className="mt-1 text-sm text-slate-500">
            Hệ thống phân tích khách hàng
          </p>
        </div>

        <div
          className="rounded-2xl p-8 shadow-xl"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-xl)",
          }}
        >
          <h2
            className="mb-6 text-lg font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Đăng nhập
          </h2>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <Input
              label="Tên đăng nhập"
              placeholder="admin"
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
              placeholder="••••••••"
              value={values.password}
              onChange={set("password")}
              error={errors.password}
              required
              autoComplete="current-password"
            />

            {reason === "unauthorized" && (
              <div className="mb-4 rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-700">
                Bạn cần đăng nhập để truy cập trang này.
              </div>
            )}

            {apiError && (
              <div className="rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-600">
                {apiError}
              </div>
            )}

            <Button
              type="submit"
              className="w-full justify-center"
              loading={loading}
            >
              Đăng nhập
            </Button>
          </form>

          <div
            className="mt-5 rounded-xl px-3 py-3"
            style={{
              background: "var(--bg-surface-2)",
              border: "1px solid var(--border)",
            }}
          >
            <p
              className="mb-1.5 text-xs font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              Tài khoản demo:
            </p>

            {[
              { username: "admin", label: "Quản trị viên" },
              { username: "manager01", label: "Quản lý" },
              { username: "staff01", label: "Nhân viên" },
            ].map((acc) => (
              <button
                key={acc.username}
                type="button"
                onClick={() => {
                  setValues({
                    username: acc.username,
                    password: "password123",
                  });
                  setErrors({});
                  setApiError(null);
                }}
                className="mt-0.5 block text-xs text-blue-600 hover:underline"
              >
                {acc.username} — {acc.label}
              </button>
            ))}

            <p className="mt-1 text-xs text-slate-400">
              Dùng tài khoản do Admin cấp từ backend
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div
          className="flex min-h-screen items-center justify-center px-4"
          style={{ background: "var(--bg-page)" }}
        >
          <p className="text-sm text-slate-500">Đang tải đăng nhập...</p>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
