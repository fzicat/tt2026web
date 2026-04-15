# TradeTools — IBKR Market Data Blueprint

## Objective
Replace the current stock-only Yahoo Finance MTM flow with a broker-aligned market data architecture that supports both equities and options through **IB Gateway API** as the primary source, while keeping **YahooQuery as a stock-only fallback** when IBKR is unavailable.

This blueprint covers:
- shared quote architecture for CLI + web
- contract identity for stocks and options
- quote storage schema
- provider boundaries
- CLI flow changes
- web/FIFO flow changes
- fallback behavior
- error handling and operational constraints

---

## System Overview
TradeTools currently imports trades from IBKR Flex queries, calculates FIFO realized P&L, and computes stock mark-to-market values using YahooQuery. Options are deliberately excluded from unrealized valuation in both CLI and web. The new system will introduce a unified quote pipeline centered on **IB Gateway API** for both stocks and options. A quote service will resolve open positions into instrument contracts, request real-time quotes from IBKR, normalize them into a shared schema, persist them in Supabase, and expose them to both the CLI and web layers. When IBKR is unreachable, stock quotes may fall back to YahooQuery; options will not fall back to Yahoo and should instead surface as unavailable or stale.

---

## Goals
- Use **IB Gateway API** as the primary quote source for:
  - stocks
  - calls
  - puts
- Keep **YahooQuery** only as fallback for stock quotes
- Value **open option positions** correctly using contract-level quotes
- Persist quotes in a schema that supports:
  - bid / ask / last / mark
  - quote timestamps
  - contract-specific option identity
- Make CLI and web consume the same stored quote model
- Keep trade import via Flex queries unchanged unless required for quote identity enrichment

## Non-Goals
- Do not implement order placement
- Do not automate IBKR 2FA
- Do not redesign FIFO matching logic unless required for correctness of option MTM
- Do not build streaming quotes in phase 1; request/refresh snapshots only
- Do not use Yahoo as fallback for options

---

## Inputs

| Input | Source | Format/Schema | Validation Rules |
|---|---|---|---|
| Trade records | Supabase `trades` table | Existing trade schema | Must contain symbol, underlying_symbol, put_call, expiry, strike, multiplier, remaining_qty |
| Open positions | Derived from FIFO calculation | In-memory trade rows with `remaining_qty != 0` | Ignore positions with zero remaining quantity |
| IBKR quote session | Local IB Gateway session | Connected API session | Must be authenticated manually via IB Gateway with 2FA already completed |
| Stock fallback quotes | YahooQuery | Quote payload by symbol | Only valid for stocks, not options |
| Market data permissions | IBKR account | External prerequisite | Must include proper market data subscriptions and API acknowledgement |

---

## Outputs

| Output | Destination | Format/Schema | Conditions |
|---|---|---|---|
| Normalized equity quotes | Supabase quote table | one row per stock instrument | Saved when IBKR stock quote retrieval succeeds, or Yahoo fallback succeeds |
| Normalized option quotes | Supabase quote table | one row per option contract | Saved only when IBKR quote retrieval succeeds |
| MTM values on positions | CLI in-memory trades / web computed views | `mtm_price`, `mtm_value`, `quote_status`, `quote_source` | Computed for all open positions with valid quotes |
| Unrealized P&L | CLI + web summaries | numeric fields at row, position, and total level | Uses current mark vs signed basis |
| Health/error status | CLI output / logs | status strings/messages | Used when gateway unavailable, quote stale, contract unresolved, or permissions missing |

---

## Data Pipelines

### Pipeline 1: Open Position Discovery
**Source:** `trades` table in Supabase

**Steps:**
1. Load all trades ordered by `date_time`
2. Run FIFO logic to compute:
   - `realized_pnl`
   - `remaining_qty`
3. Filter to rows where `remaining_qty != 0`
4. Partition into:
   - equities
   - options
5. Derive instrument identity for each open row

**Destination:** in-memory open-position contract list

**Error handling:**
- If trade load fails, abort MTM update and show error
- If required fields for contract identity are missing, mark affected rows as unresolved and continue with others

### Pipeline 2: Contract Normalization
**Source:** open-position contract list

**Steps:**
1. For equity rows, normalize to equity contract key
2. For option rows, normalize to option contract key using:
   - underlying symbol
   - expiry
   - put/call
   - strike
   - multiplier
3. If available later, enrich with IBKR `conid`
4. Deduplicate contracts before quote requests

**Destination:** normalized contract request set

**Error handling:**
- If expiry, strike, or put/call missing for an option row, flag contract as invalid and skip quote request for that row
- If multiple open rows map to the same contract, request quote once and reuse

### Pipeline 3: IBKR Quote Retrieval
**Source:** normalized contract request set

**Steps:**
1. Ensure IB Gateway connection is live
2. Resolve or qualify contracts in IBKR API format
3. Batch request quotes for:
   - equities
   - options
4. Extract bid / ask / last / close / timestamp / contract identifiers
5. Derive normalized mark price
6. Build quote records with quote source `ibkr`

**Destination:** normalized quote objects

**Error handling:**
- If gateway unavailable, transition equities to Yahoo fallback pipeline and mark options unavailable
- If individual contract resolution fails, mark only that contract unresolved
- If market data permission denied, mark quote as permission error and continue
- Respect pacing / batching limits; no tight retry loops

### Pipeline 4: Stock Fallback Quote Retrieval
**Source:** unresolved equity contracts after IBKR failure

**Steps:**
1. Collect unresolved stock symbols only
2. Request YahooQuery quotes
3. Normalize to quote records using stock schema
4. Derive mark price from Yahoo fields (prefer regular market price)
5. Build quote records with quote source `yahoo_fallback`

**Destination:** normalized equity quote objects

**Error handling:**
- If YahooQuery fails, keep equities unresolved and mark as unavailable
- Never send option contracts through this pipeline

### Pipeline 5: Quote Persistence
**Source:** normalized quote objects from IBKR or Yahoo fallback

**Steps:**
1. Upsert quote rows into Supabase by unique instrument key
2. Save:
   - source
   - bid
   - ask
   - last
   - close
   - mark
   - quote_time
   - status flags
3. Preserve latest successful quote per instrument

**Destination:** quote table in Supabase

**Error handling:**
- If DB upsert fails, retain in-memory quotes for current command but report persistence error
- Do not overwrite good quote rows with empty/invalid quote payloads

### Pipeline 6: Valuation Application
**Source:** FIFO-enriched trades + persisted/latest quote map

**Steps:**
1. Match each open row to quote record by instrument key
2. Set `mtm_price = mark`
3. Compute `mtm_value`
4. Compute row-level unrealized P&L
5. Aggregate to underlying symbol position summaries and totals

**Destination:** CLI render models + web position models

**Error handling:**
- If quote missing, set `mtm_price = 0`, `mtm_value = 0`, `quote_status = unavailable`
- Preserve realized P&L even when unrealized cannot be computed

---

## Quote and Valuation Rules

### Instrument Types
Two instrument classes are required:
- **equity**
- **option**

### Contract Key Rules
A unique quote identity is required.

#### Equity Key
Recommended canonical key:
`EQ::<symbol>`

Example:
`EQ::AAPL`

#### Option Key
Recommended canonical key:
`OPT::<underlying_symbol>::<expiry_yyyymmdd>::<put_call>::<strike_normalized>::<multiplier>`

Example:
`OPT::AAPL::20260619::C::150.0000::100`

Notes:
- normalize strike to fixed precision string
- normalize expiry to `YYYYMMDD`
- normalize put/call to `C` or `P`
- multiplier default is `100` for US equity options unless source data states otherwise
- if IBKR `conid` becomes available, store it as additional identity, but do not make phase-1 logic depend exclusively on it

### Mark Price Rules
#### Equities
Preferred order:
1. IBKR last or market price
2. Yahoo regular market price (fallback only)
3. previous close if explicitly chosen later

#### Options
Preferred order:
1. midpoint of bid and ask when both are present and positive
2. last price when midpoint unavailable
3. close / model value only if explicitly available and approved in implementation
4. otherwise unavailable

Formula:
- if `bid > 0` and `ask > 0`, `mark = (bid + ask) / 2`
- else if `last > 0`, `mark = last`
- else mark is null/unavailable

### MTM Value Rules
#### Equities
`mtm_value = mark * remaining_qty`

#### Options
`mtm_value = mark * remaining_qty * multiplier`

### Basis / Credit Rule
Keep existing row-level basis convention:
`credit = remaining_qty * trade_price * multiplier * -1`

For stocks, multiplier should default to 1.
For options, multiplier should usually be 100.

### Unrealized P&L Rule
Use row-level signed formula:
`unrealized_pnl = mtm_value + credit`

This rule must support:
- long stock
- short stock
- long call/put
- short call/put

### Quote Freshness Rules
Store freshness metadata:
- `quote_time`
- `quote_source`
- `quote_status`

Suggested statuses:
- `live`
- `delayed`
- `stale`
- `unavailable`
- `permission_denied`
- `contract_unresolved`
- `gateway_unreachable`

A stale quote should still be viewable, but flagged.

---

## Logic Flows

### Flow: MTM Refresh Command
**Trigger:** CLI user runs `M` / `mtm`

**Steps:**
1. Load trades from Supabase
2. Run FIFO calculation
3. Identify open positions
4. Build unique contract set
5. Attempt IB Gateway connection
6. If connection succeeds:
   - resolve stock + option contracts
   - request quotes
   - normalize and persist quotes
7. If connection fails:
   - request Yahoo fallback quotes for equities only
   - mark all option quotes unavailable
8. Reload trades / latest quotes
9. Recompute MTM and unrealized values
10. Render updated summary

**DECISION branches:**
- IBKR available? YES → primary quote path
- IBKR available? NO → Yahoo equities fallback + options unavailable
- Contract resolved? YES → request quote
- Contract resolved? NO → mark unresolved
- Quote valid? YES → persist and use
- Quote valid? NO → mark unavailable/stale

**Exit:** Updated CLI position data with source-aware quote status

### Flow: Web Position Load
**Trigger:** User opens IBKR web page / positions page

**Steps:**
1. Load trades from Supabase
2. Run FIFO calculation in web layer or shared server-side logic
3. Load latest persisted quotes from Supabase
4. Apply quotes by instrument key
5. Compute MTM values and unrealized P&L
6. Render position tables and totals

**DECISION branches:**
- Quote exists? YES → apply MTM
- Quote missing? NO → show unavailable/stale state
- Option quote exists? YES → include in option unrealized totals
- Option quote missing? NO → exclude from unrealized or show null based on UI convention

**Exit:** Web position screens show broker-backed stock + option MTM

### Flow: Contract Resolution for Options
**Trigger:** Open option position encountered during MTM refresh

**Steps:**
1. Read underlying symbol, expiry, put/call, strike, multiplier
2. Normalize values
3. Build option contract object for IBKR API
4. Qualify contract via IBKR
5. Persist mapping if needed (phase 2)

**DECISION branches:**
- All required fields present? NO → invalid contract
- IBKR qualification success? YES → request quote
- IBKR qualification success? NO → unresolved contract

**Exit:** Qualified option contract or unresolved contract status

### Flow: Gateway Down / Session Expired
**Trigger:** IBKR API call fails at connection or request layer

**Steps:**
1. Mark gateway status as unavailable
2. Do not retry in tight loop
3. For equities only, attempt Yahoo fallback
4. For options, return unavailable/stale state
5. Report operational message to user

**Exit:** Graceful degraded mode without incorrect option pricing

---

## Module / Interface Boundaries

### Module: Quote Provider Interface
**Responsibility:** abstract quote retrieval across providers

**Exposes:**
- `connect() -> ProviderStatus`
- `fetch_equity_quotes(contracts: list[EquityContract]) -> list[QuoteRecord]`
- `fetch_option_quotes(contracts: list[OptionContract]) -> list[QuoteRecord]`
- `disconnect() -> None`

**Depends on:** provider implementations

### Module: IBKR Gateway Provider
**Responsibility:** fetch quotes from local IB Gateway API session

**Exposes:**
- `connect() -> ProviderStatus`
- `qualify_equity_contracts(...) -> list[QualifiedEquityContract]`
- `qualify_option_contracts(...) -> list[QualifiedOptionContract]`
- `fetch_equity_quotes(...) -> list[QuoteRecord]`
- `fetch_option_quotes(...) -> list[QuoteRecord]`

**Depends on:** `ib_insync` or equivalent IBKR client library, local IB Gateway session

### Module: Yahoo Fallback Provider
**Responsibility:** fetch stock quotes only when IBKR unavailable

**Exposes:**
- `fetch_equity_quotes(contracts: list[EquityContract]) -> list[QuoteRecord]`

**Depends on:** `yahooquery`

**Constraints:**
- must reject option contract requests

### Module: Contract Normalizer
**Responsibility:** convert open trade rows into canonical instrument keys and provider contract objects

**Exposes:**
- `to_equity_contract(trade_row) -> EquityContract`
- `to_option_contract(trade_row) -> OptionContract`
- `build_contract_key(contract) -> str`

**Depends on:** trade schema

### Module: Quote Repository
**Responsibility:** persist and retrieve normalized quotes from Supabase

**Exposes:**
- `upsert_quotes(quotes: list[QuoteRecord]) -> SaveResult`
- `fetch_latest_quotes() -> dict[str, QuoteRecord]`
- `fetch_quotes_by_keys(keys: list[str]) -> dict[str, QuoteRecord]`

**Depends on:** Supabase client

### Module: Valuation Engine
**Responsibility:** apply quotes to open trades and compute MTM + unrealized values

**Exposes:**
- `apply_quotes(trades, quotes_by_key) -> trades`
- `calculate_row_unrealized(trade) -> float | None`
- `calculate_position_totals(trades) -> positions`

**Depends on:** FIFO output + quote records

### Module: CLI MTM Orchestrator
**Responsibility:** run the end-to-end refresh flow for command `M`

**Exposes:**
- `refresh_mtm() -> RefreshSummary`

**Depends on:** trade loader, FIFO, contract normalizer, providers, repository, valuation engine

### Module: Web Quote Consumer
**Responsibility:** use persisted quotes to compute/render web position state

**Exposes:**
- server-side or shared utility to join latest quotes with trades

**Depends on:** quote repository, valuation engine

---

## Data Schemas

### EquityContract
```text
instrument_type: 'equity'
symbol: str
contract_key: str           # EQ::<symbol>
source_symbol: str
currency: str | None
```

### OptionContract
```text
instrument_type: 'option'
underlying_symbol: str
symbol: str                 # raw trade symbol if present
expiry: str                 # YYYYMMDD normalized
put_call: 'C' | 'P'
strike: Decimal | float
multiplier: int | float
contract_key: str           # OPT::<underlying>::<expiry>::<P/C>::<strike>::<multiplier>
conid: str | None
currency: str | None
```

### QuoteRecord
```text
contract_key: str
instrument_type: 'equity' | 'option'
source: 'ibkr' | 'yahoo_fallback'
symbol: str
underlying_symbol: str | None
expiry: str | None
put_call: str | None
strike: Decimal | float | None
multiplier: int | float | None
conid: str | None
bid: float | None
ask: float | None
last: float | None
close: float | None
mark: float | None
quote_time: timestamp | None
status: str                 # live|delayed|stale|unavailable|...
raw_payload: json | None    # optional for diagnostics
updated_at: timestamp
```

### Trade Extensions (computed, not necessarily persisted immediately)
```text
contract_key: str | None
quote_source: str | None
quote_status: str | None
mtm_price: float | None
mtm_value: float | None
unrealized_pnl: float | None
```

---

## Database Changes

### New Table: `market_quotes`
Recommended to add a new table rather than overloading the existing `market_price` table.

Suggested schema:
```sql
CREATE TABLE IF NOT EXISTS market_quotes (
    contract_key TEXT PRIMARY KEY,
    instrument_type TEXT NOT NULL,
    source TEXT NOT NULL,
    symbol TEXT,
    underlying_symbol TEXT,
    expiry TEXT,
    put_call TEXT,
    strike NUMERIC,
    multiplier NUMERIC,
    conid TEXT,
    bid NUMERIC,
    ask NUMERIC,
    last NUMERIC,
    close NUMERIC,
    mark NUMERIC,
    status TEXT,
    quote_time TIMESTAMPTZ,
    raw_payload JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Suggested indexes:
```sql
CREATE INDEX IF NOT EXISTS idx_market_quotes_symbol ON market_quotes(symbol);
CREATE INDEX IF NOT EXISTS idx_market_quotes_underlying_symbol ON market_quotes(underlying_symbol);
CREATE INDEX IF NOT EXISTS idx_market_quotes_quote_time ON market_quotes(quote_time);
CREATE INDEX IF NOT EXISTS idx_market_quotes_instrument_type ON market_quotes(instrument_type);
```

### Existing Table Compatibility
Keep `market_price` temporarily during migration if the web or CLI still references it.

Migration strategy:
1. Add `market_quotes`
2. Update CLI to write/read from `market_quotes`
3. Update web to read from `market_quotes`
4. Remove `market_price` references after successful cutover
5. Drop `market_price` only after verification

### Optional Trade Table Additions
Optional but helpful for later stability:
- `contract_key`
- `ibkr_conid`

These are not mandatory in phase 1 if contract keys are recomputed on demand.

---

## File / Directory Structure

Proposed layout within `~/Projects/tt2026web/`:

```text
cli/
  ibkr_module.py                      # orchestrates MTM refresh command
  services/
    quote_service.py                  # orchestration entrypoint
    valuation_service.py              # apply quotes and compute MTM/unrealized
  providers/
    quote_provider.py                 # interface/base protocol
    ibkr_gateway_provider.py          # primary provider
    yahoo_equity_provider.py          # fallback provider
  domain/
    contracts.py                      # EquityContract / OptionContract builders
    quotes.py                         # QuoteRecord schema helpers
  db/
    ibkr_db.py                        # trade persistence
    market_quote_db.py                # quote persistence
shared/
  ibkr_gateway_config.py              # host/port/client id/env config
scripts/
  migrations/
    2026xx_add_market_quotes.sql
web/
  src/
    lib/
      utils/
        fifo.ts                       # updated to use contract keys + option MTM
      quotes/
        applyQuotes.ts                # optional extraction for MTM application
    server/
      data/
        marketQuotes.ts               # quote fetchers from Supabase
```

---

## CLI Changes

### Command Behavior
Current command:
- `M` / `mtm`

New behavior:
- refresh quotes from IB Gateway for all open equity and option positions
- fallback to Yahoo for equities only if IBKR unavailable
- persist quotes into `market_quotes`
- reload and display updated MTM values with quote status/source

### Display Changes
Add or expose in CLI where useful:
- quote source
- quote status
- option MTM / unrealized values
- stale or unavailable quote indicators

### Position Summary Changes
Current summaries calculate stock unrealized only.
New summaries must include:
- stock unrealized
- call unrealized
- put unrealized
- total unrealized

### Performance View Changes
Replace hard-coded:
- `call_unrealized = 0.0`
- `put_unrealized = 0.0`

With calculated values derived from open option positions using quote records.

---

## Web Changes

### FIFO / MTM Utility Updates
Current web logic explicitly zeroes option MTM.

Required changes:
- generate `contract_key` per trade row
- load latest `market_quotes`
- apply quote by `contract_key`
- for equities: `mtm_value = mark * remaining_qty`
- for options: `mtm_value = mark * remaining_qty * multiplier`
- compute `unrealized_pnl = mtm_value + credit`

### Position Aggregation Updates
Current position aggregation builds MTM from `stockTrades` only.

New aggregation should compute separately:
- stock value / stock MTM / stock unrealized
- call MTM / call unrealized
- put MTM / put unrealized
- total MTM / total unrealized

### UI Behavior
Where quotes are missing or stale:
- do not silently show zero as if it were a true market value
- show blank, unavailable, or stale indicator
- preserve realized P&L display regardless of quote availability

---

## Provider Selection Rules

### Primary Path
Use IB Gateway provider when:
- gateway connection available
- session authenticated
- market data permissions valid

### Fallback Path
Use Yahoo fallback provider only when:
- IB Gateway unavailable or unreachable
- instrument type is equity

### No Fallback Path
Do not use Yahoo for:
- call options
- put options

If IBKR option quote cannot be obtained:
- retain previous successful quote if policy allows and mark stale
- otherwise show unavailable

---

## Error Handling

| Scenario | Expected Behavior | Severity |
|---|---|---|
| IB Gateway not running | Equities use Yahoo fallback; options unavailable; show gateway error | High |
| IB Gateway connected but session expired | Same as above; prompt operational re-login | High |
| Market data permission missing | Mark affected quotes `permission_denied`; no fake zero pricing | High |
| Option contract missing expiry/strike/put_call | Mark `contract_unresolved`; exclude from MTM | High |
| Quote payload has no bid/ask/last | Mark unavailable or stale; do not compute false mark | Medium |
| Yahoo fallback fails | Equities unavailable; show degraded mode | Medium |
| Supabase write fails | Use in-memory results for current run if available; report persistence error | Medium |
| Multiple open rows share same option contract | Fetch one quote, reuse for all rows | Low |
| Multiplier missing on option trade | Default cautiously if product rules allow; otherwise unresolved | High |
| Stale last quote on illiquid option | Prefer midpoint over last; flag stale when timestamp old | Medium |
| Nightly IBKR session reset | Next refresh transitions to fallback/unavailable until gateway re-login | High |
| Paper/live account mismatch | Provider should fail fast with clear account/session message | Medium |
| Underlying symbol differs from raw option symbol representation | Contract key must use normalized option fields, not raw symbol alone | High |
| Negative quantities (shorts) | Valuation must remain signed and correct | High |
| Zero remaining quantity | Exclude from quote request set | Low |

---

## Operational Notes
- IB Gateway login and 2FA are manual operational steps outside TradeTools
- TradeTools must not attempt to automate or bypass 2FA
- Expect periodic session expiration / nightly reset behavior from IBKR
- Quote refresh should be user-invoked or scheduled conservatively, not polled aggressively
- Respect IBKR pacing and market data subscription rules
- Ensure the account has:
  - API market data acknowledgement enabled
  - required equity and options market data subscriptions

---

## Migration Plan

### Phase 1: Foundation
1. Add `market_quotes` table
2. Add quote provider interface and domain schemas
3. Implement contract key generation
4. Implement quote repository

### Phase 2: IBKR Primary Provider
1. Implement IB Gateway provider
2. Support equity contract qualification
3. Support option contract qualification
4. Normalize quote payload into shared schema

### Phase 3: Yahoo Stock Fallback
1. Implement stock-only fallback provider
2. Integrate provider selection logic
3. Ensure options never route to Yahoo

### Phase 4: CLI Integration
1. Refactor `process_mtm_update()` into quote service orchestration
2. Update CLI summaries to include option unrealized
3. Add quote source/status visibility where useful

### Phase 5: Web Integration
1. Replace stock-only MTM application in web FIFO utilities
2. Load quotes from `market_quotes`
3. Compute option MTM/unrealized
4. Update UI states for unavailable/stale data

### Phase 6: Cleanup
1. Remove legacy `market_price` dependencies
2. Remove assumptions that options MTM is zero
3. Add operational docs for running IB Gateway and refreshing quotes

---

## Open Questions & Spikes
1. **IBKR API choice at implementation level**
   - Use `ib_insync` over native IB API if acceptable.
   - Spike required only if environment or deployment constraints prevent it.

2. **Contract qualification persistence**
   - Should qualified `conid` mappings be cached in DB to reduce repeated qualification overhead?
   - Recommended as phase 2.5 if quote refresh latency becomes noticeable.

3. **Quote freshness threshold**
   - Need a policy for when a quote becomes `stale` in CLI/web.
   - Suggested starting point: stale if quote timestamp older than configurable threshold during market hours.

4. **Use of prior close / model values for options**
   - If bid/ask/last absent, should UI show previous saved quote or leave null?
   - Recommended default: keep latest saved quote only if visibly marked stale.

5. **Where valuation logic should live long-term**
   - Today FIFO logic exists in both Python and TypeScript.
   - Long-term, consider consolidating valuation rules into a single backend/shared service to avoid drift.

---

## Assumptions
- Project remains single-user / self-hosted
- IB Gateway will run locally or on a reachable trusted host
- Manual IBKR login with 2FA is acceptable operationally
- Trade import continues via Flex Query API
- Trade rows contain enough option metadata to reconstruct contracts:
  - underlying symbol
  - expiry
  - strike
  - put/call
  - multiplier
- YahooQuery remains acceptable for equity-only fallback
- Exact UI styling and wording for status indicators are implementation details for Neo

---

## Summary for Neo
Build a **shared quote architecture** with these invariants:
- **IB Gateway is the primary quote source for both stocks and options**
- **YahooQuery is fallback for stocks only**
- **Options are always quoted and valued at the contract level**
- **Store normalized quotes in a new `market_quotes` table keyed by canonical `contract_key`**
- **Use bid/ask midpoint as the preferred option mark**
- **Compute option MTM using multiplier**
- **Compute unrealized using signed row formula `mtm_value + credit`**
- **Update both CLI and web to consume the same quote model and stop assuming options MTM is zero**
