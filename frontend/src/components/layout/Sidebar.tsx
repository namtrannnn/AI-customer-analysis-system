"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  ChevronLeft,
  Circle,
  LayoutDashboard,
  LockKeyhole,
  ShieldCheck,
  Users,
  UserRoundCog,
} from "lucide-react";
import { usePermission } from "@/hooks/usePermission";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const itemAccent: Record<string, string> = {
  "/dashboard": "from-blue-500 to-cyan-500",
  "/customers": "from-violet-500 to-purple-600",
  "/users": "from-emerald-500 to-teal-600",
  "/roles": "from-amber-500 to-orange-500",
  "/permissions": "from-rose-500 to-pink-600",
};

const itemIconColor: Record<string, string> = {
  "/dashboard": "text-blue-500 dark:text-blue-400",
  "/customers": "text-violet-500 dark:text-violet-400",
  "/users": "text-emerald-500 dark:text-emerald-400",
  "/roles": "text-amber-500 dark:text-amber-400",
  "/permissions": "text-rose-500 dark:text-rose-400",
};

const menuItems = [
  {
    label: "Tổng quan",
    href: "/dashboard",
    icon: LayoutDashboard,
    desc: "Dashboard",
    permission: null,
  },
  {
    label: "Khách hàng",
    href: "/customers",
    icon: Users,
    desc: "Customer data",
    permission: "customer.view",
  },
  {
    label: "Người dùng",
    href: "/users",
    icon: UserRoundCog,
    desc: "Accounts",
    permission: "user.view",
  },
  {
    label: "Nhóm quyền",
    href: "/roles",
    icon: ShieldCheck,
    desc: "Roles",
    permission: "role.view",
  },
  {
    label: "Phân quyền",
    href: "/permissions",
    icon: LockKeyhole,
    desc: "Permissions",
    permission: "permission.view",
  },
];

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { hasPermission } = usePermission();

  const visibleMenuItems = menuItems.filter((item) => {
    if (!item.permission) return true;
    return hasPermission(item.permission);
  });

  return (
    <aside
      className={`fixed left-0 top-0 z-30 flex h-screen flex-col overflow-hidden border-r border-theme transition-[width,box-shadow,background-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        collapsed ? "w-20" : "w-64"
      }`}
      style={{
        background: "var(--sidebar-gradient)",
        boxShadow: "var(--sidebar-shadow)",
      }}
    >
      <>
        <div className="sidebar-glow pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-blue-400/20 dark:bg-blue-500/20 blur-3xl" />

        <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-violet-400/20 dark:bg-indigo-500/20 blur-3xl" />

        <div
          className="pointer-events-none absolute inset-0 opacity-[0.28] dark:opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.12) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,0.12) 1px,transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        <div className="pointer-events-none absolute inset-0 hidden dark:block bg-[radial-gradient(ellipse_at_bottom_right,rgba(99,102,241,0.16)_0%,transparent_55%)]" />
      </>

      <div
        className={`relative flex h-16 shrink-0 items-center ${
          collapsed ? "justify-center px-3" : "gap-3 px-5"
        }`}
      >
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 shadow-lg shadow-blue-500/30">
          <BarChart3
            className="h-[18px] w-[18px] text-white"
            strokeWidth={2.2}
          />
          <div className="absolute inset-0 rounded-xl ring-1 ring-inset ring-white/20" />
        </div>

        {!collapsed && (
          <div className="min-w-0 overflow-hidden whitespace-nowrap">
            <p
              className={`truncate text-[14px] font-extrabold leading-none tracking-tight ${"text-slate-900 dark:text-white"}`}
            >
              AI Customer
            </p>
            <p
              className={`mt-0.5 truncate text-[9.5px] font-semibold uppercase tracking-[0.2em] ${"text-slate-400 dark:text-slate-500"}`}
            >
              Analysis System
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          className={`absolute -right-3.5 top-5 z-20 flex h-8 w-8 items-center justify-center rounded-full border backdrop-blur-xl transition-all duration-300 hover:scale-105 active:scale-95
           border-slate-200 bg-white/95 text-slate-500 shadow-lg shadow-black/40 hover:border-blue-400/40 hover:bg-blue-600 hover:text-white
               dark:border-white/10 dark:bg-slate-950/90 dark:text-slate-300" shadow-lg shadow-slate-300/70 hover:border-blue-200 hover:bg-blue-600 hover:text-white"
          }`}
        >
          <ChevronLeft
            className={`h-4 w-4 transition-transform duration-300 ${
              collapsed ? "rotate-180" : "rotate-0"
            }`}
            strokeWidth={2.6}
          />
        </button>
      </div>

      <div
        className={`${collapsed ? "mx-4" : "mx-5"} relative h-px`}
        style={{
          background:
            "linear-gradient(to right, transparent, var(--sidebar-divider), transparent)",
        }}
      />

      {!collapsed && (
        <p
          className={`relative px-5 pb-2 pt-5 text-[9.5px] font-bold uppercase tracking-[0.25em] ${"text-slate-400 dark:text-slate-600"}`}
        >
          Menu chính
        </p>
      )}

      <nav
        className={`relative flex-1 space-y-1 overflow-y-auto pb-4 ${
          collapsed ? "px-3 pt-5" : "px-3"
        }`}
      >
        {visibleMenuItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          const accent = itemAccent[item.href];
          const iconColor =
            itemIconColor[item.href] || "text-slate-500 dark:text-slate-400";

          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch
              title={collapsed ? item.label : undefined}
              className={`group relative flex items-center overflow-hidden rounded-2xl text-sm transition-all duration-300 ease-out hover:-translate-y-0.5 active:translate-y-0 ${
                collapsed
                  ? "mx-auto h-12 w-12 justify-center p-0"
                  : "gap-3 px-3 py-2.5"
              } ${
                active
                  ? "shadow-lg"
                  : "hover:bg-white/80 dark:hover:bg-white/[0.06] hover:shadow-md dark:hover:shadow-black/20"
              }`}
            >
              {active && (
                <>
                  <div
                    className={`absolute inset-0 bg-gradient-to-br ${accent} opacity-95`}
                  />
                  <div className="absolute inset-0 bg-gradient-to-b from-white/15 to-transparent" />

                  {!collapsed && (
                    <div className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-white/70 shadow-[0_0_8px_rgba(255,255,255,0.6)]" />
                  )}
                </>
              )}

              <span
                className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110 group-hover:rotate-3 ${
                  active
                    ? "bg-white/20 text-white shadow-lg shadow-black/10"
                    : `bg-white dark:bg-white/[0.04] ${iconColor} ring-1 ring-slate-200/80 dark:ring-white/10`
                }`}
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
              </span>

              {!collapsed && (
                <span className="relative min-w-0 flex-1">
                  <span
                    className={`block text-sm font-semibold leading-none ${
                      active
                        ? "text-white"
                        : "text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-slate-100"
                    }`}
                  >
                    {item.label}
                  </span>

                  <span
                    className={`mt-0.5 block text-[11px] ${
                      active
                        ? "text-white/70"
                        : "text-slate-400 dark:text-slate-600 group-hover:text-slate-500"
                    }`}
                  >
                    {item.desc}
                  </span>
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
