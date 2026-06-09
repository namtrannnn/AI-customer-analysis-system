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
  Sparkles,
  Users,
  UserRoundCog,
} from "lucide-react";
import { useIsDark } from "@/hooks/useIsDark";

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

const itemIconColor: Record<string, { light: string; dark: string }> = {
  "/dashboard": { light: "text-blue-500", dark: "text-blue-400" },
  "/customers": { light: "text-violet-500", dark: "text-violet-400" },
  "/users": { light: "text-emerald-500", dark: "text-emerald-400" },
  "/roles": { light: "text-amber-500", dark: "text-amber-400" },
  "/permissions": { light: "text-rose-500", dark: "text-rose-400" },
};

const menuItems = [
  {
    label: "Tổng quan",
    href: "/dashboard",
    icon: LayoutDashboard,
    desc: "Dashboard",
  },
  {
    label: "Khách hàng",
    href: "/customers",
    icon: Users,
    desc: "Customer data",
  },
  {
    label: "Người dùng",
    href: "/users",
    icon: UserRoundCog,
    desc: "Accounts",
  },
  {
    label: "Nhóm quyền",
    href: "/roles",
    icon: ShieldCheck,
    desc: "Roles",
  },
  {
    label: "Phân quyền",
    href: "/permissions",
    icon: LockKeyhole,
    desc: "Permissions",
  },
];

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const isDark = useIsDark();

  return (
    <aside
      className={`fixed left-0 top-0 z-30 flex h-screen flex-col overflow-hidden transition-[width,box-shadow,background-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        collapsed ? "w-20" : "w-64"
      } ${
        isDark
          ? "border-r border-white/[0.08] shadow-2xl shadow-blue-950/30"
          : "border-r border-slate-200 shadow-xl shadow-slate-200/70"
      }`}
      style={{
        background: isDark
          ? "linear-gradient(180deg, #080f1e 0%, #0f172a 45%, #020617 100%)"
          : "linear-gradient(180deg, #ffffff 0%, #f8fafc 45%, #eef2ff 100%)",
      }}
    >
      {isDark ? (
        <>
          <div className="sidebar-glow pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-blue-500/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-indigo-500/20 blur-3xl" />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.18) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.18) 1px,transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(99,102,241,0.16)_0%,transparent_55%)]" />
        </>
      ) : (
        <>
          <div className="pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-blue-400/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-violet-400/20 blur-3xl" />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.28]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(148,163,184,0.12) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,0.12) 1px,transparent 1px)",
              backgroundSize: "28px 28px",
            }}
          />
        </>
      )}

      {/* Logo + Toggle */}
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
              className={`truncate text-[14px] font-extrabold leading-none tracking-tight ${
                isDark ? "text-white" : "text-slate-900"
              }`}
            >
              AI Customer
            </p>
            <p
              className={`mt-0.5 truncate text-[9.5px] font-semibold uppercase tracking-[0.2em] ${
                isDark ? "text-slate-500" : "text-slate-400"
              }`}
            >
              Analysis System
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          className={`absolute -right-3 top-5 z-20 flex h-7 w-7 items-center justify-center rounded-full border transition-all duration-300 hover:scale-110 active:scale-95 ${
            isDark
              ? "border-white/[0.1] bg-slate-900 text-slate-300 shadow-lg shadow-black/40 hover:bg-blue-600 hover:text-white hover:shadow-blue-500/30"
              : "border-slate-200 bg-white text-slate-500 shadow-lg shadow-slate-300/70 hover:bg-blue-600 hover:text-white hover:shadow-blue-300/60"
          }`}
        >
          <ChevronLeft
            className={`h-4 w-4 transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
              collapsed ? "rotate-180" : "rotate-0"
            }`}
            strokeWidth={2.4}
          />
        </button>
      </div>

      <div
        className={`${collapsed ? "mx-4" : "mx-5"} relative h-px`}
        style={{
          background: isDark
            ? "linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent)"
            : "linear-gradient(to right, transparent, rgba(0,0,0,0.08), transparent)",
        }}
      />

      {!collapsed && (
        <div className="relative px-4 pt-4">
          <div
            className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 ${
              isDark
                ? "border border-white/[0.08] bg-white/[0.04]"
                : "border border-slate-200 bg-white/70 shadow-sm"
            }`}
          >
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                isDark ? "bg-emerald-500/15" : "bg-emerald-50"
              }`}
            >
              <Circle
                className={`h-2.5 w-2.5 fill-emerald-400 text-emerald-400 ${
                  isDark ? "drop-shadow-[0_0_6px_rgba(52,211,153,0.8)]" : ""
                }`}
              />
            </div>

            <div className="min-w-0">
              <p
                className={`text-xs font-semibold ${
                  isDark ? "text-slate-300" : "text-slate-700"
                }`}
              >
                Mock mode
              </p>
              <p
                className={`text-[10px] ${
                  isDark ? "text-slate-600" : "text-slate-400"
                }`}
              >
                Dữ liệu thử nghiệm
              </p>
            </div>
          </div>
        </div>
      )}

      {!collapsed && (
        <p
          className={`relative px-5 pb-2 pt-5 text-[9.5px] font-bold uppercase tracking-[0.25em] ${
            isDark ? "text-slate-600" : "text-slate-400"
          }`}
        >
          Menu chính
        </p>
      )}

      <nav
        className={`relative flex-1 space-y-1 overflow-y-auto pb-4 ${
          collapsed ? "px-3 pt-5" : "px-3"
        }`}
      >
        {menuItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          const accent = itemAccent[item.href];
          const iconColor = isDark
            ? itemIconColor[item.href].dark
            : itemIconColor[item.href].light;

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
                  : isDark
                    ? "hover:bg-white/[0.06] hover:shadow-lg hover:shadow-black/20"
                    : "hover:bg-white/80 hover:shadow-md hover:shadow-slate-200/80"
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
                    : isDark
                      ? `bg-white/[0.04] ${iconColor} group-hover:bg-white/[0.1] group-hover:shadow-lg`
                      : `bg-white ${iconColor} shadow-sm ring-1 ring-slate-200/80 group-hover:shadow-md`
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
                        : isDark
                          ? "text-slate-300 group-hover:text-slate-100"
                          : "text-slate-700 group-hover:text-slate-900"
                    }`}
                  >
                    {item.label}
                  </span>

                  <span
                    className={`mt-0.5 block text-[11px] ${
                      active
                        ? "text-white/70"
                        : isDark
                          ? "text-slate-600 group-hover:text-slate-500"
                          : "text-slate-400 group-hover:text-slate-500"
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

      {/* Footer */}
      <div className="relative shrink-0 p-3">
        {collapsed ? (
          <div
            title="System Online"
            className={`mx-auto flex h-10 w-10 items-center justify-center rounded-xl ${
              isDark
                ? "border border-white/[0.08] bg-white/[0.04]"
                : "border border-slate-200 bg-white/70 shadow-sm"
            }`}
          >
            <Circle className="h-2.5 w-2.5 fill-emerald-400 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          </div>
        ) : (
          <div
            className={`rounded-xl p-3 ${
              isDark
                ? "border border-white/[0.08] bg-white/[0.03]"
                : "border border-slate-200 bg-white/70 shadow-sm"
            }`}
          >
            <div className="mb-2.5 flex items-center justify-between">
              <p
                className={`text-xs font-semibold ${
                  isDark ? "text-slate-400" : "text-slate-600"
                }`}
              >
                System health
              </p>
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-500">
                Online
              </span>
            </div>

            <div
              className={`h-1.5 overflow-hidden rounded-full ${
                isDark ? "bg-white/[0.08]" : "bg-slate-200"
              }`}
            >
              <div className="h-full w-[72%] rounded-full bg-gradient-to-r from-emerald-400 via-teal-400 to-blue-500" />
            </div>

            <p
              className={`mt-2 text-[10px] ${
                isDark ? "text-slate-700" : "text-slate-400"
              }`}
            >
              v1.0.0 · Dashboard UI
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
