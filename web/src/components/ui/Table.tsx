"use client";

import { ReactNode } from "react";

interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "center" | "right";
  className?: string;
  render?: (item: T, index: number) => ReactNode;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  title?: string;
  onRowClick?: (item: T, index: number) => void;
  keyExtractor?: (item: T, index: number) => string;
  emptyMessage?: string;
  rowClassName?: (item: T, index: number) => string;
}

export function Table<T>({
  data,
  columns,
  title,
  onRowClick,
  keyExtractor,
  emptyMessage = "No data available",
  rowClassName,
}: TableProps<T>) {
  const getKey = (item: T, index: number) => {
    if (keyExtractor) return keyExtractor(item, index);
    return String(index);
  };

  const alignClass = {
    left: "text-left",
    center: "text-center",
    right: "text-right",
  };

  return (
    <div className="overflow-x-auto">
      {title && (
        <h3 className="text-[var(--gruvbox-yellow)] font-semibold mb-2">
          {title}
        </h3>
      )}
      <table className="data-table font-data text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`${alignClass[col.align || "left"]} ${col.className || ""}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="text-center py-8 text-[var(--gruvbox-fg4)]"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, index) => {
              const dynamicRowClass = rowClassName ? rowClassName(item, index) : "";
              const classes = [
                onRowClick ? "cursor-pointer" : "",
                dynamicRowClass,
              ].filter(Boolean).join(" ");
              return (
                <tr
                  key={getKey(item, index)}
                  onClick={() => onRowClick?.(item, index)}
                  className={classes}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`${alignClass[col.align || "left"]} ${col.className || ""}`}
                    >
                      {col.render
                        ? col.render(item, index)
                        : String((item as Record<string, unknown>)[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

// Helper component for numeric values with color coding
export function NumericCell({
  value,
  format = "number",
  colorCode = false,
  className = "",
}: {
  value: number | null | undefined;
  format?: "number" | "currency" | "percent";
  colorCode?: boolean;
  className?: string;
}) {
  if (value === null || value === undefined || value === 0) {
    return <span className="text-[var(--gruvbox-fg4)]">-</span>;
  }

  const formatted = (() => {
    switch (format) {
      case "currency":
        return value.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      case "percent":
        return `${value.toFixed(2)}%`;
      default:
        return value.toLocaleString("en-US", {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        });
    }
  })();

  const colorClass = colorCode
    ? value > 0
      ? "text-[var(--gruvbox-blue)]"
      : value < 0
        ? "text-[var(--gruvbox-orange)]"
        : ""
    : "";

  return <span className={`${colorClass} ${className}`}>{formatted}</span>;
}
