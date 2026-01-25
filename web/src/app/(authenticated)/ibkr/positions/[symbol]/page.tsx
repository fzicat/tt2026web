"use client";

import { useState, useEffect, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { supabase, toCamelCaseArray } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { Trade } from "@/types";
import { calculatePnL, calculateCredit, applyMtmPrices } from "@/lib/utils/fifo";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDateTime } from "@/lib/utils/format";

interface PositionSummary {
  symbol: string;
  bookPrice: number;
  stockQty: number;
  callQty: number;
  putQty: number;
  stockPnl: number;
  callPnl: number;
  putPnl: number;
}

export default function PositionDetailPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = use(params);
  const router = useRouter();
  const { setError } = useError();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [summary, setSummary] = useState<PositionSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch all trades
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

      // Process all trades first (FIFO needs all trades)
      let processedTrades = toCamelCaseArray<Trade>(tradesData || []);
      processedTrades = processedTrades.filter((t) => t.symbol !== "USD.CAD");
      processedTrades = calculatePnL(processedTrades);
      processedTrades = calculateCredit(processedTrades);
      processedTrades = applyMtmPrices(processedTrades, marketPrices);

      // Filter to symbol
      const symbolTrades = processedTrades.filter(
        (t) => t.symbol === symbol || t.underlyingSymbol === symbol
      );
      // Sort by date descending
      symbolTrades.sort(
        (a, b) =>
          new Date(b.dateTime).getTime() - new Date(a.dateTime).getTime()
      );

      setTrades(symbolTrades);

      // Calculate summary
      const stockTrades = symbolTrades.filter(
        (t) => t.putCall !== "C" && t.putCall !== "P"
      );
      const callTrades = symbolTrades.filter((t) => t.putCall === "C");
      const putTrades = symbolTrades.filter((t) => t.putCall === "P");

      const stockQty = stockTrades.reduce(
        (sum, t) => sum + (t.remaining_qty ?? 0),
        0
      );
      const callQty = callTrades.reduce(
        (sum, t) => sum + (t.remaining_qty ?? 0),
        0
      );
      const putQty = putTrades.reduce(
        (sum, t) => sum + (t.remaining_qty ?? 0),
        0
      );

      const stockPnl = stockTrades.reduce(
        (sum, t) => sum + (t.realized_pnl ?? 0),
        0
      );
      const callPnl = callTrades.reduce(
        (sum, t) => sum + (t.realized_pnl ?? 0),
        0
      );
      const putPnl = putTrades.reduce(
        (sum, t) => sum + (t.realized_pnl ?? 0),
        0
      );

      const creditSum = stockTrades.reduce((sum, t) => sum + (t.credit ?? 0), 0);
      const bookPrice = stockQty !== 0 ? creditSum / stockQty : 0;

      setSummary({
        symbol,
        bookPrice,
        stockQty,
        callQty,
        putQty,
        stockPnl,
        callPnl,
        putPnl,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [symbol, setError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
    { key: "description", header: "Description" },
    {
      key: "putCall",
      header: "P/C",
      align: "center" as const,
      render: (t: Trade) => t.putCall || "-",
    },
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
      header: "Realized PnL",
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
      key: "credit",
      header: "Credit",
      align: "right" as const,
      className: "text-[var(--gruvbox-blue)]",
      render: (t: Trade) => <NumericCell value={t.credit} format="currency" />,
    },
    {
      key: "delta",
      header: "Delta",
      align: "right" as const,
      className: "text-[var(--gruvbox-yellow)]",
      render: (t: Trade) =>
        t.delta ? t.delta.toFixed(4) : "-",
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
            Back
          </Button>
          <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
            Position: {symbol}
          </h1>
        </div>
      </div>

      {summary && (
        <div className="mb-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
          <div className="grid grid-cols-4 gap-4 text-sm font-data">
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Book Price:</span>{" "}
              <span className="text-[var(--gruvbox-fg)]">
                {summary.bookPrice.toFixed(2)}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Stock Qty:</span>{" "}
              <span className="text-[var(--gruvbox-purple)]">
                {summary.stockQty.toFixed(0)}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Call Qty:</span>{" "}
              <span className="text-[var(--gruvbox-purple)]">
                {summary.callQty.toFixed(0)}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Put Qty:</span>{" "}
              <span className="text-[var(--gruvbox-purple)]">
                {summary.putQty.toFixed(0)}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Stock PnL:</span>{" "}
              <NumericCell value={summary.stockPnl} format="currency" colorCode />
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Call PnL:</span>{" "}
              <NumericCell value={summary.callPnl} format="currency" colorCode />
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Put PnL:</span>{" "}
              <NumericCell value={summary.putPnl} format="currency" colorCode />
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Total PnL:</span>{" "}
              <NumericCell
                value={summary.stockPnl + summary.callPnl + summary.putPnl}
                format="currency"
                colorCode
              />
            </div>
          </div>
        </div>
      )}

      <Table
        data={trades}
        columns={columns}
        keyExtractor={(t) => t.tradeID}
        emptyMessage={`No trades found for ${symbol}`}
      />
    </div>
  );
}
