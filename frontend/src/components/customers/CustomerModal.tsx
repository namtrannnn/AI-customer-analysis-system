"use client";

import Modal from "@/components/ui/Modal";
import CustomerForm from "./CustomerForm";
import {
  Customer,
  CustomerCreatePayload,
  CustomerUpdatePayload,
} from "@/types/customer.type";
import { AlertTriangle, Loader2 } from "lucide-react";

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
        showStatus={false}
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
  onSubmit: (payload: CustomerUpdatePayload) => Promise<void>;
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
        showStatus={true}
        initialValues={{
          full_name: customer.full_name,
          phone: customer.phone ?? "",
          email: customer.email ?? "",
          gender: customer.gender ?? "male",
          status: customer.status,
          note: customer.note ?? "",
          avatar_url: customer.avatar_url ?? "",
        }}
        onSubmit={async (payload) => {
          try {
            await onSubmit(payload);
            onClose();
          } catch {
            // API lỗi thì không đóng modal
          }
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
