"use client";

import Link from "next/link";
import {
  ArrowLeft,
  Home,
  LockKeyhole,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import Button from "@/components/ui/Button";

interface ForbiddenPageProps {
  title?: string;
  description?: string;
  backHref?: string;
  backLabel?: string;
  homeHref?: string;
  showHomeButton?: boolean;
}

export default function ForbiddenPage({
  title = "Không có quyền truy cập",
  description = "Bạn không có quyền truy cập chức năng này. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền.",
  backHref,
  backLabel = "Quay lại",
  homeHref = "/dashboard",
  showHomeButton = true,
}: ForbiddenPageProps) {
  return (
    <div className="relative flex min-h-[calc(100vh-140px)] items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/2 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-red-400/10 blur-3xl dark:bg-red-500/10" />
        <div className="absolute right-10 top-10 h-40 w-40 rounded-full bg-orange-400/10 blur-3xl dark:bg-orange-500/10" />
        <div className="absolute bottom-10 left-10 h-40 w-40 rounded-full bg-blue-400/10 blur-3xl dark:bg-blue-500/10" />
      </div>

      <div className="relative w-full max-w-lg">
        <div className="rounded-[2rem] border border-red-100 bg-white/90 p-8 text-center shadow-xl shadow-slate-200/70 backdrop-blur dark:border-red-500/20 dark:bg-slate-900/90 dark:shadow-black/30">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-red-500 to-orange-500 text-white shadow-lg shadow-red-500/25">
            <LockKeyhole className="h-10 w-10" strokeWidth={2.2} />
          </div>

          <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-red-100 bg-red-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            <ShieldAlert className="h-3.5 w-3.5" />
            Access denied
          </div>

          <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            {title}
          </h1>

          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
            {description}
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            {backHref && (
              <Link href={backHref}>
                <Button variant="secondary" size="sm">
                  <ArrowLeft className="mr-1.5 h-4 w-4" />
                  {backLabel}
                </Button>
              </Link>
            )}

            {showHomeButton && (
              <Link href={homeHref}>
                <Button size="sm">
                  <Home className="mr-1.5 h-4 w-4" />
                  Về Dashboard
                </Button>
              </Link>
            )}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-400 dark:text-slate-600">
          <Sparkles className="h-3.5 w-3.5" />
          <span>AI Customer Analysis System</span>
        </div>
      </div>
    </div>
  );
}
