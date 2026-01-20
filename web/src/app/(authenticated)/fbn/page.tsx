"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { FBNEntry, FBNMonthlyStat } from "@/types";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDate } from "@/lib/utils/format";

export default function FBNPage() {
  const router = useRouter();
  const { setError } = useError();
  const [monthlyStats, setMonthlyStats] = useState<FBNMonthlyStat[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const { data, error } = await supabase
        .from("fbn")
        .select("*")
        .order("date");

      if (error) throw error;

      const entries = data as FBNEntry[];

      // Apply USD to CAD conversion
      const convertedEntries = entries.map((entry) => {
        if (entry.currency === "USD") {
          const rate = entry.rate || 1;
          return {
            ...entry,
            deposit: entry.deposit * rate,
            asset: entry.asset * rate,
            fee: entry.fee * rate,
          };
        }
        return entry;
      });

      // Group by date
      const dateGroups: Record<string, { deposit: number; asset: number; fee: number }> = {};
      for (const entry of convertedEntries) {
        if (!dateGroups[entry.date]) {
          dateGroups[entry.date] = { deposit: 0, asset: 0, fee: 0 };
        }
        dateGroups[entry.date].deposit += entry.deposit || 0;
        dateGroups[entry.date].asset += entry.asset || 0;
        dateGroups[entry.date].fee += entry.fee || 0;
      }

      // Calculate PnL and percentage
      const dates = Object.keys(dateGroups).sort();
      const stats: FBNMonthlyStat[] = [];
      let prevAsset = 0;

      for (const date of dates) {
        const { deposit, asset, fee } = dateGroups[date];
        const pnl = asset - deposit - prevAsset;
        const pct = prevAsset !== 0 ? (pnl / prevAsset) * 100 : 0;

        stats.push({ date, deposit, asset, fee, pnl, pct });
        prevAsset = asset;
      }

      // Reverse to show most recent first
      stats.reverse();
      setMonthlyStats(stats);
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
      key: "a",
      action: () => router.push("/fbn/entry"),
      description: "Add entry",
    },
    {
      key: "y",
      action: () => router.push("/fbn/yearly"),
      description: "Yearly stats",
    },
    {
      key: "m",
      action: () => router.push("/fbn/assets/monthly"),
      description: "Monthly assets",
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
      render: (s: FBNMonthlyStat) => formatDate(s.date),
    },
    {
      key: "deposit",
      header: "Deposit",
      align: "right" as const,
      render: (s: FBNMonthlyStat) => <NumericCell value={s.deposit} format="currency" />,
    },
    {
      key: "asset",
      header: "Asset",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (s: FBNMonthlyStat) => <NumericCell value={s.asset} format="currency" />,
    },
    {
      key: "fee",
      header: "Fee",
      align: "right" as const,
      render: (s: FBNMonthlyStat) => <NumericCell value={s.fee} format="currency" />,
    },
    {
      key: "pnl",
      header: "PnL",
      align: "right" as const,
      render: (s: FBNMonthlyStat) => (
        <NumericCell value={s.pnl} format="currency" colorCode />
      ),
    },
    {
      key: "pct",
      header: "Pct",
      align: "right" as const,
      render: (s: FBNMonthlyStat) => (
        <NumericCell value={s.pct} format="percent" colorCode />
      ),
    },
  ];

  // Calculate totals
  const totalDeposit = monthlyStats.reduce((sum, s) => sum + s.deposit, 0);
  const currentAsset = monthlyStats.length > 0 ? monthlyStats[0].asset : 0;
  const totalFee = monthlyStats.reduce((sum, s) => sum + s.fee, 0);
  const totalPnl = monthlyStats.reduce((sum, s) => sum + s.pnl, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
          FBN Monthly Stats
        </h1>
        <div className="flex gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push("/fbn/entry")}
          >
            <kbd className="mr-1.5">a</kbd> Add Entry
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push("/fbn/yearly")}
          >
            <kbd className="mr-1.5">y</kbd> Yearly
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/fbn/assets/monthly")}
          >
            <kbd className="mr-1.5">m</kbd> Assets Matrix
          </Button>
        </div>
      </div>

      <Table
        data={monthlyStats}
        columns={columns}
        keyExtractor={(s) => s.date}
        emptyMessage="No FBN data available"
      />

      <div className="mt-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
        <div className="grid grid-cols-4 gap-4 text-sm font-data">
          <div>
            <span className="text-[var(--gruvbox-fg4)]">Total Deposit:</span>{" "}
            <span className="text-[var(--gruvbox-fg)]">
              {totalDeposit.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="text-[var(--gruvbox-fg4)]">Current Asset:</span>{" "}
            <span className="text-[var(--gruvbox-purple)]">
              {currentAsset.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="text-[var(--gruvbox-fg4)]">Total Fee:</span>{" "}
            <span className="text-[var(--gruvbox-fg)]">
              {totalFee.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="text-[var(--gruvbox-fg4)]">Total PnL:</span>{" "}
            <span
              className={
                totalPnl >= 0
                  ? "text-[var(--gruvbox-blue)]"
                  : "text-[var(--gruvbox-orange)]"
              }
            >
              {totalPnl.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
