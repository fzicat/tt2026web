import { createClient, SupabaseClient } from "@supabase/supabase-js";

let supabaseInstance: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (supabaseInstance) return supabaseInstance;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error("Supabase credentials not configured");
  }

  supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  });

  return supabaseInstance;
}

// For backwards compatibility
export const supabase = typeof window !== "undefined" ? getSupabaseClient() : null!;

// Column mapping from PostgreSQL snake_case to camelCase
const COLUMN_MAP: Record<string, string> = {
  trade_id: "tradeID",
  account_id: "accountId",
  underlying_symbol: "underlyingSymbol",
  put_call: "putCall",
  date_time: "dateTime",
  trade_price: "tradePrice",
  ib_commission: "ibCommission",
  open_close_indicator: "openCloseIndicator",
};

const REVERSE_COLUMN_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(COLUMN_MAP).map(([k, v]) => [v, k])
);

export function toSnakeCase(data: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    const newKey = REVERSE_COLUMN_MAP[k] ?? k;
    result[newKey] = v;
  }
  return result;
}

export function toCamelCase(data: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    const newKey = COLUMN_MAP[k] ?? k;
    result[newKey] = v;
  }
  return result;
}

export function toCamelCaseArray<T>(data: Record<string, unknown>[]): T[] {
  return data.map((row) => toCamelCase(row) as T);
}
