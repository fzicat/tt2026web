"use client";

import { useState, FormEvent, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { EQUITY_ACCOUNTS, EQUITY_CATEGORIES, CURRENCIES, EquityEntry } from "@/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";

export default function EquityEntryPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get("id");
  const { setError } = useError();

  const [loading, setLoading] = useState(false);
  const [loadingEntry, setLoadingEntry] = useState(!!editId);

  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [description, setDescription] = useState("");
  const [account, setAccount] = useState<string>(EQUITY_ACCOUNTS[0]);
  const [category, setCategory] = useState<string>(EQUITY_CATEGORIES[0]);
  const [currency, setCurrency] = useState<string>("CAD");
  const [rate, setRate] = useState(1);
  const [balance, setBalance] = useState(0);
  const [tax, setTax] = useState(0);

  const loadEntry = useCallback(async () => {
    if (!editId) return;

    try {
      setLoadingEntry(true);
      const { data, error } = await supabase
        .from("equity")
        .select("*")
        .eq("id", editId)
        .single();

      if (error) throw error;

      const entry = data as EquityEntry;
      setDate(entry.date);
      setDescription(entry.description);
      setAccount(entry.account);
      setCategory(entry.category);
      setCurrency(entry.currency);
      setRate(entry.rate);
      setBalance(entry.balance);
      setTax(entry.tax);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load entry");
      router.back();
    } finally {
      setLoadingEntry(false);
    }
  }, [editId, setError, router]);

  useEffect(() => {
    loadEntry();
  }, [loadEntry]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);

      const entryData = {
        date,
        description,
        account,
        category,
        currency,
        rate,
        balance,
        tax,
      };

      if (editId) {
        // Update existing
        const { error } = await supabase
          .from("equity")
          .update(entryData)
          .eq("id", editId);
        if (error) throw error;
      } else {
        // Insert new
        const { error } = await supabase.from("equity").insert(entryData);
        if (error) throw error;
      }

      router.back();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save entry");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!editId) return;
    if (!confirm("Are you sure you want to delete this entry?")) return;

    try {
      setLoading(true);
      const { error } = await supabase.from("equity").delete().eq("id", editId);
      if (error) throw error;
      router.back();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entry");
    } finally {
      setLoading(false);
    }
  };

  if (loadingEntry) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  // Calculate preview
  let balanceCad = balance * rate;
  if (currency === "SAT") {
    balanceCad = balanceCad / 100_000_000;
  }
  const balanceNet = balanceCad * (1 - tax);

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <kbd className="mr-1.5">q</kbd> Back
        </Button>
        <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
          {editId ? "Edit" : "Add"} Equity Entry
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="max-w-xl">
        <div className="space-y-4">
          <Input
            type="date"
            label="Date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />

          <Input
            type="text"
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., Bitcoin Wallet"
            required
          />

          <Select
            label="Account"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            options={EQUITY_ACCOUNTS.map((a) => ({ value: a, label: a }))}
          />

          <Select
            label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={EQUITY_CATEGORIES.map((c) => ({ value: c, label: c }))}
          />

          <Select
            label="Currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            options={CURRENCIES.map((c) => ({ value: c, label: c }))}
          />

          <Input
            type="number"
            label="Rate"
            value={rate || ""}
            onChange={(e) => setRate(parseFloat(e.target.value) || 0)}
            step="0.0001"
            required
          />

          <Input
            type="number"
            label="Balance"
            value={balance || ""}
            onChange={(e) => setBalance(parseFloat(e.target.value) || 0)}
            step="0.01"
            required
          />

          <Input
            type="number"
            label="Tax Rate (0.0 - 1.0)"
            value={tax || ""}
            onChange={(e) => setTax(parseFloat(e.target.value) || 0)}
            step="0.01"
            min="0"
            max="1"
          />
        </div>

        {/* Preview */}
        <div className="mt-6 p-3 bg-[var(--gruvbox-bg-hard)] rounded border border-[var(--gruvbox-bg2)]">
          <div className="text-sm font-medium text-[var(--gruvbox-fg3)] mb-2">
            Preview
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm font-data">
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Balance CAD:</span>{" "}
              <span className="text-[var(--gruvbox-green)]">
                {balanceCad.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--gruvbox-fg4)]">Balance Net:</span>{" "}
              <span className="text-[var(--gruvbox-green)] font-bold">
                {balanceNet.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 flex gap-2">
          <Button type="submit" variant="primary" loading={loading}>
            {editId ? "Update" : "Save"} Entry
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.back()}
          >
            Cancel
          </Button>
          {editId && (
            <Button
              type="button"
              variant="danger"
              onClick={handleDelete}
              loading={loading}
            >
              Delete
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
