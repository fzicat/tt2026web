from __future__ import annotations

from typing import Iterable

from shared.supabase_client import get_client

from cli.domain.quotes import QuoteRecord, has_any_market_data


PRESERVE_ON_EMPTY_STATUSES = {
    "unavailable",
    "gateway_unreachable",
    "contract_unresolved",
    "permission_denied",
}


def _normalize_row(row: dict) -> dict:
    return {
        "contract_key": row.get("contract_key"),
        "instrument_type": row.get("instrument_type"),
        "source": row.get("source"),
        "symbol": row.get("symbol"),
        "underlying_symbol": row.get("underlying_symbol"),
        "expiry": row.get("expiry"),
        "put_call": row.get("put_call"),
        "strike": row.get("strike"),
        "multiplier": row.get("multiplier"),
        "conid": row.get("conid"),
        "bid": row.get("bid"),
        "ask": row.get("ask"),
        "last": row.get("last"),
        "close": row.get("close"),
        "mark": row.get("mark"),
        "status": row.get("status"),
        "quote_time": row.get("quote_time"),
        "raw_payload": row.get("raw_payload"),
        "updated_at": row.get("updated_at"),
    }


def fetch_latest_quotes() -> dict[str, dict]:
    client = get_client()
    try:
        response = client.table("market_quotes").select("*").execute()
        return {row["contract_key"]: _normalize_row(row) for row in response.data or []}
    except Exception as exc:
        print(f"Error fetching market quotes: {exc}")
        return {}


def fetch_quotes_by_keys(keys: Iterable[str]) -> dict[str, dict]:
    keys = [key for key in keys if key]
    if not keys:
        return {}

    client = get_client()
    try:
        response = client.table("market_quotes").select("*").in_("contract_key", keys).execute()
        return {row["contract_key"]: _normalize_row(row) for row in response.data or []}
    except Exception as exc:
        print(f"Error fetching market quotes by key: {exc}")
        return {}


def upsert_quotes(quotes: list[QuoteRecord]) -> dict:
    if not quotes:
        return {"saved": 0, "skipped": 0, "errors": []}

    existing = fetch_quotes_by_keys([quote.contract_key for quote in quotes])
    payload = []
    skipped = 0

    for quote in quotes:
        current = quote.to_db_dict()
        prior = existing.get(quote.contract_key)
        should_preserve = (
            prior is not None
            and not has_any_market_data(quote)
            and quote.status in PRESERVE_ON_EMPTY_STATUSES
            and any(prior.get(field) is not None for field in ("bid", "ask", "last", "close", "mark"))
        )
        if should_preserve:
            skipped += 1
            continue
        payload.append(current)

    if not payload:
        return {"saved": 0, "skipped": skipped, "errors": []}

    client = get_client()
    try:
        response = client.table("market_quotes").upsert(payload, on_conflict="contract_key").execute()
        return {"saved": len(response.data or []), "skipped": skipped, "errors": []}
    except Exception as exc:
        print(f"Error upserting market quotes: {exc}")
        return {"saved": 0, "skipped": skipped, "errors": [str(exc)]}
