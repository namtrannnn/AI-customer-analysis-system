import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
}

const variantClass: Record<Variant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 shadow-sm shadow-blue-600/20 disabled:bg-blue-400",
  secondary:
    "border text-secondary hover:opacity-80 disabled:opacity-40 " +
    "[border-color:var(--border)] [background:var(--bg-surface-2)]",
  danger:
    "bg-red-600 text-white hover:bg-red-700 shadow-sm shadow-red-600/20 disabled:bg-red-400",
  ghost:
    "[color:var(--text-secondary)] hover:[background:var(--bg-surface-3)] disabled:opacity-40",
};

const sizeClass: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
  lg: "px-5 py-2.5 text-base gap-2",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      icon,
      children,
      className = "",
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`inline-flex items-center rounded-lg font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:cursor-not-allowed ${variantClass[variant]} ${sizeClass[size]} ${className}`}
        {...props}
      >
        {loading ? (
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
export default Button;
