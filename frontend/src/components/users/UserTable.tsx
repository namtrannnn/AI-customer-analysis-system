"use client";

import Image from "next/image";
import Link from "next/link";
import type { User, UserStatus } from "@/types/user.type";
import { formatDate, timeAgo } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import {
  Edit3,
  Trash2,
  ShieldCheck,
  CheckCircle2,
  CircleOff,
} from "lucide-react";

interface UserTableProps {
  users: User[];
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}

const ROLE_LABEL_MAP: Record<number, string> = {
  1: "Quản trị viên",
  2: "Quản lý",
  3: "Nhân viên",
};

const statusConfig: Record<
  UserStatus,
  {
    label: string;
    className: string;
    icon: React.ElementType;
  }
> = {
  active: {
    label: "Hoạt động",
    icon: CheckCircle2,
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  },
  inactive: {
    label: "Ngừng HĐ",
    icon: CircleOff,
    className:
      "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700",
  },
  deleted: {
    label: "Đã xóa",
    icon: CircleOff,
    className:
      "bg-red-50 text-red-700 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  },
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
    <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/50">
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <th className="px-4 py-3">Người dùng</th>
              <th className="px-4 py-3">Tài khoản</th>
              <th className="px-4 py-3">Nhóm quyền</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3">Đăng nhập gần nhất</th>
              <th className="px-4 py-3">Ngày tạo</th>
              <th className="px-4 py-3 text-right">Thao tác</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-700 dark:bg-slate-800">
            {users.map((user) => {
              const status = statusConfig[user.status] ?? statusConfig.inactive;
              const StatusIcon = status.icon;

              const firstChar =
                user.full_name?.trim()?.charAt(0)?.toUpperCase() || "U";

              const roleIds = user.role_ids ?? [];

              return (
                <tr
                  key={user.id}
                  className="group transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/40"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-slate-100 to-slate-200 ring-1 ring-slate-200 dark:from-slate-700 dark:to-slate-800 dark:ring-slate-600">
                        {user.avatar_url ? (
                          <Image
                            src={user.avatar_url}
                            alt={user.full_name}
                            fill
                            className="object-cover"
                            sizes="40px"
                          />
                        ) : (
                          <span className="flex h-full w-full items-center justify-center text-sm font-bold text-slate-500 dark:text-slate-300">
                            {firstChar}
                          </span>
                        )}
                      </div>

                      <div className="min-w-0">
                        <Link
                          href={`/users/${user.id}`}
                          className="line-clamp-1 font-semibold text-slate-900 hover:text-blue-600 hover:underline dark:text-slate-100"
                        >
                          {user.full_name}
                        </Link>

                        <p className="mt-0.5 line-clamp-1 text-xs text-slate-500 dark:text-slate-400">
                          {user.email ?? "Chưa có email"}
                        </p>
                      </div>
                    </div>
                  </td>

                  <td className="px-4 py-3">
                    <code className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                      @{user.username}
                    </code>

                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {user.phone ?? "Chưa có SĐT"}
                    </p>
                  </td>

                  <td className="px-4 py-3">
                    {roleIds.length === 0 ? (
                      <span className="text-xs text-slate-400 dark:text-slate-500">
                        Chưa gán
                      </span>
                    ) : (
                      <div className="flex max-w-[240px] flex-wrap gap-1.5">
                        {roleIds.slice(0, 2).map((roleId) => (
                          <span
                            key={roleId}
                            className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20"
                          >
                            <ShieldCheck className="h-3 w-3" />
                            {ROLE_LABEL_MAP[roleId] ?? `Role #${roleId}`}
                          </span>
                        ))}

                        {roleIds.length > 2 && (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                            +{roleIds.length - 2}
                          </span>
                        )}
                      </div>
                    )}
                  </td>

                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${status.className}`}
                    >
                      <StatusIcon className="h-3.5 w-3.5" />
                      {status.label}
                    </span>
                  </td>

                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400">
                    {user.last_login_at
                      ? timeAgo(user.last_login_at)
                      : "Chưa đăng nhập"}
                  </td>

                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400">
                    {formatDate(user.created_at)}
                  </td>

                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(user)}
                        title="Chỉnh sửa"
                      >
                        <Edit3 className="h-4 w-4" />
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                        onClick={() => onDelete(user)}
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
    </div>
  );
}
