"use client";

import { useRef, useEffect, useState } from "react";
import { useTheme } from "./ThemeProvider";
import { useIsDark } from "@/hooks/useIsDark";

const SunIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.8}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z"
    />
  </svg>
);

const MoonIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.8}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
    />
  </svg>
);

// ─── Dropdown chỉ có Sáng / Tối ──────────────────────────────────────────────
export function ThemeToggleSimple() {
  const { toggleTheme } = useTheme();
  const isDark = useIsDark();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={
        isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"
      }
      title={
        isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"
      }
      className={`group relative flex h-10 w-10 items-center justify-center rounded-2xl border transition-all duration-200 ${
        isDark
          ? "border-white/[0.08] bg-white/[0.04] text-amber-400 hover:border-amber-400/30 hover:bg-white/[0.08]"
          : "border-slate-200/80 bg-white/70 text-slate-500 hover:border-blue-200 hover:bg-white hover:text-slate-800 hover:shadow-md"
      }`}
    >
      <span
        className={`absolute transition-all duration-200 ${
          isDark
            ? "scale-100 rotate-0 opacity-100"
            : "scale-50 -rotate-90 opacity-0"
        }`}
      >
        <SunIcon className="h-[18px] w-[18px]" />
      </span>

      <span
        className={`absolute transition-all duration-200 ${
          isDark
            ? "scale-50 rotate-90 opacity-0"
            : "scale-100 rotate-0 opacity-100"
        }`}
      >
        <MoonIcon className="h-[18px] w-[18px]" />
      </span>
    </button>
  );
}
