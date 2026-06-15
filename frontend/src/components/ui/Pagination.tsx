"use client";

interface PaginationProps {
  page: number;
  totalPages: number;
  totalItems?: number;
  label?: string;
  onPageChange: (page: number) => void;
}

function getPageItems(page: number, totalPages: number): (number | "...")[] {
  return Array.from({ length: totalPages }, (_, i) => i + 1)
    .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
    .reduce<(number | "...")[]>((acc, p, idx, arr) => {
      if (
        idx > 0 &&
        typeof arr[idx - 1] === "number" &&
        p - (arr[idx - 1] as number) > 1
      ) {
        acc.push("...");
      }

      acc.push(p);
      return acc;
    }, []);
}

export default function Pagination({
  page,
  totalPages,
  totalItems,
  label = "bản ghi",
  onPageChange,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pageItems = getPageItems(page, totalPages);

  function goToPage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) return;
    onPageChange(nextPage);
  }

  return (
    <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/40 sm:flex-row sm:items-center sm:justify-between sm:px-5">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {typeof totalItems === "number" ? `${totalItems} ${label} · ` : ""}
        {totalPages} trang
      </p>

      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => goToPage(page - 1)}
          disabled={page <= 1}
          className="flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          ← Trước
        </button>

        {pageItems.map((item, index) =>
          item === "..." ? (
            <span
              key={`ellipsis-${index}`}
              className="px-1.5 text-sm font-bold text-slate-400"
            >
              …
            </span>
          ) : (
            <button
              type="button"
              key={item}
              onClick={() => goToPage(item)}
              className={`flex h-9 min-w-9 items-center justify-center rounded-xl border text-xs font-bold transition ${
                page === item
                  ? "border-blue-600 bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                  : "border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              }`}
            >
              {item}
            </button>
          ),
        )}

        <button
          type="button"
          onClick={() => goToPage(page + 1)}
          disabled={page >= totalPages}
          className="flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Sau →
        </button>
      </div>
    </div>
  );
}
