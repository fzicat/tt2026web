from __future__ import annotations

import pandas as pd

from cli.domain.contracts import build_contract_key_from_trade_row, is_option_trade


def apply_quotes(trades_df: pd.DataFrame, quotes_by_key: dict[str, dict]) -> pd.DataFrame:
    if trades_df.empty:
        return trades_df.copy()

    df = trades_df.copy()
    df["contract_key"] = df.apply(build_contract_key_from_trade_row, axis=1)
    df["quote_source"] = None
    df["quote_status"] = None
    df["mtm_price"] = 0.0
    df["mtm_value"] = 0.0
    df["unrealized_pnl"] = 0.0

    for idx, row in df.iterrows():
        contract_key = row.get("contract_key")
        multiplier = float(row.get("multiplier") or (100.0 if is_option_trade(row) else 1.0))
        remaining_qty = float(row.get("remaining_qty") or 0.0)
        credit = float(row.get("credit") or 0.0)

        if not contract_key:
            df.at[idx, "quote_status"] = "contract_unresolved"
            df.at[idx, "unrealized_pnl"] = 0.0
            continue

        quote = quotes_by_key.get(contract_key)
        if not quote:
            df.at[idx, "quote_status"] = "unavailable"
            df.at[idx, "unrealized_pnl"] = 0.0
            continue

        mark = quote.get("mark")
        source = quote.get("source")
        status = quote.get("status") or "unavailable"

        df.at[idx, "quote_source"] = source
        df.at[idx, "quote_status"] = status

        if mark is None:
            df.at[idx, "unrealized_pnl"] = 0.0
            continue

        mark = float(mark)
        mtm_value = mark * remaining_qty * (multiplier if is_option_trade(row) else 1.0)
        unrealized = mtm_value + credit

        df.at[idx, "mtm_price"] = mark
        df.at[idx, "mtm_value"] = mtm_value
        df.at[idx, "unrealized_pnl"] = unrealized

    return df


def calculate_position_totals(trades_df: pd.DataFrame) -> dict[str, float]:
    if trades_df.empty:
        return {
            "stock_unrealized": 0.0,
            "call_unrealized": 0.0,
            "put_unrealized": 0.0,
            "total_unrealized": 0.0,
        }

    stock_unrealized = trades_df.loc[
        ~trades_df["putCall"].isin(["C", "P"]), "unrealized_pnl"
    ].sum()
    call_unrealized = trades_df.loc[trades_df["putCall"] == "C", "unrealized_pnl"].sum()
    put_unrealized = trades_df.loc[trades_df["putCall"] == "P", "unrealized_pnl"].sum()

    return {
        "stock_unrealized": float(stock_unrealized),
        "call_unrealized": float(call_unrealized),
        "put_unrealized": float(put_unrealized),
        "total_unrealized": float(stock_unrealized + call_unrealized + put_unrealized),
    }
