"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Bell, ChevronDown, FileText } from "lucide-react";
import { ThemeToggleSimple } from "./ThemeToggle";

import { getCurrentUser, logout } from "@/services/auth.service";
import { useIsDark } from "@/hooks/useIsDark";
import { routeLabels } from "@/config/routeLabels.config";
import { userMenuItems } from "@/config/userMenu.config";
import type { AuthUser } from "@/types/auth.type";

function useBreadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return [{ href: "/dashboard", label: "Tổng quan", isLast: true }];
  }

  return segments.map((seg, idx) => {
    const href = "/" + segments.slice(0, idx + 1).join("/");
    const label = routeLabels[seg] ?? (seg.match(/^\d+$/) ? `#${seg}` : seg);

    return {
      href,
      label,
      isLast: idx === segments.length - 1,
    };
  });
}

// function SearchBox() {
//   const isDark = useIsDark();

//   return (
//     <button
//       type="button"
//       className={`group hidden h-10 min-w-[260px] items-center justify-between gap-3 rounded-2xl border px-3.5 text-sm shadow-sm transition-all duration-200 lg:flex ${
//         isDark
//           ? "border-white/[0.08] bg-white/[0.04] text-slate-400 hover:border-blue-400/30 hover:bg-white/[0.07]"
//           : "border-slate-200/80 bg-slate-50/80 text-slate-400 hover:border-blue-200 hover:bg-white hover:shadow-md"
//       }`}
//     >
//       <span className="flex items-center gap-2">
//         <Search
//           className={`h-4 w-4 transition-colors ${
//             isDark
//               ? "text-slate-500 group-hover:text-blue-400"
//               : "text-slate-400 group-hover:text-blue-500"
//           }`}
//         />
//         <span>Tìm kiếm khách hàng, người dùng...</span>
//       </span>

//       <kbd
//         className={`rounded-lg border px-1.5 py-0.5 text-[10px] font-semibold ${
//           isDark
//             ? "border-white/[0.08] bg-white/[0.06] text-slate-500"
//             : "border-slate-200 bg-white text-slate-400"
//         }`}
//       >
//         Ctrl K
//       </kbd>
//     </button>
//   );
// }

function NotificationBell() {
  const isDark = useIsDark();

  return (
    <button
      aria-label="Thông báo"
      className={`group relative flex h-10 w-10 items-center justify-center rounded-2xl border transition-all duration-200 ${
        isDark
          ? "border-white/[0.08] bg-white/[0.04] text-slate-400 hover:border-blue-400/30 hover:bg-white/[0.08] hover:text-slate-100"
          : "border-slate-200/80 bg-white/70 text-slate-500 hover:border-blue-200 hover:bg-white hover:text-slate-800 hover:shadow-md"
      }`}
    >
      <Bell className="h-[18px] w-[18px] transition-transform duration-200 group-hover:-rotate-12" />

      <span
        className={`absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ${
          isDark ? "ring-[#0a0f1e]" : "ring-white"
        }`}
      />

      <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 animate-ping rounded-full bg-red-400 opacity-60" />
    </button>
  );
}

function UserMenu({
  user,
  onLogout,
}: {
  user: AuthUser | null;
  onLogout: () => void;
}) {
  const isDark = useIsDark();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", h);

    return () => document.removeEventListener("mousedown", h);
  }, []);

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((w) => w[0])
        .slice(-2)
        .join("")
        .toUpperCase()
    : "?";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`group flex h-10 items-center gap-2 rounded-2xl border py-1 pl-1 pr-2 transition-all duration-200 ${
          isDark
            ? "border-white/[0.08] bg-white/[0.04] hover:border-blue-400/30 hover:bg-white/[0.08]"
            : "border-slate-200/80 bg-white/70 hover:border-blue-200 hover:bg-white hover:shadow-md"
        }`}
      >
        <div className="relative">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-xs font-bold text-white shadow-md shadow-blue-500/20">
            {initials}
          </div>

          <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500 dark:border-slate-900" />
        </div>

        <div className="hidden max-w-[150px] text-left sm:block">
          <p
            className={`truncate text-sm font-bold leading-none ${
              isDark ? "text-slate-100" : "text-slate-800"
            }`}
          >
            {user?.full_name ?? "Người dùng"}
          </p>

          <p className="mt-1 truncate text-[11px] font-medium text-slate-400">
            {user?.role?.role_name ?? "Member"}
          </p>
        </div>

        <ChevronDown
          className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div
          className={`absolute right-0 top-full z-50 mt-3 w-72 overflow-hidden rounded-3xl border p-2 shadow-2xl backdrop-blur-xl ${
            isDark
              ? "border-white/[0.08] bg-slate-900/95 shadow-black/50"
              : "border-slate-200/80 bg-white/95 shadow-slate-300/40"
          }`}
        >
          <div
            className={`rounded-2xl p-3 ${
              isDark
                ? "bg-gradient-to-br from-blue-500/10 to-indigo-500/10"
                : "bg-gradient-to-br from-blue-50 to-indigo-50"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-sm font-bold text-white shadow-lg shadow-blue-500/25">
                {initials}
              </div>

              <div className="min-w-0">
                <p
                  className={`truncate text-sm font-bold ${
                    isDark ? "text-slate-100" : "text-slate-900"
                  }`}
                >
                  {user?.full_name ?? "Người dùng"}
                </p>

                <p className="truncate text-xs text-slate-400">
                  {user?.email ?? user?.username ?? "No email"}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-2 space-y-1">
            {userMenuItems.map((item) => {
              const Icon = item.icon;

              if (item.type === "logout") {
                return (
                  <button
                    key={item.label}
                    onClick={() => {
                      setOpen(false);
                      onLogout();
                    }}
                    className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-red-500 transition-colors hover:bg-red-500/10"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-red-500/10">
                      <Icon className="h-4 w-4" />
                    </span>

                    {item.label}
                  </button>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href ?? "#"}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-colors ${
                    isDark
                      ? "text-slate-300 hover:bg-white/[0.07] hover:text-white"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-xl ${
                      isDark ? "bg-white/[0.06]" : "bg-slate-100"
                    }`}
                  >
                    <Icon className="h-4 w-4 text-slate-400" />
                  </span>

                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Header({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const breadcrumbs = useBreadcrumbs();
  const [user, setUser] = useState<AuthUser | null>(null);
  const isDark = useIsDark();

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const currentPage = breadcrumbs[breadcrumbs.length - 1]?.label ?? "Dashboard";

  return (
    <header
      className={`fixed right-0 top-0 z-20 border-b px-6 backdrop-blur-2xl transition-[left,background-color,border-color,box-shadow] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        collapsed ? "left-20" : "left-64"
      }`}
      style={{
        backgroundColor: "var(--header-bg)",
        borderColor: "var(--header-border)",
        boxShadow: "var(--header-shadow)",
      }}
    >
      <div className="flex h-16 items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <div className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg shadow-blue-500/20 md:flex">
            <FileText className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <h1
                className={`truncate text-base font-semibold tracking-tight md:text-lg ${
                  isDark ? "text-slate-100" : "text-slate-900"
                }`}
              >
                {currentPage}
              </h1>

              <span
                className={`hidden rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide md:inline-flex ${
                  isDark
                    ? "bg-blue-500/15 text-blue-300"
                    : "bg-blue-50 text-blue-600"
                }`}
              >
                AI System
              </span>
            </div>

            <nav
              className="flex items-center gap-1.5 text-xs"
              aria-label="Breadcrumb"
            >
              <Link
                href="/dashboard"
                className={`transition-colors ${
                  isDark
                    ? "text-slate-500 hover:text-slate-300"
                    : "text-slate-400 hover:text-slate-700"
                }`}
              >
                Home
              </Link>

              {breadcrumbs.map((crumb) => (
                <span key={crumb.href} className="flex items-center gap-1.5">
                  <ChevronDown
                    className={`h-3.5 w-3.5 -rotate-90 ${
                      isDark ? "text-slate-700" : "text-slate-300"
                    }`}
                  />

                  {crumb.isLast ? (
                    <span
                      className={`font-semibold ${
                        isDark ? "text-slate-300" : "text-slate-600"
                      }`}
                    >
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className={`transition-colors ${
                        isDark
                          ? "text-slate-500 hover:text-slate-300"
                          : "text-slate-400 hover:text-slate-700"
                      }`}
                    >
                      {crumb.label}
                    </Link>
                  )}
                </span>
              ))}
            </nav>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggleSimple />

          <NotificationBell />

          <div
            className={`mx-1 hidden h-8 w-px sm:block ${
              isDark ? "bg-white/[0.08]" : "bg-slate-200/80"
            }`}
          />

          <UserMenu user={user} onLogout={handleLogout} />
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
    </header>
  );
}
