"use client";

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";

export interface NotificationItem {
  id: string;
  person_key?: string;
  track_id?: number | string;
  anonymous_code?: string;
  customer_id?: string;
  title: string;
  message: string;
  customer_name?: string;
  person_type?: string;
  timestamp: string;
  read: boolean;
  source_timestamp_seconds?: number;
}

interface NotificationContextType {
  notifications: NotificationItem[];
  unreadCount: number;
  soundEnabled: boolean;
  toast: NotificationItem | null;
  toggleSound: () => void;
  markAllAsRead: () => void;
  clearAll: () => void;
  dismissToast: () => void;
  addNotification: (item: Omit<NotificationItem, "id" | "read">) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

const LOCAL_STORAGE_SOUND_KEY = "ai_customer_sound_enabled";

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [toast, setToast] = useState<NotificationItem | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const lastSoundTimeRef = useRef<number>(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Set lưu trữ các mã người dùng / track_id ĐÃ ĐƯỢC THÔNG BÁO (Tránh trùng lặp)
  const seenKeysRef = useRef<Set<string>>(new Set());

  // Read sound preference from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_SOUND_KEY);
      if (stored !== null) {
        setSoundEnabled(stored === "true");
      }
    } catch (e) {}
  }, []);

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(LOCAL_STORAGE_SOUND_KEY, String(next));
      } catch (e) {}
      return next;
    });
  }, []);

  // Helper: Play notification sound (/sounds/message_sound.mp3)
  const triggerSound = useCallback(() => {
    const now = Date.now();
    // Anti-spam: Tối thiểu 3.0s mới cho phát lại tiếng chuông 1 lần
    if (now - lastSoundTimeRef.current < 3000) return;
    lastSoundTimeRef.current = now;

    try {
      const audio = new Audio("/sounds/message_sound.mp3");
      audio.volume = 0.6;
      audio.play().catch((err) => {
        console.log("Audio autoplay prevented by browser:", err);
      });
    } catch (e) {
      console.error("Error playing audio sound:", e);
    }
  }, []);

  // Handler: Thêm thông báo mới + Bật Toast + Phát âm thanh (Có DEDUPLICATION)
  const addNotification = useCallback(
    (item: Omit<NotificationItem, "id" | "read">) => {
      // Key định danh duy nhất — ưu tiên customer_id -> anonymous_code -> person_key -> track_id
      const personKey =
        (item.customer_id ? `cust_${item.customer_id}` : null) ||
        (item.anonymous_code ? `anon_${item.anonymous_code}` : null) ||
        item.person_key ||
        (item.track_id ? `track_${item.track_id}` : null) ||
        item.customer_name;

      // NẾU ĐÃ THÔNG BÁO CHO NGƯỜI NÀY RỒI → BỎ QUA NGAY
      if (personKey && seenKeysRef.current.has(personKey)) {
        return;
      }

      if (personKey) {
        seenKeysRef.current.add(personKey);
      }

      const newNotif: NotificationItem = {
        ...item,
        person_key: personKey || undefined,
        id: `notif-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
        read: false,
      };

      setNotifications((prev) => [newNotif, ...prev.slice(0, 49)]); // Giữ tối đa 50 thông báo
      setToast(newNotif);

      if (soundEnabled) {
        triggerSound();
      }
    },
    [soundEnabled, triggerSound]
  );

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
    seenKeysRef.current.clear();
  }, []);

  const dismissToast = useCallback(() => {
    setToast(null);
  }, []);

  // Auto-dismiss Toast sau 5 giây
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast(null);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  // ── WebSocket Realtime Receiver + Auto-Reconnect ──────────────────────────
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    let isMounted = true;

    const connectWs = () => {
      if (!isMounted) return;

      try {
        const ws = new WebSocket(`${wsUrl}/api/notifications/ws`);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log("✅ [NotificationContext] WebSocket đã kết nối!");
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.type === "FACE_DETECTED" && payload.data) {
              const data = payload.data;

              addNotification({
                person_key: data.person_key,
                track_id: data.track_id,
                anonymous_code: data.anonymous_code,
                customer_id: data.customer_id,
                title: data.title || "Có khách vừa vào cửa hàng",
                message: data.message || "Phát hiện khuôn mặt mới bước vào cửa hàng",
                customer_name: data.customer_name,
                person_type: data.person_type,
                timestamp:
                  data.timestamp ||
                  new Date().toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  }),
                source_timestamp_seconds: data.source_timestamp_seconds,
              });
            }
          } catch (e) {
            console.error("Lỗi parse WS notification:", e);
          }
        };

        ws.onerror = () => {
          // Handled in onclose
        };

        ws.onclose = () => {
          console.log("❌ [NotificationContext] WS closed. Reconnecting in 5s...");
          wsRef.current = null;
          // Auto-reconnect after 5 seconds
          if (isMounted) {
            reconnectTimerRef.current = setTimeout(connectWs, 5000);
          }
        };
      } catch (e) {
        console.error("WS Connection error:", e);
        if (isMounted) {
          reconnectTimerRef.current = setTimeout(connectWs, 5000);
        }
      }
    };

    connectWs();

    return () => {
      isMounted = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [addNotification]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        soundEnabled,
        toast,
        toggleSound,
        markAllAsRead,
        clearAll,
        dismissToast,
        addNotification,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error("useNotification must be used within a NotificationProvider");
  }
  return context;
}
