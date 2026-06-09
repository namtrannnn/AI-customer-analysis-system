import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, leftIcon, className = "", id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            {label}
            {props.required && <span className="ml-1 text-red-500">*</span>}
          </label>
        )}

        <div className="relative">
          {leftIcon && (
            <span
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center"
              style={{ color: "var(--text-muted)" }}
            >
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={`w-full rounded-lg border px-3 py-2 text-sm outline-none transition-all duration-150
              placeholder-[color:var(--text-muted)]
              [background:var(--bg-surface)]
              [color:var(--text-primary)]
              ${leftIcon ? "pl-9" : ""}
              ${
                error
                  ? "border-red-400 focus:border-red-500 focus:ring-2 focus:ring-red-500/20"
                  : "[border-color:var(--border)] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              }
              disabled:cursor-not-allowed disabled:opacity-50
              ${className}`}
            style={{}}
            {...props}
          />
        </div>

        {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
        {hint && !error && (
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {hint}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
export default Input;
