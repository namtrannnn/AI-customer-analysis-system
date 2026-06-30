/**
 * StatCard — reusable stat display card
 * Dùng ở: Dashboard, Customers page, Video Analysis result
 */
import React from "react";

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  /** Tailwind gradient e.g. "from-blue-500 to-cyan-500" */
  gradient: string;
  trend?: {
    value: string;
    up: boolean;
  };
}

export default function StatCard({
  label,
  value,
  sub,
  icon,
  gradient,
  trend,
}: StatCardProps) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl p-5 transition-all hover:-translate-y-0.5 hover:shadow-md"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Decorative bg circle */}
      <div
        className={`absolute -right-3 -top-3 h-16 w-16 rounded-full bg-gradient-to-br ${gradient} opacity-10`}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            {label}
          </p>

          <p
            className="mt-1.5 text-2xl font-extrabold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {value}
          </p>

          {sub && (
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
              {sub}
            </p>
          )}

          {trend && (
            <div
              className={`mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
                trend.up
                  ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                  : "bg-red-50 text-red-500 dark:bg-red-900/20 dark:text-red-400"
              }`}
            >
              <svg
                className={`h-2.5 w-2.5 ${trend.up ? "" : "rotate-180"}`}
                viewBox="0 0 12 12"
                fill="currentColor"
              >
                <path d="M6 2l4 6H2l4-6z" />
              </svg>
              {trend.value}
            </div>
          )}
        </div>

        {/* Icon box */}
        <div
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-md`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}
