"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase, toCamelCaseArray } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { Trade, WeeklyStat } from "@/types";
import { calculatePnL } from "@/lib/utils/fifo";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDate } from "@/lib/utils/format";

function getWeekEndingFriday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  // Calculate days until next Friday (or current Friday if today is Friday)
  const daysUntilFriday = day <= 5 ? 5 - day : 5 - day + 7;
  d.setDate(d.getDate() + daysUntilFriday);
  return d;
}

export default function WeeklyStatsPage() {
  const router = useRouter();
  const { setError } = useError();
  const [stats, setStats] = useState<WeeklyStat[]>([]);
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

      // Group by week ending Friday
      const weeklyMap: Record<string, number> = {};
      for (const trade of trades) {
        const tradeDate = new Date(trade.dateTime);
        const weekEnding = getWeekEndingFriday(tradeDate);
        const weekStr = weekEnding.toISOString().split("T")[0];
        if (!weeklyMap[weekStr]) weeklyMap[weekStr] = 0;
        weeklyMap[weekStr] += trade.realized_pnl ?? 0;
      }

      // Convert to array
      const result: WeeklyStat[] = Object.entries(weeklyMap)
        .map(([weekEnding, pnl]) => ({
          weekEnding,
          realizedPnl: pnl,
        }))
        .sort((a, b) => b.weekEnding.localeCompare(a.weekEnding));

      const total = result.reduce((sum, s) => sum + s.realizedPnl, 0);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  const columns = [
    {
      key: "weekEnding",
      header: "Week Ending",
      className: "text-[var(--gruvbox-aqua)]",
      render: (s: WeeklyStat) => formatDate(s.weekEnding),
    },
    {
      key: "realizedPnl",
      header: "Realized PnL",
      align: "right" as const,
      render: (s: WeeklyStat) => (
        <NumericCell value={s.realizedPnl} format="currency" colorCode />
      ),
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
            Weekly Stats (Ending Friday)
          </h1>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => router.push("/ibkr/stats/daily")}
        >
          Daily
        </Button>
      </div>

      <Table
        data={stats}
        columns={columns}
        keyExtractor={(s) => s.weekEnding}
        emptyMessage="No weekly stats available"
      />

      <div className="mt-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
        <div className="flex justify-between items-center font-data">
          <span className="text-[var(--gruvbox-fg4)] font-semibold">TOTAL</span>
          <span
            className={`text-lg font-bold ${totalPnl >= 0
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
