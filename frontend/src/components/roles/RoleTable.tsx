"use client";

import type { Role } from "@/types/role.type";
import { formatDate } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";

interface RoleTableProps {
  roles: Role[];
  onEdit: (role: Role) => void;
  onDelete: (role: Role) => void;
}

export default function RoleTable({ roles, onEdit, onDelete }: RoleTableProps) {
  if (roles.length === 0) {
    return (
      <EmptyState
        title="Không tìm thấy nhóm quyền"
        description="Thử thay đổi từ khóa tìm kiếm hoặc thêm nhóm quyền mới."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="pb-3 pr-4">Nhóm quyền</th>
            <th className="pb-3 pr-4">Mã</th>
            <th className="pb-3 pr-4">Mô tả</th>
            <th className="pb-3 pr-4 text-center">Quyền</th>
            <th className="pb-3 pr-4 text-center">Người dùng</th>
            <th className="pb-3 pr-4">Ngày tạo</th>
            <th className="pb-3 text-right">Thao tác</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {roles.map((r) => (
            <tr key={r.id} className="group hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
              <td className="py-3 pr-4 font-medium text-slate-900 dark:text-slate-100">{r.role_name}</td>
              <td className="py-3 pr-4">
                <code className="rounded bg-slate-100 dark:bg-slate-700 px-2 py-0.5 text-xs text-slate-700 dark:text-slate-300">
                  {r.role_code}
                </code>
              </td>
              <td className="py-3 pr-4 text-slate-500 dark:text-slate-400 max-w-[200px] truncate">
                {r.description ?? "—"}
              </td>
              <td className="py-3 pr-4 text-center">
                <span className="inline-flex items-center justify-center rounded-full bg-purple-100 dark:bg-purple-900/30 px-2.5 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-400">
                  {r.permission_count}
                </span>
              </td>
              <td className="py-3 pr-4 text-center">
                <span className="inline-flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
                  {r.user_count}
                </span>
              </td>
              <td className="py-3 pr-4 text-slate-500 dark:text-slate-400">{formatDate(r.created_at)}</td>
              <td className="py-3 text-right">
                <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <Button variant="ghost" size="sm" onClick={() => onEdit(r)} title="Chỉnh sửa">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600"
                    onClick={() => onDelete(r)}
                    title="Xóa"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
