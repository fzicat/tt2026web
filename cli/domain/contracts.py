from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class EquityContract:
    instrument_type: str
    symbol: str
    contract_key: str
    source_symbol: str
    currency: str | None = None


@dataclass(frozen=True)
class OptionContract:
    instrument_type: str
    underlying_symbol: str
    symbol: str
    expiry: str
    put_call: str
    strike: float
    multiplier: float
    contract_key: str
    conid: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class InvalidContract:
    instrument_type: str
    contract_key: str | None
    reason: str
    symbol: str | None = None
    underlying_symbol: str | None = None


OPTION_RIGHTS = {"C", "P"}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except TypeError:
            pass
    return getattr(row, key, default)


def normalize_symbol(symbol: Any) -> str:
    value = str(symbol or "").strip().upper()
    return value


def normalize_put_call(value: Any) -> str | None:
    normalized = str(value or "").strip().upper()
    if normalized in OPTION_RIGHTS:
        return normalized
    if normalized in {"CALL", "CALLS"}:
        return "C"
    if normalized in {"PUT", "PUTS"}:
        return "P"
    return None


def normalize_expiry(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 8:
        return digits

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y%m%d")
        except ValueError:
            continue

    return None


def normalize_multiplier(value: Any, default: float = 100.0) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_strike(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_strike_string(value: Any) -> str | None:
    strike = normalize_strike(value)
    if strike is None:
        return None
    try:
        return f"{Decimal(str(strike)).quantize(Decimal('0.0001')):.4f}"
    except (InvalidOperation, ValueError):
        return f"{strike:.4f}"


def is_option_trade(row: Any) -> bool:
    return normalize_put_call(_row_get(row, "putCall")) in OPTION_RIGHTS


def build_equity_key(symbol: Any) -> str:
    return f"EQ::{normalize_symbol(symbol)}"


def build_option_key(
    underlying_symbol: Any,
    expiry: Any,
    put_call: Any,
    strike: Any,
    multiplier: Any,
) -> str | None:
    underlying = normalize_symbol(underlying_symbol)
    normalized_expiry = normalize_expiry(expiry)
    right = normalize_put_call(put_call)
    strike_string = normalize_strike_string(strike)
    normalized_multiplier = normalize_multiplier(multiplier)

    if not underlying or not normalized_expiry or not right or strike_string is None or normalized_multiplier is None:
        return None

    multiplier_string = str(int(normalized_multiplier)) if float(normalized_multiplier).is_integer() else str(normalized_multiplier)
    return f"OPT::{underlying}::{normalized_expiry}::{right}::{strike_string}::{multiplier_string}"


def to_equity_contract(row: Any) -> EquityContract | InvalidContract:
    symbol = normalize_symbol(_row_get(row, "symbol"))
    currency = _row_get(row, "currency")
    if not symbol:
        return InvalidContract(
            instrument_type="equity",
            contract_key=None,
            reason="missing_symbol",
        )

    return EquityContract(
        instrument_type="equity",
        symbol=symbol,
        contract_key=build_equity_key(symbol),
        source_symbol=symbol,
        currency=currency,
    )


def to_option_contract(row: Any) -> OptionContract | InvalidContract:
    underlying_symbol = normalize_symbol(
        _row_get(row, "underlyingSymbol") or _row_get(row, "symbol")
    )
    symbol = normalize_symbol(_row_get(row, "symbol"))
    expiry = normalize_expiry(_row_get(row, "expiry"))
    put_call = normalize_put_call(_row_get(row, "putCall"))
    strike = normalize_strike(_row_get(row, "strike"))
    multiplier = normalize_multiplier(_row_get(row, "multiplier"))
    currency = _row_get(row, "currency")

    missing = []
    if not underlying_symbol:
        missing.append("underlying_symbol")
    if not expiry:
        missing.append("expiry")
    if not put_call:
        missing.append("put_call")
    if strike is None:
        missing.append("strike")
    if multiplier is None:
        missing.append("multiplier")

    contract_key = build_option_key(underlying_symbol, expiry, put_call, strike, multiplier)

    if missing or not contract_key:
        return InvalidContract(
            instrument_type="option",
            contract_key=contract_key,
            reason=f"missing_or_invalid:{','.join(missing) if missing else 'contract_key'}",
            symbol=symbol or None,
            underlying_symbol=underlying_symbol or None,
        )

    return OptionContract(
        instrument_type="option",
        underlying_symbol=underlying_symbol,
        symbol=symbol,
        expiry=expiry,
        put_call=put_call,
        strike=strike,
        multiplier=multiplier,
        contract_key=contract_key,
        currency=currency,
    )


def build_contract_key_from_trade_row(row: Any) -> str | None:
    if is_option_trade(row):
        contract = to_option_contract(row)
        return None if isinstance(contract, InvalidContract) else contract.contract_key
    contract = to_equity_contract(row)
    return None if isinstance(contract, InvalidContract) else contract.contract_key
