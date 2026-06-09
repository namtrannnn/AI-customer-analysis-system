"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getCurrentUser } from "@/services/auth.service";
import { ThemeToggleDropdown } from "./ThemeToggle";
import { useIsDark } from "@/hooks/useIsDark";
import type { AuthUser } from "@/types/auth.type";

const routeLabels: Record<string, string> = {
  dashboard: "Tổng quan",
  customers: "Khách hàng",
  users: "Người dùng",
  roles: "Nhóm quyền",
  permissions: "Phân quyền",
};

function useBreadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return [{ href: "/dashboard", label: "Tổng quan", isLast: true }];
  }

  return segments.map((seg, idx) => {
    const href = "/" + segments.slice(0, idx + 1).join("/");
    const label = routeLabels[seg] ?? (seg.match(/^\d+$/) ? `#${seg}` : seg);
    return { href, label, isLast: idx === segments.length - 1 };
  });
}

function SearchBox() {
  const isDark = useIsDark();

  return (
    <button
      type="button"
      className={`group hidden h-10 min-w-[260px] items-center justify-between gap-3 rounded-2xl border px-3.5 text-sm shadow-sm transition-all duration-200 lg:flex ${
        isDark
          ? "border-white/[0.08] bg-white/[0.04] text-slate-400 hover:border-blue-400/30 hover:bg-white/[0.07]"
          : "border-slate-200/80 bg-slate-50/80 text-slate-400 hover:border-blue-200 hover:bg-white hover:shadow-md"
      }`}
    >
      <span className="flex items-center gap-2">
        <svg
          className={`h-4 w-4 transition-colors ${
            isDark
              ? "text-slate-500 group-hover:text-blue-400"
              : "text-slate-400 group-hover:text-blue-500"
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"
          />
        </svg>
        <span>Tìm kiếm khách hàng, người dùng...</span>
      </span>

      <kbd
        className={`rounded-lg border px-1.5 py-0.5 text-[10px] font-semibold ${
          isDark
            ? "border-white/[0.08] bg-white/[0.06] text-slate-500"
            : "border-slate-200 bg-white text-slate-400"
        }`}
      >
        Ctrl K
      </kbd>
    </button>
  );
}

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
      <svg
        className="h-[18px] w-[18px] transition-transform duration-200 group-hover:-rotate-12"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.9}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
        />
      </svg>

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
            {user?.roles?.[0] ?? "Member"}
          </p>
        </div>

        <svg
          className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
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
            <Link
              href="/users"
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
                <svg
                  className="h-4 w-4 text-slate-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.9}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              </span>
              Tài khoản của tôi
            </Link>

            <button
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
              className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-red-500 transition-colors hover:bg-red-500/10"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-red-500/10">
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.9}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
              </span>
              Đăng xuất
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Header({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const breadcrumbs = useBreadcrumbs();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const isDark = useIsDark();

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
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
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 7a3 3 0 013-3h10a3 3 0 013 3v10a3 3 0 01-3 3H7a3 3 0 01-3-3V7z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 9h6M9 13h6M9 17h3"
              />
            </svg>
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
                  <svg
                    className={`h-3.5 w-3.5 shrink-0 ${
                      isDark ? "text-slate-700" : "text-slate-300"
                    }`}
                    viewBox="0 0 16 16"
                    fill="currentColor"
                  >
                    <path d="M6.22 3.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 010-1.06z" />
                  </svg>

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
          <SearchBox />

          <ThemeToggleDropdown />

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
