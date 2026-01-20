"use client";

import { useEffect, useCallback, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

interface KeyBinding {
  key: string;
  action: () => void;
  description: string;
  ctrl?: boolean;
  shift?: boolean;
}

export function useKeyboard(bindings: KeyBinding[] = []) {
  const router = useRouter();
  const pathname = usePathname();
  const [showHelp, setShowHelp] = useState(false);

  // Global bindings
  const globalBindings: KeyBinding[] = [
    {
      key: "?",
      action: () => setShowHelp((prev) => !prev),
      description: "Toggle help overlay",
    },
    {
      key: "Escape",
      action: () => setShowHelp(false),
      description: "Close overlay",
    },
    {
      key: "1",
      action: () => router.push("/ibkr"),
      description: "Go to IBKR",
    },
    {
      key: "2",
      action: () => router.push("/fbn"),
      description: "Go to FBN",
    },
    {
      key: "3",
      action: () => router.push("/equity"),
      description: "Go to Equity",
    },
    {
      key: "q",
      action: () => {
        // Go back or home based on current path
        if (pathname === "/ibkr" || pathname === "/fbn" || pathname === "/equity") {
          // Already at module root, do nothing or could go to login
        } else {
          router.back();
        }
      },
      description: "Go back",
    },
  ];

  const allBindings = [...globalBindings, ...bindings];

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't trigger if typing in an input
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        // Only allow Escape when typing
        if (event.key !== "Escape") {
          return;
        }
      }

      const binding = allBindings.find(
        (b) =>
          b.key.toLowerCase() === event.key.toLowerCase() &&
          (b.ctrl === undefined || b.ctrl === event.ctrlKey) &&
          (b.shift === undefined || b.shift === event.shiftKey)
      );

      if (binding) {
        event.preventDefault();
        binding.action();
      }
    },
    [allBindings]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return { showHelp, setShowHelp, bindings: allBindings };
}

export function useListNavigation<T>(
  items: T[],
  onSelect: (item: T, index: number) => void
) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const bindings: KeyBinding[] = [
    {
      key: "j",
      action: () => setSelectedIndex((i) => Math.min(i + 1, items.length - 1)),
      description: "Move down",
    },
    {
      key: "k",
      action: () => setSelectedIndex((i) => Math.max(i - 1, 0)),
      description: "Move up",
    },
    {
      key: "ArrowDown",
      action: () => setSelectedIndex((i) => Math.min(i + 1, items.length - 1)),
      description: "Move down",
    },
    {
      key: "ArrowUp",
      action: () => setSelectedIndex((i) => Math.max(i - 1, 0)),
      description: "Move up",
    },
    {
      key: "Enter",
      action: () => {
        if (items[selectedIndex]) {
          onSelect(items[selectedIndex], selectedIndex);
        }
      },
      description: "Select item",
    },
  ];

  return { selectedIndex, setSelectedIndex, bindings };
}
