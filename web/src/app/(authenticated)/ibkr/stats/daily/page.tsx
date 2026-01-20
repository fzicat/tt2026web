"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase, toCamelCaseArray } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { Trade, DailyStat } from "@/types";
import { calculatePnL } from "@/lib/utils/fifo";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDate, getDayName } from "@/lib/utils/format";

export default function DailyStatsPage() {
  const router = useRouter();
  const { setError } = useError();
  const [stats, setStats] = useState<DailyStat[]>([]);
  const [totalPnl, setTotalPnl] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const { data: tradesData, error: tradesError } = await supabase
        .from("trades")
        .select("*")
        .order("date_time");

      if (tradesError) throw tradesError;

      let trades = toCamelCaseArray<Trade>(tradesData || []);
      trades = trades.filter((t) => t.symbol !== "USD.CAD");
      trades = calculatePnL(trades);

      // Group by date
      const dailyMap: Record<string, number> = {};
      for (const trade of trades) {
        const dateStr = trade.dateTime.split("T")[0];
        if (!dailyMap[dateStr]) dailyMap[dateStr] = 0;
        dailyMap[dateStr] += trade.realized_pnl ?? 0;
      }

      // Convert to array and add missing weekdays
      const dates = Object.keys(dailyMap).sort();
      if (dates.length === 0) {
        setStats([]);
        setTotalPnl(0);
        setLoading(false);
        return;
      }

      const minDate = new Date(dates[0]);
      const maxDate = new Date(dates[dates.length - 1]);

      const result: DailyStat[] = [];
      let total = 0;

      const currentDate = new Date(minDate);
      while (currentDate <= maxDate) {
        const dateStr = currentDate.toISOString().split("T")[0];
        const dayOfWeek = currentDate.getDay();
        const pnl = dailyMap[dateStr] ?? 0;

        // Include if weekday OR if has PnL
        if (dayOfWeek !== 0 && dayOfWeek !== 6 || pnl !== 0) {
          result.push({
            date: dateStr,
            dayName: getDayName(dateStr),
            realizedPnl: pnl,
          });
          total += pnl;
        }

        currentDate.setDate(currentDate.getDate() + 1);
      }

      // Reverse to show most recent first
      result.reverse();

      setStats(result);
      setTotalPnl(total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useKeyboard([
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
    {
      key: "date",
      header: "Date",
      className: "text-[var(--gruvbox-aqua)]",
      render: (s: DailyStat) => formatDate(s.date),
    },
    {
      key: "dayName",
      header: "Day",
      className: "text-[var(--gruvbox-yellow)]",
    },
    {
      key: "realizedPnl",
      header: "Realized PnL",
      align: "right" as const,
      render: (s: DailyStat) => (
        <NumericCell value={s.realizedPnl} format="currency" colorCode />
      ),
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
            Daily Stats
          </h1>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => router.push("/ibkr/stats/weekly")}
        >
          <kbd className="mr-1.5">w</kbd> Weekly
        </Button>
      </div>

      <Table
        data={stats}
        columns={columns}
        keyExtractor={(s) => s.date}
        emptyMessage="No daily stats available"
      />

      <div className="mt-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
        <div className="flex justify-between items-center font-data">
          <span className="text-[var(--gruvbox-fg4)] font-semibold">TOTAL</span>
          <span
            className={`text-lg font-bold ${
              totalPnl >= 0
                ? "text-[var(--gruvbox-blue)]"
                : "text-[var(--gruvbox-orange)]"
            }`}
          >
            {totalPnl.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
      </div>
    </div>
  );
}
