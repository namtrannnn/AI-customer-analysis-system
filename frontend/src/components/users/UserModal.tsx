"use client";

import Modal from "@/components/ui/Modal";
import ConfirmModal from "@/components/ui/ConfirmModal";
import UserForm from "./UserForm";
import type {
  User,
  UserCreatePayload,
  UserUpdatePayload,
} from "@/types/user.type";
import { AlertTriangle, KeyRound } from "lucide-react";

// ─── Add ──────────────────────────────────────────────────────────────────────
interface UserAddModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: UserCreatePayload) => Promise<void>;
}

export function UserAddModal({ open, onClose, onSubmit }: UserAddModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Thêm người dùng mới" size="lg">
      <UserForm
        mode="create"
        onSubmit={async (payload) => {
          await onSubmit(payload as UserCreatePayload);
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
  onSubmit: (payload: UserUpdatePayload) => Promise<void>;
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
        initialRoleId={user.role_id ?? null}
        onSubmit={async (payload) => {
          await onSubmit(payload as UserUpdatePayload);
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
    <ConfirmModal
      open={open}
      onClose={onClose}
      onConfirm={onConfirm}
      loading={loading}
      title="Xác nhận xóa người dùng"
      confirmText="Xác nhận xóa"
      variant="danger"
      icon={
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
          <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
        </div>
      }
      description={
        <>
          <p>
            Xóa người dùng{" "}
            <span className="font-semibold">"{user.full_name}"</span>?
          </p>

          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Tài khoản sẽ bị xóa mềm khỏi danh sách người dùng.
          </p>
        </>
      }
    />
  );
}

// ─── Reset Password ───────────────────────────────────────────────────────────
interface UserResetPasswordModalProps {
  open: boolean;
  onClose: () => void;
  user: User | null;
  onConfirm: () => Promise<void>;
  loading?: boolean;
}

export function UserResetPasswordModal({
  open,
  onClose,
  user,
  onConfirm,
  loading = false,
}: UserResetPasswordModalProps) {
  if (!user) return null;

  return (
    <ConfirmModal
      open={open}
      onClose={onClose}
      onConfirm={onConfirm}
      loading={loading}
      title="Xác nhận reset mật khẩu"
      confirmText="Xác nhận reset"
      variant="primary"
      icon={
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
          <KeyRound className="h-6 w-6 text-blue-600 dark:text-blue-400" />
        </div>
      }
      description={
        <>
          <p>
            Reset mật khẩu cho{" "}
            <span className="font-semibold">"{user.full_name}"</span>?
          </p>

          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Hệ thống sẽ tạo mật khẩu tạm thời mới. Mật khẩu này sẽ hiển thị cho
            admin copy sau khi reset thành công.
          </p>
        </>
      }
    />
  );
}
