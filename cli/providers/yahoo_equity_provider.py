from __future__ import annotations

from datetime import datetime
from typing import Sequence

from cli.domain.contracts import EquityContract
from cli.domain.quotes import QuoteRecord, clean_number, clean_timestamp, derive_equity_mark, utc_now_iso


class YahooEquityProvider:
    source = "yahoo_fallback"

    def fetch_equity_quotes(self, contracts: Sequence[EquityContract]) -> list[QuoteRecord]:
        if not contracts:
            return []

        try:
            from yahooquery import Ticker
        except ImportError as exc:
            raise RuntimeError("yahooquery is not installed") from exc

        symbols = [contract.symbol for contract in contracts]
        ticker = Ticker(symbols, asynchronous=True)
        payload = ticker.price
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected yahooquery response type: {type(payload)}")

        quote_time = utc_now_iso()
        quotes: list[QuoteRecord] = []

        for contract in contracts:
            info = payload.get(contract.symbol)
            if not isinstance(info, dict):
                quotes.append(
                    QuoteRecord(
                        contract_key=contract.contract_key,
                        instrument_type="equity",
                        source=self.source,
                        symbol=contract.symbol,
                        underlying_symbol=contract.symbol,
                        status="unavailable",
                        quote_time=quote_time,
                        raw_payload={"error": info},
                    )
                )
                continue

            market_price = clean_number(info.get("regularMarketPrice"))
            last = clean_number(info.get("regularMarketPrice"))
            close = clean_number(info.get("regularMarketPreviousClose"))
            quote_timestamp = info.get("regularMarketTime") or info.get("postMarketTime")
            if isinstance(quote_timestamp, (int, float)):
                quote_timestamp = clean_timestamp(datetime.utcfromtimestamp(int(quote_timestamp)))
            else:
                quote_timestamp = clean_timestamp(quote_timestamp) or quote_time

            mark = derive_equity_mark(last=last, market_price=market_price, close=close)
            status = "live" if mark is not None else "unavailable"

            quotes.append(
                QuoteRecord(
                    contract_key=contract.contract_key,
                    instrument_type="equity",
                    source=self.source,
                    symbol=contract.symbol,
                    underlying_symbol=contract.symbol,
                    bid=clean_number(info.get("bid")),
                    ask=clean_number(info.get("ask")),
                    last=last,
                    close=close,
                    mark=mark,
                    quote_time=quote_timestamp,
                    status=status,
                    raw_payload=info,
                )
            )

        return quotes

    def fetch_option_quotes(self, contracts):  # pragma: no cover - explicit guard
        raise ValueError("Yahoo fallback does not support option quotes")
