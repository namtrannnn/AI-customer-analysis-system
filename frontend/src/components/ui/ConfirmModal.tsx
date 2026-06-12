import Modal from "@/components/ui/Modal";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

interface ConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  title: string;
  description: ReactNode;
  icon?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  loading?: boolean;
  variant?: "danger" | "primary";
}

export default function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  icon,
  confirmText = "Xác nhận",
  cancelText = "Hủy",
  loading = false,
  variant = "primary",
}: ConfirmModalProps) {
  const confirmClass =
    variant === "danger"
      ? "bg-red-600 hover:bg-red-700"
      : "bg-blue-600 hover:bg-blue-700";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            {cancelText}
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition disabled:opacity-60 ${confirmClass}`}
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmText}
          </button>
        </>
      }
    >
      <div className="flex flex-col items-center py-2 text-center">
        {icon && <div className="mb-4">{icon}</div>}

        <div className="text-sm text-slate-700 dark:text-slate-300">
          {description}
        </div>
      </div>
    </Modal>
  );
}
