"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const menuItems = [
  {
    label: "Tổng quan",
    href: "/dashboard",
  },
  {
    label: "Khách hàng",
    href: "/customers",
  },
  {
    label: "Người dùng",
    href: "/users",
  },
  {
    label: "Nhóm quyền",
    href: "/roles",
  },
  {
    label: "Phân quyền",
    href: "/permissions",
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center border-b border-slate-200 px-6">
        <h1 className="text-lg font-bold text-blue-600">AI Customer</h1>
      </div>

      <nav className="space-y-1 p-4">
        {menuItems.map((item) => {
          const active = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                active
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
