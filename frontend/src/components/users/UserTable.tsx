"use client";

import Image from "next/image";
import Link from "next/link";
import type { User, UserStatus } from "@/types/user.type";
import { formatDate, timeAgo } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";

interface UserTableProps {
  users: User[];
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}

const statusConfig: Record<UserStatus, { label: string; className: string }> = {
  active:   { label: "Hoạt động",  className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" },
  inactive: { label: "Ngừng HĐ",   className: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300" },
  locked:   { label: "Bị khóa",    className: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" },
};

export default function UserTable({ users, onEdit, onDelete }: UserTableProps) {
  if (users.length === 0) {
    return (
      <EmptyState
        title="Không tìm thấy người dùng"
        description="Thử thay đổi bộ lọc hoặc thêm người dùng mới."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="pb-3 pr-4">Người dùng</th>
            <th className="pb-3 pr-4">Tài khoản</th>
            <th className="pb-3 pr-4">Nhóm quyền</th>
            <th className="pb-3 pr-4">Trạng thái</th>
            <th className="pb-3 pr-4">Đăng nhập gần nhất</th>
            <th className="pb-3 pr-4">Ngày tạo</th>
            <th className="pb-3 text-right">Thao tác</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {users.map((u) => {
            const status = statusConfig[u.status];
            return (
              <tr key={u.id} className="group hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                {/* Avatar + name */}
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-3">
                    <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                      {u.avatar_url ? (
                        <Image src={u.avatar_url} alt={u.full_name} fill className="object-cover" sizes="36px" />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-sm font-semibold text-slate-500 dark:text-slate-400">
                          {u.full_name.charAt(0).toUpperCase()}
                        </span>
                      )}
                    </div>
                    <div>
                      <Link
                        href={`/users/${u.id}`}
                        className="font-medium text-slate-900 dark:text-slate-100 hover:text-blue-600 hover:underline"
                      >
                        {u.full_name}
                      </Link>
                      <p className="text-xs text-slate-400 dark:text-slate-500">{u.email ?? "—"}</p>
                    </div>
                  </div>
                </td>
                {/* Username */}
                <td className="py-3 pr-4">
                  <code className="rounded bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-xs text-slate-700 dark:text-slate-300">
                    {u.username}
                  </code>
                  <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{u.phone ?? "—"}</p>
                </td>
                {/* Roles */}
                <td className="py-3 pr-4">
                  <div className="flex flex-wrap gap-1">
                    {u.roles.length === 0 ? (
                      <span className="text-xs text-slate-400 dark:text-slate-500">Chưa gán</span>
                    ) : (
                      u.roles.map((r) => (
                        <span
                          key={r.role_id}
                          className="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400"
                        >
                          {r.role_name}
                        </span>
                      ))
                    )}
                  </div>
                </td>
                {/* Status */}
                <td className="py-3 pr-4">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}>
                    {status.label}
                  </span>
                </td>
                {/* Last login */}
                <td className="py-3 pr-4 text-slate-500 dark:text-slate-400">{timeAgo(u.last_login_at)}</td>
                {/* Created */}
                <td className="py-3 pr-4 text-slate-500 dark:text-slate-400">{formatDate(u.created_at)}</td>
                {/* Actions */}
                <td className="py-3 text-right">
                  <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <Button variant="ghost" size="sm" onClick={() => onEdit(u)} title="Chỉnh sửa">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600"
                      onClick={() => onDelete(u)}
                      title="Xóa"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
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
