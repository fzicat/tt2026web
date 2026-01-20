"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase, toCamelCaseArray } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard, useListNavigation } from "@/lib/hooks/useKeyboard";
import { Trade, Position } from "@/types";
import {
  calculatePnL,
  calculateCredit,
  applyMtmPrices,
  calculatePositions,
  calculateTotals,
} from "@/lib/utils/fifo";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { KeyboardHelp } from "@/components/layout/KeyboardHelp";

export default function IBKRPage() {
  const router = useRouter();
  const { setError } = useError();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [totals, setTotals] = useState<ReturnType<typeof calculateTotals> | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [updatingMtm, setUpdatingMtm] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch trades
      const { data: tradesData, error: tradesError } = await supabase
        .from("trades")
        .select("*")
        .order("date_time");

      if (tradesError) throw tradesError;

      // Fetch market prices
      const { data: pricesData, error: pricesError } = await supabase
        .from("market_price")
        .select("symbol, price");

      if (pricesError) throw pricesError;

      const marketPrices: Record<string, number> = {};
      (pricesData || []).forEach((p: { symbol: string; price: number }) => {
        marketPrices[p.symbol] = p.price;
      });

      // Process trades
      let processedTrades = toCamelCaseArray<Trade>(tradesData || []);
      // Filter out USD.CAD
      processedTrades = processedTrades.filter((t) => t.symbol !== "USD.CAD");
      processedTrades = calculatePnL(processedTrades);
      processedTrades = calculateCredit(processedTrades);
      processedTrades = applyMtmPrices(processedTrades, marketPrices);

      setTrades(processedTrades);

      // Calculate positions
      const totalMtm = processedTrades.reduce(
        (sum, t) => sum + (t.mtm_value ?? 0),
        0
      );
      const positionsData = calculatePositions(processedTrades, totalMtm);
      // Sort by MTM descending
      positionsData.sort((a, b) => b.mtm - a.mtm);
      setPositions(positionsData);
      setTotals(calculateTotals(positionsData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleImport = async () => {
    try {
      setImporting(true);
      // Call the import API endpoint
      const res = await fetch("/api/ibkr/import", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Import failed");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const handleUpdateMtm = async () => {
    try {
      setUpdatingMtm(true);
      const res = await fetch("/api/ibkr/mtm", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "MTM update failed");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "MTM update failed");
    } finally {
      setUpdatingMtm(false);
    }
  };

  const { selectedIndex, bindings: listBindings } = useListNavigation(
    positions,
    (position) => router.push(`/ibkr/positions/${position.symbol}`)
  );

  const { showHelp, setShowHelp, bindings } = useKeyboard([
    ...listBindings,
    {
      key: "i",
      action: handleImport,
      description: "Import trades",
    },
    {
      key: "m",
      action: handleUpdateMtm,
      description: "Update MTM prices",
    },
    {
      key: "l",
      action: () => router.push("/ibkr/positions"),
      description: "List all positions",
    },
    {
      key: "t",
      action: () => router.push("/ibkr/trades"),
      description: "View all trades",
    },
    {
      key: "s",
      action: () => router.push("/ibkr/stats/daily"),
      description: "Daily stats",
    },
    {
      key: "w",
      action: () => router.push("/ibkr/stats/weekly"),
      description: "Weekly stats",
    },
  ]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  const columns = [
    { key: "symbol", header: "Symbol", className: "text-[var(--gruvbox-yellow)] font-semibold" },
    {
      key: "value",
      header: "Value",
      align: "right" as const,
      render: (p: Position) => <NumericCell value={p.value} format="currency" />,
    },
    {
      key: "mtm",
      header: "MTM",
      align: "right" as const,
      className: "text-[var(--gruvbox-blue)]",
      render: (p: Position) => <NumericCell value={p.mtm} format="currency" />,
    },
    {
      key: "mtmPercent",
      header: "MTM %",
      align: "right" as const,
      render: (p: Position) => <NumericCell value={p.mtmPercent} format="percent" />,
    },
    {
      key: "targetPercent",
      header: "Tgt %",
      align: "right" as const,
      className: "text-[var(--gruvbox-aqua)]",
      render: (p: Position) => (
        <span
          className={
            Math.abs(p.mtmPercent - p.targetPercent) <= 2
              ? "text-[var(--gruvbox-green)]"
              : "text-[var(--gruvbox-red)]"
          }
        >
          {p.targetPercent > 0 ? `${p.targetPercent.toFixed(2)}%` : "-"}
        </span>
      ),
    },
    {
      key: "unrealizedPnl",
      header: "Unrlzd PnL",
      align: "right" as const,
      render: (p: Position) => (
        <NumericCell value={p.unrealizedPnl} format="currency" colorCode />
      ),
    },
    {
      key: "stockQty",
      header: "Stock",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (p: Position) => <NumericCell value={p.stockQty} />,
    },
    {
      key: "callQty",
      header: "Call",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (p: Position) => <NumericCell value={p.callQty} />,
    },
    {
      key: "putQty",
      header: "Put",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (p: Position) => <NumericCell value={p.putQty} />,
    },
    {
      key: "stockPnl",
      header: "Stk PnL",
      align: "right" as const,
      render: (p: Position) => (
        <NumericCell value={p.stockPnl} format="currency" colorCode />
      ),
    },
    {
      key: "callPnl",
      header: "Call PnL",
      align: "right" as const,
      render: (p: Position) => (
        <NumericCell value={p.callPnl} format="currency" colorCode />
      ),
    },
    {
      key: "putPnl",
      header: "Put PnL",
      align: "right" as const,
      render: (p: Position) => (
        <NumericCell value={p.putPnl} format="currency" colorCode />
      ),
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
          IBKR Positions
        </h1>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleImport}
            loading={importing}
          >
            <kbd className="mr-1.5">i</kbd> Import
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleUpdateMtm}
            loading={updatingMtm}
          >
            <kbd className="mr-1.5">m</kbd> Update MTM
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/ibkr/trades")}
          >
            <kbd className="mr-1.5">t</kbd> Trades
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/ibkr/stats/daily")}
          >
            <kbd className="mr-1.5">s</kbd> Stats
          </Button>
        </div>
      </div>

      <Table
        data={positions}
        columns={columns}
        selectedIndex={selectedIndex}
        onRowClick={(position) =>
          router.push(`/ibkr/positions/${position.symbol}`)
        }
        keyExtractor={(p) => p.symbol}
        emptyMessage="No positions found"
      />

      {totals && (
        <div className="mt-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
          <div className="grid grid-cols-4 gap-4 text-sm font-data">
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Total Value:</span>{" "}
              <span className="text-[var(--gruvbox-fg)]">
                {totals.totalValue.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Total MTM:</span>{" "}
              <span className="text-[var(--gruvbox-blue)]">
                {totals.totalMtm.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Unrealized PnL:</span>{" "}
              <span
                className={
                  totals.totalUnrealizedPnl >= 0
                    ? "text-[var(--gruvbox-blue)]"
                    : "text-[var(--gruvbox-orange)]"
                }
              >
                {totals.totalUnrealizedPnl.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Realized PnL:</span>{" "}
              <span
                className={
                  totals.totalStockPnl + totals.totalCallPnl + totals.totalPutPnl >= 0
                    ? "text-[var(--gruvbox-blue)]"
                    : "text-[var(--gruvbox-orange)]"
                }
              >
                {(
                  totals.totalStockPnl +
                  totals.totalCallPnl +
                  totals.totalPutPnl
                ).toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>
      )}

      {showHelp && (
        <KeyboardHelp bindings={bindings} onClose={() => setShowHelp(false)} />
      )}
    </div>
  );
}
