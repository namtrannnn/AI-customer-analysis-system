"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
    <div
      className="flex min-h-screen items-center justify-center px-4 transition-colors"
      style={{ background: "var(--bg-page)" }}
    >
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-blue-600">AI Customer</h1>
          <p className="mt-1 text-sm text-slate-500">Thiết lập mật khẩu mới</p>
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
            className="mb-2 text-lg font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Đổi mật khẩu
          </h2>

          <p className="mb-6 text-sm text-slate-500">
            Nếu đây là lần đầu đăng nhập, bạn cần đổi mật khẩu trước khi vào hệ
            thống.
          </p>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
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

            {apiError && (
              <div className="rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-600">
                {apiError}
              </div>
            )}

            {success && (
              <div className="rounded-lg bg-emerald-50 px-3 py-2.5 text-sm text-emerald-600">
                {success}
              </div>
            )}

            <Button
              type="submit"
              className="w-full justify-center"
              loading={loading}
            >
              Đổi mật khẩu
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
