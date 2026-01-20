"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase, toCamelCaseArray } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { Trade } from "@/types";
import { calculatePnL, calculateCredit, applyMtmPrices } from "@/lib/utils/fifo";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDateTime } from "@/lib/utils/format";

export default function TradesPage() {
  const router = useRouter();
  const { setError } = useError();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const { data: tradesData, error: tradesError } = await supabase
        .from("trades")
        .select("*")
        .order("date_time", { ascending: false });

      if (tradesError) throw tradesError;

      const { data: pricesData, error: pricesError } = await supabase
        .from("market_price")
        .select("symbol, price");

      if (pricesError) throw pricesError;

      const marketPrices: Record<string, number> = {};
      (pricesData || []).forEach((p: { symbol: string; price: number }) => {
        marketPrices[p.symbol] = p.price;
      });

      let processedTrades = toCamelCaseArray<Trade>(tradesData || []);
      processedTrades = processedTrades.filter((t) => t.symbol !== "USD.CAD");
      // Need to sort by date ascending for FIFO, then sort back
      processedTrades.sort(
        (a, b) =>
          new Date(a.dateTime).getTime() - new Date(b.dateTime).getTime()
      );
      processedTrades = calculatePnL(processedTrades);
      processedTrades = calculateCredit(processedTrades);
      processedTrades = applyMtmPrices(processedTrades, marketPrices);
      // Sort back to descending
      processedTrades.sort(
        (a, b) =>
          new Date(b.dateTime).getTime() - new Date(a.dateTime).getTime()
      );

      setTrades(processedTrades);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useKeyboard([]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  const columns = [
    {
      key: "dateTime",
      header: "Date",
      className: "text-[var(--gruvbox-aqua)]",
      render: (t: Trade) => formatDateTime(t.dateTime),
    },
    {
      key: "symbol",
      header: "Symbol",
      className: "text-[var(--gruvbox-yellow)] font-semibold",
    },
    { key: "description", header: "Desc" },
    {
      key: "quantity",
      header: "Qty",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (t: Trade) => <NumericCell value={t.quantity} />,
    },
    {
      key: "tradePrice",
      header: "Price",
      align: "right" as const,
      className: "text-[var(--gruvbox-green)]",
      render: (t: Trade) => <NumericCell value={t.tradePrice} format="currency" />,
    },
    {
      key: "ibCommission",
      header: "Comm",
      align: "right" as const,
      render: (t: Trade) => <NumericCell value={t.ibCommission} format="currency" />,
    },
    {
      key: "openCloseIndicator",
      header: "O/C",
      align: "center" as const,
      render: (t: Trade) => t.openCloseIndicator || "-",
    },
    {
      key: "realized_pnl",
      header: "PnL",
      align: "right" as const,
      render: (t: Trade) => (
        <NumericCell value={t.realized_pnl} format="currency" colorCode />
      ),
    },
    {
      key: "remaining_qty",
      header: "Rem Qty",
      align: "right" as const,
      className: "text-[var(--gruvbox-blue)]",
      render: (t: Trade) => <NumericCell value={t.remaining_qty} />,
    },
    {
      key: "delta",
      header: "Delta",
      align: "right" as const,
      className: "text-[var(--gruvbox-yellow)]",
      render: (t: Trade) => (t.delta ? t.delta.toFixed(4) : "-"),
    },
    {
      key: "und_price",
      header: "Und Price",
      align: "right" as const,
      className: "text-[var(--gruvbox-yellow)]",
      render: (t: Trade) => <NumericCell value={t.und_price} format="currency" />,
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <kbd className="mr-1.5">q</kbd> Back
          </Button>
          <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
            All Trades
          </h1>
          <span className="text-[var(--gruvbox-fg4)] text-sm">
            ({trades.length} trades)
          </span>
        </div>
      </div>

      <Table
        data={trades}
        columns={columns}
        keyExtractor={(t) => t.tradeID}
        onRowClick={(t) =>
          router.push(`/ibkr/positions/${t.underlyingSymbol || t.symbol}`)
        }
        emptyMessage="No trades found"
      />
    </div>
  );
}
