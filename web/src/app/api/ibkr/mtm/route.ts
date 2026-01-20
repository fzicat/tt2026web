import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("Supabase credentials not configured");
  }
  return createClient(url, key);
}

export async function POST() {
  try {
    const supabase = getSupabase();

    // Get unique symbols from trades (non-options only)
    const { data: trades, error: tradesError } = await supabase
      .from("trades")
      .select("symbol, put_call")
      .not("symbol", "eq", "USD.CAD");

    if (tradesError) throw tradesError;

    // Filter for non-option symbols
    const symbols = [
      ...new Set(
        (trades || [])
          .filter((t) => t.put_call !== "C" && t.put_call !== "P")
          .map((t) => t.symbol)
      ),
    ];

    if (symbols.length === 0) {
      return NextResponse.json({
        message: "No symbols to update",
        updated: 0,
      });
    }

    // Fetch prices from Yahoo Finance API
    const prices: Record<string, number> = {};
    const symbolsStr = symbols.join(",");

    // Use Yahoo Finance v8 API
    const yahooUrl = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbolsStr)}`;

    try {
      const res = await fetch(yahooUrl, {
        headers: {
          "User-Agent": "Mozilla/5.0",
        },
      });

      if (res.ok) {
        const data = await res.json();
        const quotes = data?.quoteResponse?.result || [];

        for (const quote of quotes) {
          const price =
            quote.regularMarketPrice || quote.regularMarketPreviousClose;
          if (quote.symbol && price) {
            prices[quote.symbol] = price;
          }
        }
      }
    } catch (fetchErr) {
      console.error("Yahoo fetch error:", fetchErr);
      // Try individual requests as fallback
      for (const symbol of symbols) {
        try {
          const singleUrl = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${symbol}`;
          const singleRes = await fetch(singleUrl, {
            headers: { "User-Agent": "Mozilla/5.0" },
          });
          if (singleRes.ok) {
            const singleData = await singleRes.json();
            const quote = singleData?.quoteResponse?.result?.[0];
            const price =
              quote?.regularMarketPrice || quote?.regularMarketPreviousClose;
            if (price) {
              prices[symbol] = price;
            }
          }
        } catch {
          console.error(`Failed to fetch price for ${symbol}`);
        }
      }
    }

    // Update market_price table
    const currentTime = new Date().toISOString();
    let updateCount = 0;

    for (const [symbol, price] of Object.entries(prices)) {
      const { error: upsertError } = await supabase.from("market_price").upsert(
        {
          symbol,
          price,
          date_time: currentTime,
        },
        { onConflict: "symbol" }
      );

      if (!upsertError) {
        updateCount++;
      }
    }

    return NextResponse.json({
      message: `Updated prices for ${updateCount} symbols`,
      updated: updateCount,
      total: symbols.length,
    });
  } catch (err) {
    console.error("MTM update error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "MTM update failed" },
      { status: 500 }
    );
  }
}
