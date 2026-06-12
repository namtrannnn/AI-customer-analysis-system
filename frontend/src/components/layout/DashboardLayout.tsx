"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Header from "./Header";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [collapsed, setCollapsed] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");

    if (!token) {
      router.replace("/login?reason=unauthorized");
      return;
    }

    setCheckingAuth(false);
  }, [router]);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    setCollapsed(saved === "true");
  }, []);

  const handleToggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  };

  if (checkingAuth) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: "var(--bg-page)" }}
      >
        <p className="text-sm text-slate-500">Đang kiểm tra đăng nhập...</p>
      </div>
    );
  }

  return (
    <div
      className="relative min-h-screen transition-colors duration-200"
      style={{ backgroundColor: "var(--bg-page)" }}
    >
      <Sidebar collapsed={collapsed} onToggle={handleToggleSidebar} />
      <Header collapsed={collapsed} />

      <main
        className={`relative pt-16 transition-[margin-left] duration-300 ease-in-out ${
          collapsed ? "ml-20" : "ml-64"
        }`}
      >
        <div
          key={pathname}
          className="content-enter min-h-[calc(100vh-64px)] p-6"
        >
          {children}
        </div>
      </main>
    </div>
  );
}
