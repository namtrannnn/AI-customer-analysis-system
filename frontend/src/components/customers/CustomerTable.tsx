"use client";

import Link from "next/link";
import Image from "next/image";
import { Customer, CustomerStatus } from "@/types/customer.type";
import { formatDate, timeAgo } from "@/utils/formatDate";
import { formatCurrency } from "@/utils/formatCurrency";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";

interface CustomerTableProps {
  customers: Customer[];
  onEdit: (customer: Customer) => void;
  onDelete: (customer: Customer) => void;
}

const statusConfig: Record<
  CustomerStatus,
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
      "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700",
  },
  vip: {
    label: "VIP",
    className:
      "bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
  },
};

const genderLabel: Record<string, string> = {
  male: "Nam",
  female: "Nữ",
  other: "Khác",
};

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
            const status = statusConfig[c.status];

            return (
              <tr
                key={c.id}
                className="group bg-white transition-colors hover:bg-blue-50/40 dark:bg-slate-900 dark:hover:bg-slate-800/60"
              >
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 ring-1 ring-slate-200 dark:from-slate-800 dark:to-slate-700 dark:ring-slate-700">
                      {c.avatar_url ? (
                        <Image
                          src={c.avatar_url}
                          alt={c.full_name}
                          fill
                          className="object-cover"
                          sizes="40px"
                        />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-sm font-black text-slate-500 dark:text-slate-300">
                          {c.full_name?.charAt(0).toUpperCase() || "K"}
                        </span>
                      )}
                    </div>

                    <div className="min-w-0">
                      <Link
                        href={`/customers/${c.id}`}
                        className="line-clamp-1 font-bold text-slate-900 transition hover:text-blue-600 dark:text-white dark:hover:text-blue-300"
                      >
                        {c.full_name || "Khách ẩn danh"}
                      </Link>

                      <p className="mt-0.5 text-xs font-medium text-slate-400 dark:text-slate-500">
                        {c.customer_code}
                      </p>
                    </div>
                  </div>
                </td>

                <td className="px-4 py-3.5">
                  <p className="font-medium text-slate-700 dark:text-slate-300">
                    {c.phone ?? "—"}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                    {c.email ?? "—"}
                  </p>
                </td>

                <td className="px-4 py-3.5">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${status.className}`}
                  >
                    {status.label}
                  </span>

                  {c.gender && (
                    <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                      {genderLabel[c.gender]}
                    </p>
                  )}
                </td>

                <td className="px-4 py-3.5 text-right font-bold text-slate-700 dark:text-slate-300">
                  {c.total_visits}
                </td>

                <td className="px-4 py-3.5 text-right font-bold text-slate-700 dark:text-slate-300">
                  {c.total_spent > 0 ? formatCurrency(c.total_spent) : "—"}
                </td>

                <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {timeAgo(c.last_visited_at)}
                </td>

                <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {formatDate(c.created_at)}
                </td>

                <td className="px-4 py-3.5 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Link href={`/customers/${c.id}`}>
                      <Button variant="ghost" size="sm" title="Xem chi tiết">
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      </Button>
                    </Link>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(c)}
                      title="Chỉnh sửa"
                    >
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                        />
                      </svg>
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-300"
                      onClick={() => onDelete(c)}
                      title="Xóa"
                    >
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
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
