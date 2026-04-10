from __future__ import annotations

from itertools import islice
from typing import Iterable, Sequence

from cli.domain.contracts import EquityContract, OptionContract
from cli.domain.quotes import (
    QuoteRecord,
    clean_number,
    clean_timestamp,
    derive_equity_mark,
    derive_option_mark,
    utc_now_iso,
)
from cli.providers.quote_provider import ProviderStatus
from shared.ibkr_gateway_config import DEFAULT_IB_GATEWAY_CONFIG, IBGatewayConfig


class IBKRGatewayProvider:
    source = "ibkr"

    def __init__(self, config: IBGatewayConfig | None = None):
        self.config = config or DEFAULT_IB_GATEWAY_CONFIG
        self.ib = None
        self._ib_insync_import_error: Exception | None = None

        try:
            from ib_insync import IB, Stock, Option  # type: ignore

            self._IB = IB
            self._Stock = Stock
            self._Option = Option
        except Exception as exc:  # pragma: no cover - depends on optional dep
            self._IB = None
            self._Stock = None
            self._Option = None
            self._ib_insync_import_error = exc

    def connect(self) -> ProviderStatus:
        if self._IB is None:
            return ProviderStatus(
                ok=False,
                status="gateway_unreachable",
                message=f"ib_insync unavailable: {self._ib_insync_import_error}",
            )

        if self.ib and self.ib.isConnected():
            return ProviderStatus(ok=True, status="live", message="already_connected")

        try:
            self.ib = self._IB()
            self.ib.connect(
                self.config.host,
                self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.timeout,
                readonly=self.config.read_only,
            )
            if not self.ib.isConnected():
                return ProviderStatus(
                    ok=False,
                    status="gateway_unreachable",
                    message="IB Gateway connection did not become active",
                )
            return ProviderStatus(ok=True, status="live", message="connected")
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            self.ib = None
            return ProviderStatus(
                ok=False,
                status="gateway_unreachable",
                message=str(exc),
            )

    def disconnect(self) -> None:
        if self.ib is not None:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
            finally:
                self.ib = None

    def fetch_equity_quotes(self, contracts: Sequence[EquityContract]) -> list[QuoteRecord]:
        ib_contracts = [self._Stock(c.symbol, "SMART", c.currency or "USD") for c in contracts]
        return self._fetch_quotes(contracts, ib_contracts, instrument_type="equity")

    def fetch_option_quotes(self, contracts: Sequence[OptionContract]) -> list[QuoteRecord]:
        ib_contracts = [
            self._Option(
                c.underlying_symbol,
                c.expiry,
                c.strike,
                c.put_call,
                "SMART",
                multiplier=str(int(c.multiplier)) if float(c.multiplier).is_integer() else str(c.multiplier),
                currency=c.currency or "USD",
            )
            for c in contracts
        ]
        return self._fetch_quotes(contracts, ib_contracts, instrument_type="option")

    def _fetch_quotes(self, contracts: Sequence, ib_contracts: Sequence, instrument_type: str) -> list[QuoteRecord]:
        if not contracts:
            return []
        if not self.ib or not self.ib.isConnected():
            return [self._gateway_unreachable_quote(contract, instrument_type) for contract in contracts]

        quotes: list[QuoteRecord] = []
        for contract_batch, ib_batch in zip(_batched(list(contracts), 50), _batched(list(ib_contracts), 50)):
            try:
                qualified = self.ib.qualifyContracts(*ib_batch)
            except Exception as exc:  # pragma: no cover - broker/runtime dependent
                for contract in contract_batch:
                    quotes.append(
                        self._unresolved_quote(
                            contract,
                            instrument_type,
                            reason=str(exc),
                        )
                    )
                continue

            qualified_map = self._match_qualified(contract_batch, qualified, instrument_type)
            to_request = [pair[1] for pair in qualified_map if pair[1] is not None]

            ticker_map = {}
            if to_request:
                try:
                    tickers = self.ib.reqTickers(*to_request)
                    ticker_map = {getattr(t.contract, "conId", None): t for t in tickers}
                except Exception as exc:  # pragma: no cover - broker/runtime dependent
                    for contract, qualified_contract in qualified_map:
                        if qualified_contract is None:
                            quotes.append(self._unresolved_quote(contract, instrument_type, reason="qualification_failed"))
                        else:
                            quotes.append(self._unavailable_quote(contract, instrument_type, reason=str(exc)))
                    continue

            for contract, qualified_contract in qualified_map:
                if qualified_contract is None:
                    quotes.append(self._unresolved_quote(contract, instrument_type, reason="qualification_failed"))
                    continue

                ticker = ticker_map.get(getattr(qualified_contract, "conId", None))
                quotes.append(self._ticker_to_quote(contract, qualified_contract, ticker, instrument_type))

        return quotes

    def _ticker_to_quote(self, contract, qualified_contract, ticker, instrument_type: str) -> QuoteRecord:
        quote_time = utc_now_iso()
        bid = ask = last = close = mark = None
        raw_payload = {
            "qualified_contract": {
                "conId": getattr(qualified_contract, "conId", None),
                "localSymbol": getattr(qualified_contract, "localSymbol", None),
                "exchange": getattr(qualified_contract, "exchange", None),
            }
        }

        if ticker is not None:
            bid = clean_number(getattr(ticker, "bid", None))
            ask = clean_number(getattr(ticker, "ask", None))
            last = clean_number(getattr(ticker, "last", None))
            close = clean_number(getattr(ticker, "close", None))
            market_price = clean_number(getattr(ticker, "marketPrice", lambda: None)())
            quote_time = clean_timestamp(getattr(ticker, "time", None)) or quote_time
            raw_payload.update(
                {
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "close": close,
                    "marketPrice": market_price,
                    "marketDataType": getattr(ticker, "marketDataType", None),
                }
            )
            if instrument_type == "option":
                mark = derive_option_mark(bid=bid, ask=ask, last=last, close=close)
            else:
                mark = derive_equity_mark(last=last, market_price=market_price, close=close)

        status = self._resolve_status(ticker, mark)

        return QuoteRecord(
            contract_key=contract.contract_key,
            instrument_type=instrument_type,
            source=self.source,
            symbol=contract.symbol,
            underlying_symbol=getattr(contract, "underlying_symbol", None) or contract.symbol,
            expiry=getattr(contract, "expiry", None),
            put_call=getattr(contract, "put_call", None),
            strike=getattr(contract, "strike", None),
            multiplier=getattr(contract, "multiplier", None),
            conid=str(getattr(qualified_contract, "conId", "")) or None,
            bid=bid,
            ask=ask,
            last=last,
            close=close,
            mark=mark,
            quote_time=quote_time,
            status=status,
            raw_payload=raw_payload,
        )

    def _resolve_status(self, ticker, mark: float | None) -> str:
        if ticker is None:
            return "unavailable"
        market_data_type = getattr(ticker, "marketDataType", None)
        if market_data_type in {3, 4}:
            return "delayed" if mark is not None else "unavailable"
        if market_data_type == 2:
            return "stale" if mark is not None else "unavailable"
        if mark is not None:
            return "live"
        return "unavailable"

    def _gateway_unreachable_quote(self, contract, instrument_type: str) -> QuoteRecord:
        return QuoteRecord(
            contract_key=contract.contract_key,
            instrument_type=instrument_type,
            source=self.source,
            symbol=contract.symbol,
            underlying_symbol=getattr(contract, "underlying_symbol", None) or contract.symbol,
            expiry=getattr(contract, "expiry", None),
            put_call=getattr(contract, "put_call", None),
            strike=getattr(contract, "strike", None),
            multiplier=getattr(contract, "multiplier", None),
            status="gateway_unreachable",
            quote_time=utc_now_iso(),
        )

    def _unresolved_quote(self, contract, instrument_type: str, reason: str) -> QuoteRecord:
        return QuoteRecord(
            contract_key=contract.contract_key,
            instrument_type=instrument_type,
            source=self.source,
            symbol=contract.symbol,
            underlying_symbol=getattr(contract, "underlying_symbol", None) or contract.symbol,
            expiry=getattr(contract, "expiry", None),
            put_call=getattr(contract, "put_call", None),
            strike=getattr(contract, "strike", None),
            multiplier=getattr(contract, "multiplier", None),
            status="contract_unresolved",
            quote_time=utc_now_iso(),
            raw_payload={"reason": reason},
        )

    def _unavailable_quote(self, contract, instrument_type: str, reason: str) -> QuoteRecord:
        return QuoteRecord(
            contract_key=contract.contract_key,
            instrument_type=instrument_type,
            source=self.source,
            symbol=contract.symbol,
            underlying_symbol=getattr(contract, "underlying_symbol", None) or contract.symbol,
            expiry=getattr(contract, "expiry", None),
            put_call=getattr(contract, "put_call", None),
            strike=getattr(contract, "strike", None),
            multiplier=getattr(contract, "multiplier", None),
            status="unavailable",
            quote_time=utc_now_iso(),
            raw_payload={"reason": reason},
        )

    def _match_qualified(self, original_contracts: Sequence, qualified_contracts: Sequence, instrument_type: str):
        matched = []
        remaining = list(qualified_contracts)
        for contract in original_contracts:
            found = None
            for idx, qualified in enumerate(remaining):
                if instrument_type == "equity":
                    if getattr(qualified, "symbol", "") == contract.symbol:
                        found = remaining.pop(idx)
                        break
                else:
                    if (
                        getattr(qualified, "symbol", "") == contract.underlying_symbol
                        and getattr(qualified, "lastTradeDateOrContractMonth", "") == contract.expiry
                        and getattr(qualified, "right", "") == contract.put_call
                        and float(getattr(qualified, "strike", 0.0)) == float(contract.strike)
                    ):
                        found = remaining.pop(idx)
                        break
            matched.append((contract, found))
        return matched


def _batched(values: list, size: int) -> Iterable[list]:
    iterator = iter(values)
    while batch := list(islice(iterator, size)):
        yield batch
