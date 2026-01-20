"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      className = "",
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-colors rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gruvbox-orange)] disabled:opacity-50 disabled:cursor-not-allowed";

    const variants = {
      primary:
        "bg-[var(--gruvbox-orange)] text-[var(--gruvbox-bg)] hover:bg-[var(--gruvbox-orange-dim)]",
      secondary:
        "bg-[var(--gruvbox-bg2)] text-[var(--gruvbox-fg)] hover:bg-[var(--gruvbox-bg3)]",
      danger:
        "bg-[var(--gruvbox-red-dim)] text-[var(--gruvbox-fg)] hover:bg-[var(--gruvbox-red)]",
      ghost:
        "bg-transparent text-[var(--gruvbox-fg3)] hover:bg-[var(--gruvbox-bg1)] hover:text-[var(--gruvbox-fg)]",
    };

    const sizes = {
      sm: "px-2 py-1 text-xs",
      md: "px-3 py-1.5 text-sm",
      lg: "px-4 py-2 text-base",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {loading && <div className="spinner mr-2 w-4 h-4" />}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
