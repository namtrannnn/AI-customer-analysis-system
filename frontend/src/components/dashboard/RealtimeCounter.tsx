"use client";

/**
 * RealtimeCounter — Live counter "Đang có mặt" trên Dashboard
 *
 * Cơ chế:
 * 1. Load initial data từ GET /api/dashboard/today-stats
 * 2. Lắng nghe BroadcastChannel "visitor_count" từ LiveDetectionsList
 *    → Nhận số người chính xác (đã deduplicate) từ trang Videos
 * 3. WebSocket /api/dashboard/ws chỉ dùng để nhận complete/error → reset
 *
 * Pattern: BroadcastChannel giống cashier page dùng "video_sync"
 */

import { useEffect, useState, useRef } from "react";
import { Users, Wifi, WifiOff, RefreshCw } from "lucide-react";
import Link from "next/link";
import { http } from "@/lib/http";

interface PresenceData {
  current_count:    number;
  today_total:      number;
  today_revenue:    number;
  today_orders:     number;
  avg_stay_minutes: number;
}

type WsStatus = "connecting" | "connected" | "disconnected";

export default function RealtimeCounter() {
  const [data, setData]           = useState<PresenceData | null>(null);
  const [wsStatus, setWsStatus]   = useState<WsStatus>("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [isLiveActive, setIsLiveActive] = useState(false); // video đang chạy
  const wsRef = useRef<WebSocket | null>(null);
  const liveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadInitialData() {
    try {
      const res = await http.raw.get<any>("/dashboard/today-stats");
      const d = res.data?.data || res.data;
      setData({
        current_count:    d.current_count    ?? 0,
        today_total:      d.today_total      ?? 0,
        today_revenue:    d.today_revenue    ?? 0,
        today_orders:     d.today_orders     ?? 0,
        avg_stay_minutes: d.avg_stay_minutes ?? 0,
      });
    } catch {
      setData({ current_count: 0, today_total: 0, today_revenue: 0, today_orders: 0, avg_stay_minutes: 0 });
    }
  }

  useEffect(() => {
    loadInitialData();

    // ── BroadcastChannel: nhận số người từ LiveDetectionsList ────────────────
    // LiveDetectionsList đã deduplicate đúng → đây là source of truth
    const visitorChannel = new BroadcastChannel("visitor_count");
    visitorChannel.onmessage = (e) => {
      const { count } = e.data as { count: number; identified?: unknown[]; timestamp: number };
      setLastUpdate(new Date());
      setIsLiveActive(true);

      // Reset timeout "live active" sau 5s nếu không có update mới
      if (liveTimeoutRef.current) clearTimeout(liveTimeoutRef.current);
      liveTimeoutRef.current = setTimeout(() => setIsLiveActive(false), 5000);

      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          current_count: count,
          // today_total chỉ tăng — không giảm khi người ra khỏi frame
          today_total: Math.max(prev.today_total, count),
        };
      });
    };

    // ── WebSocket: chỉ nhận complete/error để reset khi video xong ──────────
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/api/dashboard/ws`);
    wsRef.current = ws;

    ws.onopen  = () => setWsStatus("connected");
    ws.onclose = () => setWsStatus("disconnected");
    ws.onerror = () => setWsStatus("disconnected");

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "complete" || msg.type === "error") {
          // Video xong → reset live counter, reload data thật từ DB
          setIsLiveActive(false);
          setData((prev) => prev ? { ...prev, current_count: 0 } : prev);
          loadInitialData();
        }
      } catch { /* ignore */ }
    };

    return () => {
      visitorChannel.close();
      ws.close();
      wsRef.current = null;
      if (liveTimeoutRef.current) clearTimeout(liveTimeoutRef.current);
    };
  }, []);

  if (!data) return null;

  const timeStr = lastUpdate.toLocaleTimeString("vi-VN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  });

  return (
    <div
      className="overflow-hidden rounded-2xl"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      {/* Top accent bar */}
      <div className={`h-1 bg-gradient-to-r ${
        isLiveActive
          ? "from-emerald-500 via-teal-500 to-cyan-500"
          : wsStatus === "connected"
          ? "from-sky-400 to-blue-500"
          : "from-slate-300 to-slate-400"
      }`} />

      <div className="px-5 py-4">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${
              isLiveActive ? "bg-emerald-500 animate-pulse" :
              wsStatus === "connected" ? "bg-sky-400" : "bg-slate-400"
            }`} />
            <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Realtime hôm nay
            </span>

            {isLiveActive && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
                Live
              </span>
            )}
            {!isLiveActive && wsStatus === "connected" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-bold text-sky-600 dark:bg-sky-900/30 dark:text-sky-400">
                <Wifi className="h-3 w-3" />
                Sẵn sàng
              </span>
            )}
            {wsStatus === "disconnected" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                <WifiOff className="h-3 w-3" />
                Offline
              </span>
            )}
            {wsStatus === "connecting" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                <RefreshCw className="h-3 w-3 animate-spin" />
                Đang kết nối
              </span>
            )}
          </div>
          <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
            {timeStr}
          </span>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* Đang có mặt */}
          <div className={`col-span-2 sm:col-span-1 flex flex-col items-center justify-center rounded-2xl p-4 shadow-lg ${
            isLiveActive
              ? "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/20"
              : "bg-gradient-to-br from-slate-400 to-slate-500 shadow-slate-400/20"
          }`}>
            <p className="text-4xl font-black text-white leading-none">{data.current_count}</p>
            <p className="mt-1 text-xs font-semibold text-white/80">Đang có mặt</p>
            <div className="mt-2 flex items-center gap-1">
              <Users className="h-3.5 w-3.5 text-white/60" />
              <span className="text-[11px] text-white/60">trong cửa hàng</span>
            </div>
          </div>

          {/* Hôm nay */}
          <div className="flex flex-col justify-between rounded-2xl p-4"
            style={{ background: "var(--bg-surface-2)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Hôm nay
            </p>
            <p className="mt-2 text-2xl font-black" style={{ color: "var(--text-primary)" }}>
              {data.today_total}
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>lượt khách</p>
          </div>

          {/* Doanh thu hôm nay */}
          <div className="flex flex-col justify-between rounded-2xl p-4"
            style={{ background: "var(--bg-surface-2)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Doanh thu
            </p>
            <p className="mt-2 text-lg font-black truncate" style={{ color: "var(--text-primary)" }}>
              {data.today_revenue > 0
                ? data.today_revenue >= 1_000_000
                  ? `${(data.today_revenue / 1_000_000).toFixed(1)}M`
                  : `${Math.round(data.today_revenue / 1000).toLocaleString()}K`
                : "—"}
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>hôm nay (VND)</p>
          </div>

          {/* Số đơn hôm nay */}
          <div className="flex flex-col justify-between rounded-2xl p-4"
            style={{ background: "var(--bg-surface-2)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Đơn hàng
            </p>
            <p className="mt-2 text-2xl font-black" style={{ color: "var(--text-primary)" }}>
              {data.today_orders > 0 ? data.today_orders : "—"}
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>đơn hôm nay</p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {isLiveActive
              ? "Đang nhận data từ video AI đang chạy"
              : wsStatus === "connected"
              ? "Chạy video AI để cập nhật realtime"
              : "Hiển thị data từ DB"}
          </span>
          <Link
            href="/visit-profiles"
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
          >
            Xem chi tiết →
          </Link>
        </div>
      </div>
    </div>
  );
}
