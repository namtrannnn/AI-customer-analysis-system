"use client";

import Link from "next/link";
import { Eye, Pencil, Trash2 } from "lucide-react";

import { Customer } from "@/types/customer.type";
import { formatDate, timeAgo } from "@/utils/formatDate";
import { formatCurrency } from "@/utils/formatCurrency";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";

interface CustomerTableProps {
  customers: Customer[];
  onEdit: (customer: Customer) => void;
  onDelete: (customer: Customer) => void;
}

type CustomerStatusView = "active" | "inactive";

const statusConfig: Record<
  CustomerStatusView,
  { label: string; className: string }
> = {
  active: {
    label: "Hoạt động",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  },
  inactive: {
    label: "Ngừng HĐ",
    className:
      "bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  },
};

const genderLabel: Record<string, string> = {
  male: "Nam",
  female: "Nữ",
  other: "Khác",
};

function getCustomerName(customer: Customer) {
  return customer.full_name?.trim() || "Khách ẩn danh";
}

function getCustomerInitial(customer: Customer) {
  const name = getCustomerName(customer);
  return name.charAt(0).toUpperCase() || "K";
}

function getCustomerStatus(status?: string | null) {
  if (status === "inactive") return statusConfig.inactive;
  return statusConfig.active;
}

export default function CustomerTable({
  customers,
  onEdit,
  onDelete,
}: CustomerTableProps) {
  if (customers.length === 0) {
    return (
      <div className="py-12">
        <EmptyState
          title="Không tìm thấy khách hàng"
          description="Thử thay đổi bộ lọc hoặc thêm khách hàng mới."
        />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto bg-white dark:bg-slate-900">
      <table className="w-full min-w-[1050px] text-sm">
        <thead className="bg-slate-50 dark:bg-slate-950/50">
          <tr className="text-left text-[11px] font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="px-4 py-3">Khách hàng</th>
            <th className="px-4 py-3">Liên hệ</th>
            <th className="px-4 py-3">Trạng thái</th>
            <th className="px-4 py-3 text-right">Lượt ghé</th>
            <th className="px-4 py-3 text-right">Chi tiêu</th>
            <th className="px-4 py-3">Ghé gần nhất</th>
            <th className="px-4 py-3">Ngày tạo</th>
            <th className="px-4 py-3 text-right">Thao tác</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {customers.map((c) => {
            const customerName = getCustomerName(c);
            const status = getCustomerStatus(c.status);
            const totalVisits = c.total_visits ?? 0;
            const totalSpent = Number(c.total_spent ?? 0);
            const customerCode = c.customer_code || `CUS-${c.id}`;

            return (
              <tr
                key={c.id}
                className="group bg-white transition-colors hover:bg-blue-50/40 dark:bg-slate-900 dark:hover:bg-slate-800/60"
              >
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 ring-1 ring-slate-200 dark:from-slate-800 dark:to-slate-700 dark:ring-slate-700">
                      {c.avatar_url ? (
                        <img
                          src={c.avatar_url}
                          alt={customerName}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-sm font-black text-slate-500 dark:text-slate-300">
                          {getCustomerInitial(c)}
                        </span>
                      )}
                    </div>

                    <div className="min-w-0">
                      <Link
                        href={`/customers/${c.id}`}
                        className="line-clamp-1 font-bold text-slate-900 transition hover:text-blue-600 dark:text-white dark:hover:text-blue-300"
                      >
                        {customerName}
                      </Link>

                      <p className="mt-0.5 text-xs font-medium text-slate-400 dark:text-slate-500">
                        {customerCode}
                      </p>
                    </div>
                  </div>
                </td>

                <td className="px-4 py-3.5">
                  <p className="font-medium text-slate-700 dark:text-slate-300">
                    {c.phone || "—"}
                  </p>

                  <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                    {c.email || "—"}
                  </p>
                </td>

                <td className="px-4 py-3.5">
                  <span
                    className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${status.className}`}
                  >
                    {status.label}
                  </span>

                  {c.gender && (
                    <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                      {genderLabel[c.gender] ?? c.gender}
                    </p>
                  )}
                </td>

                <td className="px-4 py-3.5 text-right font-bold text-slate-700 dark:text-slate-300">
                  {totalVisits}
                </td>

                <td className="px-4 py-3.5 text-right font-bold text-slate-700 dark:text-slate-300">
                  {totalSpent > 0 ? formatCurrency(totalSpent) : "—"}
                </td>

                <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {c.last_visited_at ? timeAgo(c.last_visited_at) : "Chưa ghé"}
                </td>

                <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {c.created_at ? formatDate(c.created_at) : "—"}
                </td>

                <td className="px-4 py-3.5 text-right">
                  <div className="invisible flex items-center justify-end gap-1 opacity-0 pointer-events-none transition-all duration-150 group-hover:visible group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:visible group-focus-within:pointer-events-auto group-focus-within:opacity-100">
                    <Link href={`/customers/${c.id}`}>
                      <Button variant="ghost" size="sm" title="Xem chi tiết">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </Link>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(c)}
                      title="Chỉnh sửa"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-300"
                      onClick={() => onDelete(c)}
                      title="Xóa"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
