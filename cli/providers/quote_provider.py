from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from cli.domain.contracts import EquityContract, OptionContract
from cli.domain.quotes import QuoteRecord


@dataclass(frozen=True)
class ProviderStatus:
    ok: bool
    status: str
    message: str = ""


class QuoteProvider(Protocol):
    def connect(self) -> ProviderStatus:
        ...

    def fetch_equity_quotes(self, contracts: Sequence[EquityContract]) -> list[QuoteRecord]:
        ...

    def fetch_option_quotes(self, contracts: Sequence[OptionContract]) -> list[QuoteRecord]:
        ...

    def disconnect(self) -> None:
        ...
