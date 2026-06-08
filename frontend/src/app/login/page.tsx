"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("admin@gmail.com");
  const [password, setPassword] = useState("123456");
  const [loading, setLoading] = useState(false);

  const handleLogin = () => {
    if (!email || !password) {
      alert("Vui lòng nhập email và mật khẩu");
      return;
    }

    setLoading(true);

    setTimeout(() => {
      localStorage.setItem("token", "fake-token");
      localStorage.setItem(
        "user",
        JSON.stringify({
          id: 1,
          fullName: "Admin",
          email,
          role: "admin",
        }),
      );

      router.push("/dashboard");
      setLoading(false);
    }, 500);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900">
            AI Customer Analysis
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Đăng nhập vào hệ thống quản lý khách hàng
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              type="email"
              value={email}
              placeholder="Nhập email"
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Mật khẩu
            </label>
            <input
              type="password"
              value={password}
              placeholder="Nhập mật khẩu"
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Tài khoản test: admin@gmail.com / 123456
        </p>
      </div>
    </main>
  );
}
