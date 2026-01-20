"use client";

import { useError } from "@/lib/error-context";

export function ErrorBanner() {
  const { error, clearError } = useError();

  if (!error) return null;

  return (
    <div className="bg-[var(--gruvbox-red-dim)] border-b border-[var(--gruvbox-red)]">
      <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
        <span className="text-[var(--gruvbox-fg0)] text-sm">{error.message}</span>
        <button
          onClick={clearError}
          className="text-[var(--gruvbox-fg0)] hover:text-white transition-colors text-lg leading-none"
          aria-label="Dismiss error"
        >
          &times;
        </button>
      </div>
    </div>
  );
}
