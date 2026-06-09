"use client";

import { useRef, useEffect, useState } from "react";
import { useTheme } from "./ThemeProvider";
import { useIsDark } from "@/hooks/useIsDark";

const SunIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
  </svg>
);

const MoonIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
  </svg>
);

// ─── Dropdown chỉ có Sáng / Tối ──────────────────────────────────────────────
export function ThemeToggleDropdown() {
  const { setTheme } = useTheme();
  const isDark = useIsDark();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Đổi giao diện"
        className={`relative flex h-9 w-9 items-center justify-center rounded-xl transition-colors ${
          isDark
            ? "text-amber-400 hover:bg-white/10"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        }`}
      >
        {/* Sun — hiện khi dark */}
        <span className={`absolute transition-all duration-200 ${isDark ? "scale-100 opacity-100 rotate-0" : "scale-50 opacity-0 -rotate-90"}`}>
          <SunIcon className="h-[18px] w-[18px]" />
        </span>
        {/* Moon — hiện khi light */}
        <span className={`absolute transition-all duration-200 ${isDark ? "scale-50 opacity-0 rotate-90" : "scale-100 opacity-100 rotate-0"}`}>
          <MoonIcon className="h-[18px] w-[18px]" />
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className={`absolute right-0 top-full z-50 mt-2 w-36 overflow-hidden rounded-xl border py-1.5 shadow-xl ${
          isDark
            ? "border-white/10 bg-slate-800 shadow-black/40"
            : "border-slate-200 bg-white shadow-slate-200/60"
        }`}>
          <p className={`px-3 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider ${
            isDark ? "text-slate-500" : "text-slate-400"
          }`}>
            Giao diện
          </p>

          {/* Sáng */}
          <button
            onClick={() => { setTheme("light"); setOpen(false); }}
            className={`flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
              !isDark
                ? isDark ? "bg-blue-600/20 text-blue-400" : "bg-blue-50 text-blue-700"
                : isDark ? "text-slate-300 hover:bg-white/8 hover:text-white" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <SunIcon className="h-4 w-4 shrink-0" />
            <span>Sáng</span>
            {!isDark && (
              <svg className="ml-auto h-3.5 w-3.5 shrink-0 text-blue-600" viewBox="0 0 16 16" fill="currentColor">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
              </svg>
            )}
          </button>

          {/* Tối */}
          <button
            onClick={() => { setTheme("dark"); setOpen(false); }}
            className={`flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
              isDark
                ? "bg-blue-600/20 text-blue-400"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <MoonIcon className="h-4 w-4 shrink-0" />
            <span>Tối</span>
            {isDark && (
              <svg className="ml-auto h-3.5 w-3.5 shrink-0 text-blue-400" viewBox="0 0 16 16" fill="currentColor">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
              </svg>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// Giữ export ThemeToggleSimple để không break nơi nào dùng
export function ThemeToggleSimple() {
  const { toggleTheme } = useTheme();
  const isDark = useIsDark();

  return (
    <button
      onClick={toggleTheme}
      aria-label={isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      className={`relative flex h-9 w-9 items-center justify-center rounded-xl transition-colors ${
        isDark ? "text-amber-400 hover:bg-white/10" : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
      }`}
    >
      <span className={`absolute transition-all duration-200 ${isDark ? "scale-100 opacity-100 rotate-0" : "scale-50 opacity-0 -rotate-90"}`}>
        <SunIcon className="h-[18px] w-[18px]" />
      </span>
      <span className={`absolute transition-all duration-200 ${isDark ? "scale-50 opacity-0 rotate-90" : "scale-100 opacity-100 rotate-0"}`}>
        <MoonIcon className="h-[18px] w-[18px]" />
      </span>
    </button>
  );
}
