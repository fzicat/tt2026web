"use client";

import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="space-y-1">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-[var(--gruvbox-fg3)]"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            w-full px-3 py-2 rounded
            bg-[var(--gruvbox-bg1)] border border-[var(--gruvbox-bg3)]
            text-[var(--gruvbox-fg)] placeholder-[var(--gruvbox-fg4)]
            focus:outline-none focus:border-[var(--gruvbox-orange)] focus:ring-1 focus:ring-[var(--gruvbox-orange)]
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? "border-[var(--gruvbox-red)]" : ""}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="text-sm text-[var(--gruvbox-red)]">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
