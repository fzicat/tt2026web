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

  // Partition trades into 3 categories
  const optionsTrades = trades.filter(
    (t) => t.putCall === "C" || t.putCall === "P"
  );
  const openOptionsTrades = optionsTrades.filter(
    (t) => t.openCloseIndicator === "O"
  );
  const closingOptionsTrades = optionsTrades.filter(
    (t) => t.openCloseIndicator === "C"
  );
  const stockTrades = trades.filter(
    (t) => t.putCall !== "C" && t.putCall !== "P"
  );

  // Base column definitions
  const dateColumn = {
    key: "dateTime",
    header: "Date",
    className: "text-[var(--gruvbox-aqua)]",
    render: (t: Trade) => formatDateTime(t.dateTime),
  };
  const descColumn = { key: "description", header: "Description" };
  const qtyColumn = {
    key: "quantity",
    header: "Qty",
    align: "right" as const,
    className: "text-[var(--gruvbox-purple)]",
    render: (t: Trade) => <NumericCell value={t.quantity} />,
  };
  const priceColumn = {
    key: "tradePrice",
    header: "Price",
    align: "right" as const,
    className: "text-[var(--gruvbox-green)]",
    render: (t: Trade) => <NumericCell value={t.tradePrice} format="currency" />,
  };
  const commColumn = {
    key: "ibCommission",
    header: "Comm",
    align: "right" as const,
    render: (t: Trade) => <NumericCell value={t.ibCommission} format="currency" />,
  };
  const ocColumn = {
    key: "openCloseIndicator",
    header: "O/C",
    align: "center" as const,
    render: (t: Trade) => t.openCloseIndicator || "-",
  };
  const pnlColumn = {
    key: "realized_pnl",
    header: "Realized PnL",
    align: "right" as const,
    render: (t: Trade) => (
      <NumericCell value={t.realized_pnl} format="currency" colorCode />
    ),
  };
  const remQtyColumn = {
    key: "remaining_qty",
    header: "Rem Qty",
    align: "right" as const,
    className: "text-[var(--gruvbox-blue)]",
    render: (t: Trade) => <NumericCell value={t.remaining_qty} />,
  };
  const creditColumn = {
    key: "credit",
    header: "Credit",
    align: "right" as const,
    className: "text-[var(--gruvbox-blue)]",
    render: (t: Trade) => <NumericCell value={t.credit} format="currency" />,
  };
  const deltaColumn = {
    key: "delta",
    header: "Delta",
    align: "right" as const,
    className: "text-[var(--gruvbox-yellow)]",
    render: (t: Trade) => (t.delta ? t.delta.toFixed(4) : "-"),
  };
  const undPriceColumn = {
    key: "und_price",
    header: "Und Price",
    align: "right" as const,
    className: "text-[var(--gruvbox-yellow)]",
    render: (t: Trade) => <NumericCell value={t.und_price} format="currency" />,
  };

  // Stock Trades: Date, Desc, Qty, Price, Comm, O/C, Realized PnL, Rem Qty, Credit
  // (removed: P/C, Delta, Und Price)
  const stockColumns = [
    dateColumn,
    descColumn,
    qtyColumn,
    priceColumn,
    commColumn,
    ocColumn,
    pnlColumn,
    remQtyColumn,
    creditColumn,
  ];

  // Closing Options: Date, Desc, Qty, Price, Comm, O/C, Realized PnL
  // (removed: P/C, Rem Qty, Credit, Delta, Und Price)
  const closingOptionsColumns = [
    dateColumn,
    descColumn,
    qtyColumn,
    priceColumn,
    commColumn,
    ocColumn,
    pnlColumn,
  ];

  // Open Options: Date, Desc, Qty, Price, Comm, O/C, Rem Qty, Credit, Delta, Und Price
  // (removed: P/C, Realized PnL)
  const openOptionsColumns = [
    dateColumn,
    descColumn,
    qtyColumn,
    priceColumn,
    commColumn,
    ocColumn,
    remQtyColumn,
    creditColumn,
    deltaColumn,
    undPriceColumn,
  ];

  // Row class function for dimming closed positions (remaining_qty is 0, null, or undefined)
  const getDimmedRowClass = (t: Trade) =>
    !t.remaining_qty || t.remaining_qty === 0 ? "row-dimmed" : "";

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

      {/* Open Options Table */}
      {openOptionsTrades.length > 0 && (
        <div className="mb-6">
          <Table
            title={`Open Options: ${symbol}`}
            data={openOptionsTrades}
            columns={openOptionsColumns}
            keyExtractor={(t) => t.tradeID}
            rowClassName={getDimmedRowClass}
          />
        </div>
      )}

      {/* Closing Options Table */}
      {closingOptionsTrades.length > 0 && (
        <div className="mb-6">
          <Table
            title={`Closing Options: ${symbol}`}
            data={closingOptionsTrades}
            columns={closingOptionsColumns}
            keyExtractor={(t) => t.tradeID}
          />
        </div>
      )}

      {/* Stock Trades Table */}
      {stockTrades.length > 0 && (
        <div className="mb-6">
          <Table
            title={`Stock Trades: ${symbol}`}
            data={stockTrades}
            columns={stockColumns}
            keyExtractor={(t) => t.tradeID}
            rowClassName={getDimmedRowClass}
          />
        </div>
      )}

      {/* Show message if no trades */}
      {openOptionsTrades.length === 0 &&
        closingOptionsTrades.length === 0 &&
        stockTrades.length === 0 && (
          <div className="text-center py-8 text-[var(--gruvbox-fg4)]">
            No trades found for {symbol}
          </div>
        )}
    </div>
  );
}

