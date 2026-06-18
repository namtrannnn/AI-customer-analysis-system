"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Bell, ChevronDown, FileText } from "lucide-react";
import { ThemeToggleSimple } from "./ThemeToggle";
import Image from "next/image";

import { logout } from "@/services/auth.service";
import { routeLabels } from "@/config/routeLabels.config";
import { userMenuItems } from "@/config/userMenu.config";
import type { AuthUser } from "@/types/auth.type";
import { getUser } from "@/utils/storage";

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
//

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
  return (
    <button
      aria-label="Thông báo"
      className="group relative flex h-10 w-10 items-center justify-center rounded-2xl border border-theme surface text-secondary transition-all duration-200 hover:bg-[var(--bg-surface-2)] hover:text-[var(--text-primary)] hover:shadow-md"
    >
      <Bell className="h-[18px] w-[18px] transition-transform duration-200 group-hover:-rotate-12" />

      <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-[var(--bg-page)]" />

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
        className="
  group flex h-10 items-center gap-2 rounded-2xl border py-1 pl-1 pr-2 transition-all duration-200

  border-slate-200/80 bg-white/70
  hover:border-blue-200 hover:bg-white hover:shadow-md

  dark:border-white/[0.08]
  dark:bg-white/[0.04]
  dark:hover:border-blue-400/30
  dark:hover:bg-white/[0.08]
"
      >
        <div className="relative">
          <div className="relative h-8 w-8 overflow-hidden rounded-xl">
            {user?.avatar_url ? (
              <Image
                src={user.avatar_url}
                alt={user.full_name ?? "Avatar"}
                fill
                className="object-cover"
                sizes="32px"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-xs font-bold text-white">
                {initials}
              </div>
            )}
          </div>

          <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500 dark:border-slate-900" />
        </div>

        <div className="hidden max-w-[150px] text-left sm:block">
          <p className="truncate text-sm font-bold leading-none text-slate-800 dark:text-slate-100">
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
          className="
          absolute right-0 top-full z-50 mt-3 w-72 overflow-hidden rounded-3xl border p-2 shadow-2xl backdrop-blur-xl

          border-slate-200/80 bg-white/95 shadow-slate-300/40

          dark:border-white/[0.08]
          dark:bg-slate-900/95
          dark:shadow-black/50
        "
        >
          <div
            className="
              rounded-2xl p-3
              bg-gradient-to-br from-blue-50 to-indigo-50
              dark:from-blue-500/10 dark:to-indigo-500/10
            "
          >
            <div className="flex items-center gap-3">
              <div className="relative h-11 w-11 overflow-hidden rounded-2xl">
                {user?.avatar_url ? (
                  <Image
                    src={user.avatar_url}
                    alt={user.full_name ?? "Avatar"}
                    fill
                    className="object-cover"
                    sizes="44px"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-sm font-bold text-white">
                    {initials}
                  </div>
                )}
              </div>

              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
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
                  className="
                  flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-colors

                  text-slate-600 hover:bg-slate-100 hover:text-slate-900

                  dark:text-slate-300
                  dark:hover:bg-white/[0.07]
                  dark:hover:text-white
                "
                >
                  <span
                    className="
                    flex h-8 w-8 items-center justify-center rounded-xl
                    bg-slate-100
                    dark:bg-white/[0.06]
                  "
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

  useEffect(() => {
    const syncUser = () => {
      setUser(getUser<AuthUser>());
    };

    syncUser();

    window.addEventListener("user-updated", syncUser);

    return () => {
      window.removeEventListener("user-updated", syncUser);
    };
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
              <h1 className="text-primary truncate text-base font-semibold tracking-tight md:text-lg">
                {currentPage}
              </h1>

              <span className="hidden rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-400 md:inline-flex">
                AI System
              </span>
            </div>

            <nav
              className="flex items-center gap-1.5 text-xs"
              aria-label="Breadcrumb"
            >
              <Link
                href="/dashboard"
                className="text-muted transition-colors hover:text-[var(--text-primary)]"
              >
                Home
              </Link>

              {breadcrumbs.map((crumb) => (
                <span key={crumb.href} className="flex items-center gap-1.5">
                  <ChevronDown
                    className="h-3.5 w-3.5 -rotate-90"
                    style={{ color: "var(--text-muted)" }}
                  />

                  {crumb.isLast ? (
                    <span className="text-secondary font-semibold">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="text-muted transition-colors hover:text-[var(--text-primary)]"
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
            className="mx-1 hidden h-8 w-px sm:block"
            style={{ backgroundColor: "var(--border)" }}
          />

          <UserMenu user={user} onLogout={handleLogout} />
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
    </header>
  );
}
