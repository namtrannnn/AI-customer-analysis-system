"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  ReactNode,
} from "react";
import { AlertCircle, CheckCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (type: ToastType, message: string) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (type: ToastType, message: string) => {
      const id = Date.now();

      setToasts((prev) => [...prev, { id, type, message }]);

      setTimeout(() => {
        removeToast(id);
      }, 3000);
    },
    [removeToast],
  );

  const value: ToastContextValue = {
    showToast,
    success: (message) => showToast("success", message),
    error: (message) => showToast("error", message),
    info: (message) => showToast("info", message),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div className="fixed bottom-6 right-6 z-[9999] flex w-[360px] max-w-[calc(100vw-32px)] flex-col gap-3">
        {toasts.map((toast) => (
          <ToastCard
            key={toast.id}
            toast={toast}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({
  toast,
  onClose,
}: {
  toast: ToastItem;
  onClose: () => void;
}) {
  const config = {
    success: {
      icon: <CheckCircle className="h-5 w-5" />,
      className:
        "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200",
    },
    error: {
      icon: <AlertCircle className="h-5 w-5" />,
      className:
        "border-red-200 bg-red-50 text-red-800 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200",
    },
    info: {
      icon: <Info className="h-5 w-5" />,
      className:
        "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-200",
    },
  }[toast.type];

  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-lg backdrop-blur ${config.className}`}
      role="alert"
    >
      <div className="mt-0.5 shrink-0">{config.icon}</div>

      <p className="flex-1 text-sm font-semibold leading-5">{toast.message}</p>

      <button
        type="button"
        onClick={onClose}
        className="shrink-0 rounded-full p-1 hover:bg-black/5 dark:hover:bg-white/10"
        aria-label="Đóng thông báo"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error("useToast must be used inside ToastProvider");
  }

  return context;
}
