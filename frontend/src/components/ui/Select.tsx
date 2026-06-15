"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export interface SelectOption<T extends string = string> {
  value: T;
  label: string;
}

interface SelectProps<T extends string = string> {
  value: T;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
}

export default function Select<T extends string = string>({
  value,
  options,
  onChange,
  placeholder = "Chọn",
  ariaLabel,
  className = "",
}: SelectProps<T>) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = options.find((item) => item.value === value);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className={`relative min-w-[170px] ${className}`}>
      <button
        type="button"
        aria-label={ariaLabel}
        onClick={() => setOpen((prev) => !prev)}
        className="
          flex h-10 w-full items-center justify-between gap-3 rounded-xl border px-3.5 text-sm font-medium
          outline-none transition-all duration-150
          [background:var(--bg-surface)]
          [border-color:var(--border)]
          [color:var(--text-secondary)]
          hover:[background:var(--bg-surface-2)]
          focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
        "
      >
        <span className="truncate">{selected?.label ?? placeholder}</span>

        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div
          className="
            absolute left-0 top-full z-40 mt-2 w-full overflow-hidden rounded-xl border p-1 shadow-xl
            [background:var(--bg-surface)]
            [border-color:var(--border)]
          "
        >
          {options.map((item) => {
            const active = item.value === value;

            return (
              <button
                key={item.value}
                type="button"
                onClick={() => {
                  onChange(item.value);
                  setOpen(false);
                }}
                className={`
                  flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors
                  ${
                    active
                      ? "bg-blue-600 text-white"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                  }
                `}
              >
                <span className="truncate">{item.label}</span>

                {active && <Check className="h-4 w-4 shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
