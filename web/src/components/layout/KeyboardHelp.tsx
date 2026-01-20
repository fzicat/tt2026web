"use client";

interface KeyBinding {
  key: string;
  description: string;
  ctrl?: boolean;
  shift?: boolean;
}

interface KeyboardHelpProps {
  bindings: KeyBinding[];
  onClose: () => void;
}

export function KeyboardHelp({ bindings, onClose }: KeyboardHelpProps) {
  // Group bindings by type
  const globalBindings = bindings.filter((b) =>
    ["?", "Escape", "1", "2", "3", "q"].includes(b.key)
  );
  const pageBindings = bindings.filter(
    (b) => !["?", "Escape", "1", "2", "3", "q"].includes(b.key)
  );

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-[var(--gruvbox-bg)] border border-[var(--gruvbox-bg3)] rounded-lg shadow-xl max-w-lg w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-[var(--gruvbox-bg2)] px-4 py-3 flex items-center justify-between">
          <h2 className="text-[var(--gruvbox-orange)] font-semibold">
            Keyboard Shortcuts
          </h2>
          <button
            onClick={onClose}
            className="text-[var(--gruvbox-fg4)] hover:text-[var(--gruvbox-fg)] transition-colors"
          >
            <kbd>Esc</kbd>
          </button>
        </div>

        <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
          {globalBindings.length > 0 && (
            <div>
              <h3 className="text-[var(--gruvbox-fg3)] text-xs uppercase tracking-wider mb-2">
                Global
              </h3>
              <div className="space-y-1">
                {globalBindings.map((binding, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-[var(--gruvbox-fg2)] text-sm">
                      {binding.description}
                    </span>
                    <kbd>
                      {binding.ctrl && "Ctrl+"}
                      {binding.shift && "Shift+"}
                      {binding.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          )}

          {pageBindings.length > 0 && (
            <div>
              <h3 className="text-[var(--gruvbox-fg3)] text-xs uppercase tracking-wider mb-2">
                Page Actions
              </h3>
              <div className="space-y-1">
                {pageBindings.map((binding, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-[var(--gruvbox-fg2)] text-sm">
                      {binding.description}
                    </span>
                    <kbd>
                      {binding.ctrl && "Ctrl+"}
                      {binding.shift && "Shift+"}
                      {binding.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
