"use client";

import { useRouter } from "next/navigation";

export default function Header() {
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  return (
    <header className="fixed left-64 right-0 top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <h2 className="text-base font-semibold text-slate-900">
          Hệ thống phân tích khách hàng
        </h2>
        <p className="text-xs text-slate-500">
          Quản lý khách hàng, nhận diện và thống kê hành vi mua sắm
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm font-medium text-slate-900">Admin</p>
          <p className="text-xs text-slate-500">Quản trị viên</p>
        </div>

        <button
          onClick={handleLogout}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
