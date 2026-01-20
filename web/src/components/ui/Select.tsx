"use client";

import { SelectHTMLAttributes, forwardRef } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, className = "", id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="space-y-1">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-sm font-medium text-[var(--gruvbox-fg3)]"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={`
            w-full px-3 py-2 rounded
            bg-[var(--gruvbox-bg1)] border border-[var(--gruvbox-bg3)]
            text-[var(--gruvbox-fg)]
            focus:outline-none focus:border-[var(--gruvbox-orange)] focus:ring-1 focus:ring-[var(--gruvbox-orange)]
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? "border-[var(--gruvbox-red)]" : ""}
            ${className}
          `}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && (
          <p className="text-sm text-[var(--gruvbox-red)]">{error}</p>
        )}
      </div>
    );
  }
);

Select.displayName = "Select";
