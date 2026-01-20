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
    const token = process.env.IBKR_TOKEN;
    const queryId = process.env.QUERY_ID_DAILY;

    if (!token || !queryId) {
      return NextResponse.json(
        { error: "IBKR credentials not configured" },
        { status: 500 }
      );
    }

    const supabase = getSupabase();

    // Step 1: Request the report
    const requestUrl = `https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t=${token}&q=${queryId}&v=3`;
    const requestRes = await fetch(requestUrl);
    const requestText = await requestRes.text();

    // Parse XML response
    const statusMatch = requestText.match(/<Status>(\w+)<\/Status>/);
    if (!statusMatch || statusMatch[1] !== "Success") {
      const errorMatch = requestText.match(/<ErrorMessage>(.+?)<\/ErrorMessage>/);
      return NextResponse.json(
        { error: errorMatch?.[1] || "Failed to request report" },
        { status: 400 }
      );
    }

    const refCodeMatch = requestText.match(/<ReferenceCode>(\w+)<\/ReferenceCode>/);
    const baseUrlMatch = requestText.match(/<Url>(.+?)<\/Url>/);

    if (!refCodeMatch || !baseUrlMatch) {
      return NextResponse.json(
        { error: "Invalid response from IBKR" },
        { status: 400 }
      );
    }

    const refCode = refCodeMatch[1];
    const baseUrl = baseUrlMatch[1];

    // Step 2: Poll for the report
    const downloadUrl = `${baseUrl}?q=${refCode}&t=${token}&v=3`;

    let reportContent: string | null = null;
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => setTimeout(r, 2000));

      const downloadRes = await fetch(downloadUrl);
      const downloadText = await downloadRes.text();

      if (
        downloadText.includes("<FlexStatement") ||
        downloadText.includes("<FlexQueryResponse")
      ) {
        reportContent = downloadText;
        break;
      }
    }

    if (!reportContent) {
      return NextResponse.json(
        { error: "Timeout waiting for report" },
        { status: 408 }
      );
    }

    // Step 3: Parse trades from XML
    const tradeMatches = reportContent.matchAll(
      /<(?:Trade|TradeConfirm)\s+([^>]+)\/>/g
    );

    const trades: Record<string, unknown>[] = [];
    for (const match of tradeMatches) {
      const attrs = match[1];
      const trade: Record<string, unknown> = {};

      // Parse attributes
      const attrMatches = attrs.matchAll(/(\w+)="([^"]*)"/g);
      for (const [, key, value] of attrMatches) {
        trade[key] = value;
      }

      // Map to our schema
      const tradeData = {
        trade_id: trade.tradeID,
        account_id: trade.accountId,
        underlying_symbol: trade.underlyingSymbol,
        symbol: trade.symbol,
        description: trade.description,
        expiry: trade.expiry || null,
        put_call: trade.putCall || null,
        strike: trade.strike ? parseFloat(trade.strike as string) : null,
        date_time: convertDateTime(trade.dateTime as string),
        quantity: trade.quantity ? parseFloat(trade.quantity as string) : null,
        trade_price:
          trade.tradePrice || trade.price
            ? parseFloat((trade.tradePrice || trade.price) as string)
            : null,
        multiplier: trade.multiplier
          ? parseFloat(trade.multiplier as string)
          : 1,
        ib_commission:
          trade.ibCommission || trade.commission
            ? parseFloat((trade.ibCommission || trade.commission) as string)
            : null,
        currency: trade.currency,
        notes: trade.notes || null,
        open_close_indicator: getOpenClose(trade),
      };

      if (tradeData.trade_id) {
        trades.push(tradeData);
      }
    }

    // Step 4: Upsert trades
    let newCount = 0;
    for (const trade of trades) {
      const { data, error } = await supabase
        .from("trades")
        .upsert(trade, { onConflict: "trade_id", ignoreDuplicates: true });

      if (!error && data && (data as unknown[]).length > 0) {
        newCount++;
      }
    }

    return NextResponse.json({
      message: `Import complete. ${newCount} new trades imported.`,
      total: trades.length,
      new: newCount,
    });
  } catch (err) {
    console.error("Import error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Import failed" },
      { status: 500 }
    );
  }
}

function convertDateTime(dt: string | undefined): string | null {
  if (!dt) return null;
  if (dt.length === 14 && /^\d+$/.test(dt)) {
    // YYYYMMDDHHmmss format
    const year = dt.slice(0, 4);
    const month = dt.slice(4, 6);
    const day = dt.slice(6, 8);
    const hour = dt.slice(8, 10);
    const min = dt.slice(10, 12);
    const sec = dt.slice(12, 14);
    return `${year}-${month}-${day}T${hour}:${min}:${sec}`;
  }
  return dt;
}

function getOpenClose(trade: Record<string, unknown>): string | null {
  if (trade.openCloseIndicator) return trade.openCloseIndicator as string;
  const code = (trade.code as string) || "";
  if (code.includes("O")) return "O";
  if (code.includes("C")) return "C";
  return null;
}
