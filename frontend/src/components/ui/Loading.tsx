interface LoadingProps {
  text?: string;
  fullPage?: boolean;
}

export default function Loading({
  text = "Đang tải...",
  fullPage = false,
}: LoadingProps) {
  if (fullPage) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner text={text} />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-16">
      <Spinner text={text} />
    </div>
  );
}

function Spinner({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-3">
      <svg
        className="h-8 w-8 animate-spin text-blue-600"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
        />
      </svg>
      <p className="text-sm text-slate-500 dark:text-slate-400">{text}</p>
    </div>
  );
}
