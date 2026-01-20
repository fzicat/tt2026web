"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { FBNEntry, FBN_ACCOUNTS } from "@/types";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatCurrency } from "@/lib/utils/format";

interface MatrixRow {
  year: number;
  accounts: Record<string, number>;
  total: number;
}

export default function FBNYearlyAssetsPage() {
  const router = useRouter();
  const { setError } = useError();
  const [data, setData] = useState<MatrixRow[]>([]);
  const [loading, setLoading] = useState(true);

  const accountNames = FBN_ACCOUNTS.map((a) => a.name);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const { data: entries, error } = await supabase
        .from("fbn")
        .select("*")
        .order("date");

      if (error) throw error;

      // Apply USD to CAD conversion
      const convertedEntries = (entries as FBNEntry[]).map((entry) => {
        if (entry.currency === "USD") {
          const rate = entry.rate || 1;
          return { ...entry, asset: entry.asset * rate };
        }
        return entry;
      });

      // Group by year, taking the last date entry for each account
      const yearAccountGroups: Record<
        number,
        Record<string, { date: string; asset: number }>
      > = {};

      for (const entry of convertedEntries) {
        const year = parseInt(entry.date.split("-")[0]);
        if (!yearAccountGroups[year]) {
          yearAccountGroups[year] = {};
        }
        const existing = yearAccountGroups[year][entry.account];
        if (!existing || entry.date > existing.date) {
          yearAccountGroups[year][entry.account] = {
            date: entry.date,
            asset: entry.asset,
          };
        }
      }

      // Convert to matrix rows
      const rows: MatrixRow[] = Object.entries(yearAccountGroups)
        .map(([yearStr, accounts]) => {
          const year = parseInt(yearStr);
          const accountAssets: Record<string, number> = {};
          let total = 0;
          for (const [name, data] of Object.entries(accounts)) {
            accountAssets[name] = data.asset;
            total += data.asset;
          }
          return { year, accounts: accountAssets, total };
        })
        .sort((a, b) => b.year - a.year);

      setData(rows);
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

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <kbd className="mr-1.5">q</kbd> Back
          </Button>
          <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
            FBN Yearly Assets Matrix
          </h1>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => router.push("/fbn/assets/monthly")}
        >
          <kbd className="mr-1.5">m</kbd> Monthly
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table font-data text-sm">
          <thead>
            <tr>
              <th className="text-left">Year</th>
              {accountNames.map((name) => (
                <th key={name} className="text-right">
                  {name}
                </th>
              ))}
              <th className="text-right text-[var(--gruvbox-purple)] font-bold">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.year}>
                <td className="text-[var(--gruvbox-aqua)]">{row.year}</td>
                {accountNames.map((name) => (
                  <td key={name} className="text-right">
                    {row.accounts[name] !== undefined
                      ? formatCurrency(row.accounts[name])
                      : "-"}
                  </td>
                ))}
                <td className="text-right text-[var(--gruvbox-purple)] font-bold">
                  {formatCurrency(row.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
