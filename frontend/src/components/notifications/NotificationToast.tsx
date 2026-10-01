"use client";

import React from "react";
import { Bell, X, UserCheck, UserPlus, Volume2, VolumeX } from "lucide-react";
import { useNotification } from "@/context/NotificationContext";

export function NotificationToast() {
  const { toast, dismissToast, soundEnabled, toggleSound } = useNotification();

  if (!toast) return null;

  const isIdentified = toast.person_type === "identified";

  return (
    <div
      className="fixed right-5 z-[99999] w-80 sm:w-96"
      style={{ top: "4.5rem" }}
    >
      <div className="relative overflow-hidden rounded-2xl border shadow-2xl backdrop-blur-lg animate-in slide-in-from-top-4 fade-in duration-300"
        style={{
          borderColor: isIdentified
            ? "rgba(139, 92, 246, 0.35)"
            : "rgba(59, 130, 246, 0.35)",
          backgroundColor: "var(--bg-surface-solid, #ffffff)",
          boxShadow: isIdentified
            ? "0 20px 60px -12px rgba(139, 92, 246, 0.25), 0 8px 20px -8px rgba(0,0,0,0.15)"
            : "0 20px 60px -12px rgba(59, 130, 246, 0.25), 0 8px 20px -8px rgba(0,0,0,0.15)",
        }}
      >
        {/* Top Gradient accent bar */}
        <div
          className="absolute top-0 left-0 right-0 h-1"
          style={{
            background: isIdentified
              ? "linear-gradient(to right, #8b5cf6, #a855f7, #d946ef)"
              : "linear-gradient(to right, #3b82f6, #6366f1, #8b5cf6)",
          }}
        />

        <div className="flex items-start gap-3 p-4">
          {/* Icon Badge */}
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl shadow-sm ${
              isIdentified
                ? "bg-purple-50 text-purple-600 dark:bg-purple-500/20 dark:text-purple-400"
                : "bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400"
            }`}
          >
            {isIdentified ? (
              <UserCheck className="h-5 w-5" />
            ) : (
              <Bell className="h-5 w-5 animate-bounce" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4
                className={`text-xs font-bold uppercase tracking-wider ${
                  isIdentified
                    ? "text-purple-600 dark:text-purple-400"
                    : "text-blue-600 dark:text-blue-400"
                }`}
              >
                {toast.title}
              </h4>
              <span className="text-[11px] font-medium text-slate-400 shrink-0">
                {toast.timestamp}
              </span>
            </div>

            <p className="mt-1 text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">
              {toast.message}
            </p>

            {/* Sub-tag */}
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
                  isIdentified
                    ? "bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-300"
                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                }`}
              >
                {isIdentified ? (
                  <>
                    <UserCheck className="h-3 w-3" /> Khách quen
                  </>
                ) : (
                  <>
                    <UserPlus className="h-3 w-3" /> Khách hàng mới
                  </>
                )}
              </span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-col items-center gap-1">
            <button
              onClick={dismissToast}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
              aria-label="Đóng"
            >
              <X className="h-4 w-4" />
            </button>
            <button
              onClick={toggleSound}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-500 dark:hover:bg-slate-800 transition-colors"
              title={soundEnabled ? "Tắt âm thanh" : "Bật âm thanh"}
            >
              {soundEnabled ? (
                <Volume2 className="h-3.5 w-3.5 text-blue-500" />
              ) : (
                <VolumeX className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
          </div>
        </div>

        {/* Auto-dismiss progress bar */}
        <div className="h-0.5 bg-slate-100 dark:bg-slate-800">
          <div
            className={`h-full ${isIdentified ? "bg-purple-400" : "bg-blue-400"}`}
            style={{
              animation: "notif-countdown 5s linear forwards",
            }}
          />
        </div>
      </div>

      <style jsx>{`
        @keyframes notif-countdown {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
}
