interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export default function EmptyState({
  title = "Không có dữ liệu",
  description = "Chưa có dữ liệu nào để hiển thị.",
  action,
  icon,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon ?? (
        <svg
          className="mb-4 h-12 w-12 text-slate-300 dark:text-slate-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0H4m8-5v5"
          />
        </svg>
      )}
      <h3 className="mb-1 text-sm font-semibold text-slate-700 dark:text-slate-300">{title}</h3>
      <p className="mb-4 text-sm text-slate-400 dark:text-slate-500">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
