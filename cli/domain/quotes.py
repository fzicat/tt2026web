from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isnan
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isnan(number):
        return None
    return number


def clean_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    text = str(value).strip()
    return text or None


@dataclass
class QuoteRecord:
    contract_key: str
    instrument_type: str
    source: str
    symbol: str
    underlying_symbol: str | None = None
    expiry: str | None = None
    put_call: str | None = None
    strike: float | None = None
    multiplier: float | None = None
    conid: str | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    close: float | None = None
    mark: float | None = None
    quote_time: str | None = None
    status: str = "unavailable"
    raw_payload: dict[str, Any] | None = None
    updated_at: str = field(default_factory=utc_now_iso)

    def to_db_dict(self) -> dict[str, Any]:
        return asdict(self)


def has_any_market_data(quote: QuoteRecord) -> bool:
    return any(
        value is not None
        for value in (quote.bid, quote.ask, quote.last, quote.close, quote.mark)
    )


def derive_equity_mark(last: Any = None, market_price: Any = None, close: Any = None) -> float | None:
    for value in (market_price, last, close):
        number = clean_number(value)
        if number is not None and number > 0:
            return number
    return None


def derive_option_mark(
    bid: Any = None,
    ask: Any = None,
    last: Any = None,
    close: Any = None,
    allow_close_fallback: bool = True,
) -> float | None:
    bid_num = clean_number(bid)
    ask_num = clean_number(ask)
    last_num = clean_number(last)
    close_num = clean_number(close)

    if bid_num is not None and ask_num is not None and bid_num > 0 and ask_num > 0:
        return (bid_num + ask_num) / 2
    if last_num is not None and last_num > 0:
        return last_num
    if allow_close_fallback and close_num is not None and close_num > 0:
        return close_num
    return None


def quote_with_status(quote: QuoteRecord, status: str, mark: Any = None) -> QuoteRecord:
    quote.status = status
    if mark is not None:
        quote.mark = clean_number(mark)
    return quote
