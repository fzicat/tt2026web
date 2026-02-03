import { Trade, Position } from "@/types";

interface InventoryItem {
  idx: number;
  qty: number;
  price: number;
}

export function calculatePnL(trades: Trade[]): Trade[] {
  if (trades.length === 0) return [];

  // Create a copy with initialized fields
  const result = trades.map((trade) => ({
    ...trade,
    realized_pnl: 0,
    remaining_qty: 0,
  }));

  // Inventory: symbol -> list of {idx, qty, price}
  const inventory: Record<string, InventoryItem[]> = {};

  for (let idx = 0; idx < result.length; idx++) {
    const row = result[idx];
    const symbol = row.symbol;
    let qty = row.quantity ?? 0;
    const price = row.tradePrice ?? 0;
    const multiplier = row.multiplier ?? 1;

    if (!inventory[symbol]) {
      inventory[symbol] = [];
    }

    // If inventory is empty, open/add
    if (inventory[symbol].length === 0) {
      result[idx].remaining_qty = qty;
      inventory[symbol].push({ idx, qty, price });
      continue;
    }

    // Check head of inventory
    const head = inventory[symbol][0];

    // Same sign means adding to position
    if ((qty > 0 && head.qty > 0) || (qty < 0 && head.qty < 0)) {
      result[idx].remaining_qty = qty;
      inventory[symbol].push({ idx, qty, price });
    } else {
      // Opposite sign: Close/Reduce position
      let qtyToProcess = qty;
      let totalPnl = 0;

      while (qtyToProcess !== 0 && inventory[symbol].length > 0) {
        const item = inventory[symbol][0];
        const openQty = item.qty;
        const openPrice = item.price;
        const openIdx = item.idx;

        if (Math.abs(qtyToProcess) >= Math.abs(openQty)) {
          // Fully consume this open lot
          const matchQty = -openQty;
          const termPnl = -(price - openPrice) * matchQty * multiplier;
          totalPnl += termPnl;
          qtyToProcess -= matchQty;

          // Update matched open lot
          result[openIdx].remaining_qty = 0;
          inventory[symbol].shift();
        } else {
          // Partially consume open lot
          const termPnl = -(price - openPrice) * qtyToProcess * multiplier;
          totalPnl += termPnl;

          // Update inventory item
          item.qty += qtyToProcess;
          result[openIdx].remaining_qty = item.qty;

          qtyToProcess = 0;
        }
      }

      result[idx].realized_pnl = totalPnl;

      // If we still have quantity left, it becomes new position
      if (qtyToProcess !== 0) {
        result[idx].remaining_qty = qtyToProcess;
        inventory[symbol].push({ idx, qty: qtyToProcess, price });
      }
    }
  }

  return result;
}

export function calculateCredit(trades: Trade[]): Trade[] {
  return trades.map((trade) => {
    const multiplier = trade.multiplier ?? 1;
    const credit = (trade.remaining_qty ?? 0) * trade.tradePrice * multiplier * -1;
    return { ...trade, credit };
  });
}

export function applyMtmPrices(
  trades: Trade[],
  marketPrices: Record<string, number>
): Trade[] {
  return trades.map((trade) => {
    // Only apply MTM for non-option trades
    const isOption = trade.putCall === "C" || trade.putCall === "P";
    if (isOption) {
      return { ...trade, mtm_price: 0, mtm_value: 0 };
    }

    const mtmPrice = marketPrices[trade.symbol] ?? 0;
    const mtmValue = mtmPrice * (trade.remaining_qty ?? 0);
    return { ...trade, mtm_price: mtmPrice, mtm_value: mtmValue };
  });
}

export function groupByUnderlying(trades: Trade[]): Record<string, Trade[]> {
  const groups: Record<string, Trade[]> = {};
  for (const trade of trades) {
    const symbol = trade.underlyingSymbol || trade.symbol;
    if (!groups[symbol]) {
      groups[symbol] = [];
    }
    groups[symbol].push(trade);
  }
  return groups;
}

export function calculatePositions(
  trades: Trade[],
  totalMtm: number,
  targetPercents: Record<string, number> = {}
): Position[] {
  const groups = groupByUnderlying(trades);
  const positions: Position[] = [];

  for (const [symbol, groupTrades] of Object.entries(groups)) {
    const stockTrades = groupTrades.filter(
      (t) => t.putCall !== "C" && t.putCall !== "P"
    );
    const callTrades = groupTrades.filter((t) => t.putCall === "C");
    const putTrades = groupTrades.filter((t) => t.putCall === "P");

    const value = stockTrades.reduce((sum, t) => sum + (t.credit ?? 0), 0) * -1;
    const mtm = stockTrades.reduce((sum, t) => sum + (t.mtm_value ?? 0), 0);
    const unrealizedPnl = mtm - value;

    const stockQty = stockTrades.reduce((sum, t) => sum + (t.remaining_qty ?? 0), 0);
    const callQty = callTrades.reduce((sum, t) => sum + (t.remaining_qty ?? 0), 0);
    const putQty = putTrades.reduce((sum, t) => sum + (t.remaining_qty ?? 0), 0);

    const stockPnl = stockTrades.reduce((sum, t) => sum + (t.realized_pnl ?? 0), 0);
    const callPnl = callTrades.reduce((sum, t) => sum + (t.realized_pnl ?? 0), 0);
    const putPnl = putTrades.reduce((sum, t) => sum + (t.realized_pnl ?? 0), 0);

    // Calculate book price
    const creditSum = stockTrades.reduce((sum, t) => sum + (t.credit ?? 0), 0);
    const bookPrice = stockQty !== 0 ? creditSum / stockQty : 0;

    // Skip positions with no activity
    if (
      value === 0 &&
      mtm === 0 &&
      stockQty === 0 &&
      callQty === 0 &&
      putQty === 0 &&
      stockPnl === 0 &&
      callPnl === 0 &&
      putPnl === 0
    ) {
      continue;
    }

    positions.push({
      symbol,
      underlyingSymbol: symbol,
      value,
      mtm,
      mtmPercent: totalMtm !== 0 ? (mtm / totalMtm) * 100 : 0,
      targetPercent: targetPercents[symbol] ?? 0,
      unrealizedPnl,
      stockQty,
      callQty,
      putQty,
      stockPnl,
      callPnl,
      putPnl,
      bookPrice,
    });
  }

  return positions;
}

export function calculateTotals(positions: Position[]) {
  return {
    totalValue: positions.reduce((sum, p) => sum + p.value, 0),
    totalMtm: positions.reduce((sum, p) => sum + p.mtm, 0),
    totalUnrealizedPnl: positions.reduce((sum, p) => sum + p.unrealizedPnl, 0),
    totalStockQty: positions.reduce((sum, p) => sum + p.stockQty, 0),
    totalCallQty: positions.reduce((sum, p) => sum + p.callQty, 0),
    totalPutQty: positions.reduce((sum, p) => sum + p.putQty, 0),
    totalStockPnl: positions.reduce((sum, p) => sum + p.stockPnl, 0),
    totalCallPnl: positions.reduce((sum, p) => sum + p.callPnl, 0),
    totalPutPnl: positions.reduce((sum, p) => sum + p.putPnl, 0),
    totalTargetPct: positions.reduce((sum, p) => sum + p.targetPercent, 0),
  };
}
