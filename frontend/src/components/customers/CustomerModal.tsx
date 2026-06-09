"use client";

import Modal from "@/components/ui/Modal";
import CustomerForm from "./CustomerForm";
import { Customer, CustomerCreatePayload } from "@/types/customer.type";

// ─── Add Modal ────────────────────────────────────────────────────────────────
interface CustomerAddModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: CustomerCreatePayload) => Promise<void>;
}

export function CustomerAddModal({
  open,
  onClose,
  onSubmit,
}: CustomerAddModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Thêm khách hàng mới" size="lg">
      <CustomerForm
        onSubmit={async (payload) => {
          await onSubmit(payload);
          onClose();
        }}
        onCancel={onClose}
        submitLabel="Thêm khách hàng"
      />
    </Modal>
  );
}

// ─── Edit Modal ───────────────────────────────────────────────────────────────
interface CustomerEditModalProps {
  open: boolean;
  onClose: () => void;
  customer: Customer | null;
  onSubmit: (payload: CustomerCreatePayload) => Promise<void>;
}

export function CustomerEditModal({
  open,
  onClose,
  customer,
  onSubmit,
}: CustomerEditModalProps) {
  if (!customer) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Cập nhật: ${customer.full_name}`}
      size="lg"
    >
      <CustomerForm
        initialValues={{
          full_name: customer.full_name,
          phone: customer.phone ?? "",
          email: customer.email ?? "",
          gender: customer.gender ?? undefined,
          status: customer.status,
          note: customer.note ?? "",
          avatar_url: customer.avatar_url ?? "",
        }}
        onSubmit={async (payload) => {
          await onSubmit(payload);
          onClose();
        }}
        onCancel={onClose}
        submitLabel="Lưu thay đổi"
      />
    </Modal>
  );
}

// ─── Delete Confirm Modal ─────────────────────────────────────────────────────
interface CustomerDeleteModalProps {
  open: boolean;
  onClose: () => void;
  customer: Customer | null;
  onConfirm: () => Promise<void>;
  loading?: boolean;
}

export function CustomerDeleteModal({
  open,
  onClose,
  customer,
  onConfirm,
  loading = false,
}: CustomerDeleteModalProps) {
  if (!customer) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Xác nhận xóa khách hàng"
      size="sm"
      footer={
        <>
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
          >
            Hủy
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
          >
            {loading && (
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            )}
            Xác nhận xóa
          </button>
        </>
      }
    >
      <div className="flex flex-col items-center py-2 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
          <svg className="h-6 w-6 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p className="text-sm text-slate-700 dark:text-slate-300">
          Bạn có chắc muốn xóa khách hàng{" "}
          <span className="font-semibold">"{customer.full_name}"</span>?
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Hành động này sẽ đặt trạng thái thành "Ngừng hoạt động".
        </p>
      </div>
    </Modal>
  );
}
