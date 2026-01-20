"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { useKeyboard } from "@/lib/hooks/useKeyboard";
import { FBNEntry, FBN_ACCOUNTS } from "@/types";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { formatDate, formatCurrency } from "@/lib/utils/format";

interface MatrixRow {
  date: string;
  accounts: Record<string, number>;
  total: number;
}

export default function FBNMonthlyAssetsPage() {
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

      // Group by date
      const dateGroups: Record<string, Record<string, number>> = {};
      for (const entry of convertedEntries) {
        if (!dateGroups[entry.date]) {
          dateGroups[entry.date] = {};
        }
        dateGroups[entry.date][entry.account] = entry.asset;
      }

      // Convert to matrix rows
      const rows: MatrixRow[] = Object.entries(dateGroups)
        .map(([date, accounts]) => {
          const total = Object.values(accounts).reduce((sum, val) => sum + val, 0);
          return { date, accounts, total };
        })
        .sort((a, b) => b.date.localeCompare(a.date));

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
      key: "y",
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

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <kbd className="mr-1.5">q</kbd> Back
          </Button>
          <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
            FBN Monthly Assets Matrix
          </h1>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => router.push("/fbn/assets/yearly")}
        >
          <kbd className="mr-1.5">y</kbd> Yearly
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table font-data text-sm">
          <thead>
            <tr>
              <th className="text-left">Date</th>
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
              <tr key={row.date}>
                <td className="text-[var(--gruvbox-aqua)]">
                  {formatDate(row.date)}
                </td>
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
