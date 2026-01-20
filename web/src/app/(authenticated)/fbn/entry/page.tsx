"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useError } from "@/lib/error-context";
import { FBN_ACCOUNTS } from "@/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { getLastDayOfPreviousMonth } from "@/lib/utils/format";

interface EntryValues {
  investment: number;
  deposit: number;
  interest: number;
  dividend: number;
  distribution: number;
  tax: number;
  fee: number;
  other: number;
  cash: number;
  asset: number;
  rate: number;
}

export default function FBNEntryPage() {
  const router = useRouter();
  const { setError } = useError();
  const [loading, setLoading] = useState(false);

  const defaultDate = getLastDayOfPreviousMonth().toISOString().split("T")[0];
  const [date, setDate] = useState(defaultDate);
  const [selectedAccount, setSelectedAccount] = useState<number | null>(null);
  const [values, setValues] = useState<EntryValues>({
    investment: 0,
    deposit: 0,
    interest: 0,
    dividend: 0,
    distribution: 0,
    tax: 0,
    fee: 0,
    other: 0,
    cash: 0,
    asset: 0,
    rate: 1,
  });

  const handleAccountSelect = (index: number) => {
    setSelectedAccount(index);
    const account = FBN_ACCOUNTS[index];
    // Reset values, set rate to 1 for CAD accounts
    setValues({
      investment: 0,
      deposit: 0,
      interest: 0,
      dividend: 0,
      distribution: 0,
      tax: 0,
      fee: 0,
      other: 0,
      cash: 0,
      asset: 0,
      rate: account.currency === "USD" ? 0 : 1,
    });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (selectedAccount === null) {
      setError("Please select an account");
      return;
    }

    const account = FBN_ACCOUNTS[selectedAccount];

    try {
      setLoading(true);

      // Delete existing entry if any
      await supabase
        .from("fbn")
        .delete()
        .eq("date", date)
        .eq("account", account.name);

      // Insert new entry
      const { error } = await supabase.from("fbn").insert({
        date,
        account: account.name,
        portfolio: account.portfolio,
        currency: account.currency,
        ...values,
      });

      if (error) throw error;

      // Ask if they want to enter another account
      setSelectedAccount(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save entry");
    } finally {
      setLoading(false);
    }
  };

  const variationEncaisse =
    values.investment +
    values.deposit +
    values.interest +
    values.dividend +
    values.distribution +
    values.tax +
    values.fee +
    values.other;
  const totalPlacements = values.asset - values.cash;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <kbd className="mr-1.5">q</kbd> Back
        </Button>
        <h1 className="text-xl font-semibold text-[var(--gruvbox-orange)]">
          Add/Edit FBN Entry
        </h1>
      </div>

      <div className="max-w-2xl">
        {/* Date Selection */}
        <div className="mb-6">
          <Input
            type="date"
            label="Date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        {/* Account Selection */}
        {selectedAccount === null ? (
          <div className="mb-6">
            <label className="block text-sm font-medium text-[var(--gruvbox-fg3)] mb-2">
              Select Account
            </label>
            <div className="grid grid-cols-3 gap-2">
              {FBN_ACCOUNTS.map((account, index) => (
                <button
                  key={account.name}
                  onClick={() => handleAccountSelect(index)}
                  className="p-3 text-left rounded border border-[var(--gruvbox-bg3)] bg-[var(--gruvbox-bg1)] hover:bg-[var(--gruvbox-bg2)] hover:border-[var(--gruvbox-orange)] transition-colors"
                >
                  <div className="font-medium text-[var(--gruvbox-fg)]">
                    {account.name}
                  </div>
                  <div className="text-xs text-[var(--gruvbox-fg4)]">
                    {account.currency}
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="mb-4 p-3 bg-[var(--gruvbox-bg1)] rounded border border-[var(--gruvbox-bg3)]">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-[var(--gruvbox-yellow)] font-semibold">
                    {FBN_ACCOUNTS[selectedAccount].name}
                  </span>
                  <span className="text-[var(--gruvbox-fg4)] ml-2">
                    ({FBN_ACCOUNTS[selectedAccount].currency})
                  </span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedAccount(null)}
                >
                  Change
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <Input
                type="number"
                label="Investment"
                value={values.investment || ""}
                onChange={(e) =>
                  setValues({ ...values, investment: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Deposit"
                value={values.deposit || ""}
                onChange={(e) =>
                  setValues({ ...values, deposit: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Interest"
                value={values.interest || ""}
                onChange={(e) =>
                  setValues({ ...values, interest: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Dividend"
                value={values.dividend || ""}
                onChange={(e) =>
                  setValues({ ...values, dividend: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Distribution"
                value={values.distribution || ""}
                onChange={(e) =>
                  setValues({ ...values, distribution: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Tax"
                value={values.tax || ""}
                onChange={(e) =>
                  setValues({ ...values, tax: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Fee"
                value={values.fee || ""}
                onChange={(e) =>
                  setValues({ ...values, fee: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Other"
                value={values.other || ""}
                onChange={(e) =>
                  setValues({ ...values, other: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Cash"
                value={values.cash || ""}
                onChange={(e) =>
                  setValues({ ...values, cash: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              <Input
                type="number"
                label="Asset"
                value={values.asset || ""}
                onChange={(e) =>
                  setValues({ ...values, asset: parseFloat(e.target.value) || 0 })
                }
                step="0.01"
              />
              {FBN_ACCOUNTS[selectedAccount].currency === "USD" && (
                <Input
                  type="number"
                  label="Rate (USD/CAD)"
                  value={values.rate || ""}
                  onChange={(e) =>
                    setValues({ ...values, rate: parseFloat(e.target.value) || 1 })
                  }
                  step="0.0001"
                />
              )}
            </div>

            {/* Validation */}
            <div className="mb-6 p-3 bg-[var(--gruvbox-bg-hard)] rounded border border-[var(--gruvbox-bg2)]">
              <div className="text-sm font-medium text-[var(--gruvbox-fg3)] mb-2">
                Validation
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm font-data">
                <div>
                  <span className="text-[var(--gruvbox-fg4)]">
                    Variation Encaisse:
                  </span>{" "}
                  <span className="text-[var(--gruvbox-aqua)]">
                    {variationEncaisse.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--gruvbox-fg4)]">
                    Total Placements:
                  </span>{" "}
                  <span className="text-[var(--gruvbox-aqua)]">
                    {totalPlacements.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <Button type="submit" variant="primary" loading={loading}>
                Save Entry
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setSelectedAccount(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
