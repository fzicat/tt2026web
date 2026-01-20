"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { FBNEntry, FBNYearlyStat } from "@/types";
import { Table, NumericCell } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

export default function FBNYearlyPage() {
  const router = useRouter();
  const { setError } = useError();
  const [yearlyStats, setYearlyStats] = useState<FBNYearlyStat[]>([]);
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

      // Group by date first, then by year
      const dateGroups: Record<string, { deposit: number; asset: number; fee: number }> = {};
      for (const entry of convertedEntries) {
        if (!dateGroups[entry.date]) {
          dateGroups[entry.date] = { deposit: 0, asset: 0, fee: 0 };
        }
        dateGroups[entry.date].deposit += entry.deposit || 0;
        dateGroups[entry.date].asset += entry.asset || 0;
        dateGroups[entry.date].fee += entry.fee || 0;
      }

      // Group by year
      const yearGroups: Record<number, { deposit: number; lastAsset: number; fee: number; lastDate: string }> = {};
      for (const [date, values] of Object.entries(dateGroups)) {
        const year = parseInt(date.split("-")[0]);
        if (!yearGroups[year]) {
          yearGroups[year] = { deposit: 0, lastAsset: 0, fee: 0, lastDate: "" };
        }
        yearGroups[year].deposit += values.deposit;
        yearGroups[year].fee += values.fee;
        if (date > yearGroups[year].lastDate) {
          yearGroups[year].lastDate = date;
          yearGroups[year].lastAsset = values.asset;
        }
      }

      // Calculate PnL and percentage
      const years = Object.keys(yearGroups).map(Number).sort();
      const stats: FBNYearlyStat[] = [];
      let prevAsset = 0;

      for (const year of years) {
        const { deposit, lastAsset, fee } = yearGroups[year];
        const pnl = lastAsset - deposit - prevAsset;
        const pct = prevAsset !== 0 ? (pnl / prevAsset) * 100 : 0;

        stats.push({ year, deposit, asset: lastAsset, fee, pnl, pct });
        prevAsset = lastAsset;
      }

      // Reverse to show most recent first
      stats.reverse();
      setYearlyStats(stats);
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
      key: "m",
      action: () => router.push("/fbn"),
      description: "Monthly stats",
    },
    {
      key: "a",
      action: () => router.push("/fbn/assets/yearly"),
      description: "Yearly assets",
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
      key: "year",
      header: "Year",
      className: "text-[var(--gruvbox-aqua)]",
      render: (s: FBNYearlyStat) => s.year.toString(),
    },
    {
      key: "deposit",
      header: "Deposit",
      align: "right" as const,
      render: (s: FBNYearlyStat) => <NumericCell value={s.deposit} format="currency" />,
    },
    {
      key: "asset",
      header: "Asset",
      align: "right" as const,
      className: "text-[var(--gruvbox-purple)]",
      render: (s: FBNYearlyStat) => <NumericCell value={s.asset} format="currency" />,
    },
    {
      key: "fee",
      header: "Fee",
      align: "right" as const,
      render: (s: FBNYearlyStat) => <NumericCell value={s.fee} format="currency" />,
    },
    {
      key: "pnl",
      header: "PnL",
      align: "right" as const,
      render: (s: FBNYearlyStat) => (
        <NumericCell value={s.pnl} format="currency" colorCode />
      ),
    },
    {
      key: "pct",
      header: "Pct",
      align: "right" as const,
      render: (s: FBNYearlyStat) => (
        <NumericCell value={s.pct} format="percent" colorCode />
      ),
    },
  ];

  // Calculate totals
  const totalDeposit = yearlyStats.reduce((sum, s) => sum + s.deposit, 0);
  const currentAsset = yearlyStats.length > 0 ? yearlyStats[0].asset : 0;
  const totalFee = yearlyStats.reduce((sum, s) => sum + s.fee, 0);
  const totalPnl = yearlyStats.reduce((sum, s) => sum + s.pnl, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <kbd className="mr-1.5">q</kbd> Back
          </Button>
          <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
            FBN Yearly Stats
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push("/fbn")}
          >
            <kbd className="mr-1.5">m</kbd> Monthly
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/fbn/assets/yearly")}
          >
            <kbd className="mr-1.5">a</kbd> Assets Matrix
          </Button>
        </div>
      </div>

      <Table
        data={yearlyStats}
        columns={columns}
        keyExtractor={(s) => s.year.toString()}
        emptyMessage="No yearly stats available"
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
