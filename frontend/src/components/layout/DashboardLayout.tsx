"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Header from "./Header";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  // Auth check chạy ngầm — KHÔNG dùng state để block render
  // Sidebar + Header luôn mount ngay, không bao giờ bị unmount/remount
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
    }
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

  return (
    <div
      className="relative min-h-screen transition-colors duration-200"
      style={{ backgroundColor: "var(--bg-page)" }}
    >
      {/* Sidebar — fixed, không bao giờ re-mount */}
      <Sidebar collapsed={collapsed} onToggle={handleToggleSidebar} />

      {/* Header — fixed, không bao giờ re-mount */}
      <Header collapsed={collapsed} />

      {/* Main — chỉ children thay đổi, wrapper không unmount */}
      <main
        className={`relative pt-16 transition-[margin-left] duration-300 ease-in-out ${
          collapsed ? "ml-20" : "ml-64"
        }`}
      >
        {/*
          key=pathname để React tạo DOM mới cho children khi navigate
          animation chỉ chạy trên div này, Sidebar/Header không bị ảnh hưởng
        */}
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
