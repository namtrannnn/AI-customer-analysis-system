"use client";

/**
 * RealtimeCounter — Live counter "Đang có mặt" trên Dashboard
 * 
 * Hiện tại: dùng mock data, tự động thay đổi mỗi 8 giây để simulate realtime
 * Khi có camera thật: thay MOCK_MODE = false và connect WebSocket thật
 * 
 * TODO: đổi WS_URL thành endpoint thật khi có camera
 * const WS_URL = "wss://intership-api.hqsolutions.vn/api/cameras/presence";
 */

import { useEffect, useState } from "react";
import { Users, TrendingUp, Clock, Wifi, Info } from "lucide-react";
import Link from "next/link";

const MOCK_MODE = true; // ← đổi thành false khi có camera thật

interface PresenceData {
  current_count: number;    // Đang có mặt lúc này
  today_total: number;      // Tổng hôm nay
  peak_hour: string;        // Giờ đông nhất hôm nay
  peak_count: number;       // Số người lúc đông nhất
  avg_stay_minutes: number; // Thời gian ở lại TB hôm nay
}

// Simulate fluctuating realtime data
function generateMockData(): PresenceData {
  const hour = new Date().getHours();
  // Peak giờ trưa và chiều tối
  const baseCount = hour >= 11 && hour <= 13 ? 8 :
                    hour >= 17 && hour <= 19 ? 12 :
                    hour >= 9  && hour <= 18 ? 5 : 2;
  return {
    current_count: baseCount + Math.floor(Math.random() * 4),
    today_total: 47 + Math.floor(Math.random() * 10),
    peak_hour: "17:00 - 18:00",
    peak_count: 14,
    avg_stay_minutes: 32 + Math.floor(Math.random() * 8),
  };
}

export default function RealtimeCounter() {
  const [data, setData] = useState<PresenceData | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    if (MOCK_MODE) {
      // Initial load
      setData(generateMockData());
      setLastUpdate(new Date());

      // Simulate realtime updates mỗi 8 giây
      const interval = setInterval(() => {
        setData(generateMockData());
        setLastUpdate(new Date());
      }, 8000);

      return () => clearInterval(interval);
    }

    // Khi có camera thật — uncomment:
    // const ws = new WebSocket("wss://intership-api.hqsolutions.vn/api/cameras/presence");
    // ws.onmessage = (e) => {
    //   const payload = JSON.parse(e.data);
    //   setData(payload);
    //   setLastUpdate(new Date());
    // };
    // return () => ws.close();
  }, []);

  if (!data) return null;

  const timeStr = lastUpdate.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div
      className="overflow-hidden rounded-2xl"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      {/* Top gradient bar */}
      <div className="h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500" />

      <div className="px-5 py-4">
        {/* Header row */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Realtime hôm nay
            </span>
            {MOCK_MODE && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                <Info className="h-3 w-3" />
                Mock
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <Wifi className="h-3.5 w-3.5 text-emerald-500" />
            <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
              {timeStr}
            </span>
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* Đang có mặt — highlight nhất */}
          <div className="col-span-2 sm:col-span-1 flex flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 p-4 shadow-lg shadow-emerald-500/20">
            <p className="text-4xl font-black text-white leading-none">{data.current_count}</p>
            <p className="mt-1 text-xs font-semibold text-emerald-100">Đang có mặt</p>
            <div className="mt-2 flex items-center gap-1">
              <Users className="h-3.5 w-3.5 text-emerald-200" />
              <span className="text-[11px] text-emerald-200">trong cửa hàng</span>
            </div>
          </div>

          {/* Hôm nay */}
          <div
            className="flex flex-col justify-between rounded-2xl p-4"
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

          {/* Giờ đông nhất */}
          <div
            className="flex flex-col justify-between rounded-2xl p-4"
            style={{ background: "var(--bg-surface-2)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Đông nhất
            </p>
            <p className="mt-2 text-xl font-black" style={{ color: "var(--text-primary)" }}>
              {data.peak_count} người
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>{data.peak_hour}</p>
          </div>

          {/* TB ở lại */}
          <div
            className="flex flex-col justify-between rounded-2xl p-4"
            style={{ background: "var(--bg-surface-2)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              TB ở lại
            </p>
            <p className="mt-2 text-2xl font-black" style={{ color: "var(--text-primary)" }}>
              {data.avg_stay_minutes}
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>phút</p>
          </div>
        </div>

        {/* Link sang visit-profiles */}
        <div className="mt-3 flex justify-end">
          <Link
            href="/visit-profiles"
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
          >
            Xem chi tiết khách ghé thăm →
          </Link>
        </div>
      </div>
    </div>
  );
}
