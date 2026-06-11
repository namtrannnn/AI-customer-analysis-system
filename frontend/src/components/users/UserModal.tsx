"use client";

import Modal from "@/components/ui/Modal";
import UserForm from "./UserForm";
import type {
  User,
  UserCreatePayload,
  UserUpdatePayload,
} from "@/types/user.type";
import { AlertTriangle, Loader2 } from "lucide-react";

// ─── Add ──────────────────────────────────────────────────────────────────────
interface UserAddModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: UserCreatePayload, roleIds: number[]) => Promise<void>;
}

export function UserAddModal({ open, onClose, onSubmit }: UserAddModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Thêm người dùng mới" size="lg">
      <UserForm
        mode="create"
        onSubmit={async (payload, roleIds) => {
          await onSubmit(payload as UserCreatePayload, roleIds);
        }}
        onCancel={onClose}
      />
    </Modal>
  );
}

// ─── Edit ─────────────────────────────────────────────────────────────────────
interface UserEditModalProps {
  open: boolean;
  onClose: () => void;
  user: User | null;
  onSubmit: (payload: UserUpdatePayload, roleIds: number[]) => Promise<void>;
}

export function UserEditModal({
  open,
  onClose,
  user,
  onSubmit,
}: UserEditModalProps) {
  if (!user) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Cập nhật: ${user.full_name}`}
      size="lg"
    >
      <UserForm
        mode="edit"
        initialValues={{
          full_name: user.full_name,
          email: user.email ?? "",
          phone: user.phone ?? "",
          status:
            user.status === "active" || user.status === "inactive"
              ? user.status
              : "inactive",
        }}
        initialRoleIds={user.role_ids ?? []}
        onSubmit={async (payload, roleIds) => {
          await onSubmit(payload as UserUpdatePayload, roleIds);
        }}
        onCancel={onClose}
      />
    </Modal>
  );
}

// ─── Delete ───────────────────────────────────────────────────────────────────
interface UserDeleteModalProps {
  open: boolean;
  onClose: () => void;
  user: User | null;
  onConfirm: () => Promise<void>;
  loading?: boolean;
}

export function UserDeleteModal({
  open,
  onClose,
  user,
  onConfirm,
  loading = false,
}: UserDeleteModalProps) {
  if (!user) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Xác nhận xóa người dùng"
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            Hủy
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-60"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Xác nhận xóa
          </button>
        </>
      }
    >
      <div className="flex flex-col items-center py-2 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
          <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
        </div>

        <p className="text-sm text-slate-700 dark:text-slate-300">
          Xóa người dùng{" "}
          <span className="font-semibold">"{user.full_name}"</span>?
        </p>

        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Tài khoản sẽ bị xóa mềm khỏi danh sách người dùng.
        </p>
      </div>
    </Modal>
  );
}
