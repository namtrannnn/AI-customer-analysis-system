"use client";

import Modal from "@/components/ui/Modal";
import RoleForm from "./RoleForm";
import type {
  Role,
  RoleCreatePayload,
  RoleUpdatePayload,
} from "@/types/role.type";

interface RoleAddModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: RoleCreatePayload) => Promise<void>;
}

export function RoleAddModal({ open, onClose, onSubmit }: RoleAddModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Thêm nhóm quyền mới" size="xl">
      <RoleForm
        onSubmit={onSubmit}
        onCancel={onClose}
        submitLabel="Thêm nhóm quyền"
      />
    </Modal>
  );
}

interface RoleEditModalProps {
  open: boolean;
  onClose: () => void;
  role: Role | null;
  currentPermissionIds: number[];
  onSubmit: (payload: RoleUpdatePayload) => Promise<void>;
}

export function RoleEditModal({
  open,
  onClose,
  role,
  currentPermissionIds,
  onSubmit,
}: RoleEditModalProps) {
  if (!role) return null;

  const initialPermissionIds =
    currentPermissionIds.length > 0
      ? currentPermissionIds
      : (role.permission_ids ?? role.permissions?.map((p) => p.id) ?? []);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Cập nhật: ${role.role_name}`}
      size="xl"
    >
      <RoleForm
        initialValues={{
          role_code: role.role_code,
          role_name: role.role_name,
          description: role.description ?? "",
          permission_ids: initialPermissionIds,
        }}
        initialPermissionIds={initialPermissionIds}
        onSubmit={onSubmit}
        onCancel={onClose}
        submitLabel="Lưu thay đổi"
      />
    </Modal>
  );
}

interface RoleDeleteModalProps {
  open: boolean;
  onClose: () => void;
  role: Role | null;
  onConfirm: () => Promise<void>;
  loading?: boolean;
}

export function RoleDeleteModal({
  open,
  onClose,
  role,
  onConfirm,
  loading = false,
}: RoleDeleteModalProps) {
  if (!role) return null;

  const userCount = role.users?.length ?? 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Xác nhận xóa nhóm quyền"
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            Hủy
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
          >
            {loading && (
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                />
              </svg>
            )}
            Xác nhận xóa
          </button>
        </>
      }
    >
      <div className="flex flex-col items-center py-2 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
          <svg
            className="h-6 w-6 text-red-600 dark:text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <p className="text-sm text-slate-700 dark:text-slate-300">
          Xóa nhóm quyền{" "}
          <span className="font-semibold">"{role.role_name}"</span>?
        </p>

        {userCount > 0 ? (
          <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
            Nhóm quyền này đang có {userCount} người dùng. BE sẽ không cho xóa
            cho tới khi gỡ nhóm quyền khỏi người dùng.
          </p>
        ) : (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Thao tác này sẽ xóa nhóm quyền và các quyền đã gán trong nhóm.
          </p>
        )}
      </div>
    </Modal>
  );
}
