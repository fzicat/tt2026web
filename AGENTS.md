# AGENTS.md - tt2026web

## What this project is

TradeTools is a personal trading/portfolio management application with **two interfaces** backed by the **same Supabase PostgreSQL database**:

- **CLI**: Python + Rich terminal UI
- **Web**: Next.js + React + Tailwind frontend

Core domains:
- **IBKR** trade import + position/P&L tracking
- **FBN** monthly/yearly account tracking
- **Equity** personal asset snapshot tracking

This repo is **not just a frontend**. Most of the mature business logic originally lives in the **Python CLI modules**, but some core IBKR calculation logic has also been reimplemented in the web layer under `web/src/lib/utils/fifo.ts`.

---

## High-level architecture

```text
tt2026web/
├── cli/                    # Python terminal app (Rich)
│   ├── main.py             # App bootstrap, auth, module switching, render loop
│   ├── home_module.py      # Main menu / navigation
│   ├── ibkr_module.py      # IBKR import, FIFO P&L, MTM, stats, position views
│   ├── fbn_module.py       # FBN monthly/yearly/account workflows
│   ├── equity_module.py    # Equity entry CRUD, copy, pivot views
│   └── db/                 # Supabase data access wrappers per domain
├── shared/
│   ├── config.py           # Loads root .env
│   └── supabase_client.py  # Python Supabase singleton + auth helpers
├── web/                    # Next.js app
│   ├── package.json
│   └── src/
│       ├── app/            # App Router entrypoints
│       ├── lib/            # Auth, error context, Supabase client utils
│       ├── components/     # UI building blocks
│       └── types/          # TS domain models / enums
├── scripts/
│   └── supabase_schema.sql # DB schema + RLS policies
├── .env.example
└── t.bat                   # Windows shortcut to run CLI
```

---

## Fastest way to understand the app

If you are a new agent/model, read these first in order:

1. `README.md`
2. `scripts/supabase_schema.sql`
3. `cli/main.py`
4. `cli/ibkr_module.py`
5. `cli/fbn_module.py`
6. `cli/equity_module.py`
7. `cli/db/ibkr_db.py`, `cli/db/fbn_db.py`, `cli/db/equity_db.py`
8. `shared/config.py` and `shared/supabase_client.py`
9. `web/src/types/index.ts`
10. `web/src/lib/auth.tsx`, `web/src/lib/supabase.ts`, `web/src/lib/utils/fifo.ts`, `web/src/lib/utils/format.ts`, `web/src/app/layout.tsx`, `web/src/app/page.tsx`, `web/src/app/login/page.tsx`

If you need to change business rules, start by checking both the **CLI module** and the mirrored web utility layer. For IBKR math in particular, compare `cli/ibkr_module.py` with `web/src/lib/utils/fifo.ts` and keep them aligned.

---

## Runtime model

### CLI side
The CLI is a stateful terminal app.

- `cli/main.py`:
  - authenticates user against Supabase Auth
  - builds a Rich layout
  - switches between modules (`ibkr`, `fbn`, `equity`)
  - handles optional auto-login and direct-module launch via CLI args

Command-line entry:
```bash
python cli/main.py
```

Optional args:
- `-l / --login`
- `-p / --password`
- `-m / --module` (`ibkr`, `fbn`, `equity`)

### Web side
The web app is a Next.js 16 App Router app.

Inspected pieces show:
- root layout wraps everything in:
  - `AuthProvider`
  - `ErrorProvider`
- root page redirects:
  - authenticated user -> `/ibkr`
  - unauthenticated user -> `/login`
- login is Supabase email/password auth
- styling is Gruvbox-themed via CSS custom properties + Tailwind 4

The web app appears to mirror CLI concepts, but the most detailed domain behavior inspected so far is in the Python code.

---

## Environment and credentials

### Root `.env` (used by Python CLI)
Loaded by `shared/config.py`.

Expected variables:
- `SUPABASE_URL`
- `SUPABASE_KEY` -> **service role key** for backend/CLI
- `SUPABASE_ANON_KEY`
- `IBKR_TOKEN`
- `QUERY_ID_DAILY`
- `QUERY_ID_WEEKLY`

### `web/.env.local` (used by Next.js)
Expected variables:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `IBKR_TOKEN`
- `QUERY_ID_DAILY`

### Important distinction
- **CLI uses service-role access** via `shared/supabase_client.py`
- **Web uses anon key + user auth** via `web/src/lib/supabase.ts`

This means the CLI currently has broader DB power than the browser app.

---

## Database schema

Declared in `scripts/supabase_schema.sql`.

### Tables

#### `trades`
IBKR trades and trade confirmations.
Key fields:
- `trade_id` (PK)
- `account_id`
- `underlying_symbol`
- `symbol`
- `description`
- `expiry`
- `put_call`
- `strike`
- `date_time`
- `quantity`
- `trade_price`
- `multiplier`
- `ib_commission`
- `currency`
- `notes`
- `open_close_indicator`
- `delta`
- `und_price`

#### `market_price`
Latest mark-to-market prices by symbol.
- `symbol` (PK)
- `price`
- `date_time`

#### `fbn`
Monthly account tracking snapshots.
- `id` (identity PK)
- `date`
- `account`
- `portfolio`
- cash-flow/value fields (`investment`, `deposit`, `interest`, `dividend`, `distribution`, `tax`, `fee`, `other`, `cash`, `asset`)
- `currency`
- `rate`
- unique constraint on `(date, account)`

#### `equity`
General asset snapshot table.
- `id` (identity PK)
- `date`
- `description`
- `account`
- `category`
- `currency`
- `rate`
- `balance`
- `tax`

### RLS model
RLS is enabled on all declared tables.
Policies allow **all operations for any authenticated user**.
This is effectively a **single-user authenticated app** model.

---

## Important schema/code mismatch

### `symbol_targets` is used by code but missing from schema
`cli/db/ibkr_db.py` reads from:
- `symbol_targets(symbol, target_percent)`

`web/src/types/index.ts` also defines:
- `SymbolTarget`

But `scripts/supabase_schema.sql` does **not** create this table.

If anything target-allocation related breaks, this is the first place to look.

---

## Domain logic by module

# 1) IBKR

Primary files:
- `cli/ibkr_module.py`
- `cli/db/ibkr_db.py`

### What it does
- Imports trades from **Interactive Brokers Flex Query API**
- Stores trades into Supabase
- Computes **FIFO realized P&L** in memory
- Computes remaining open quantities
- Saves/fetches latest market prices
- Produces position summaries and daily/weekly stats

### Import flow
`IBKRModule.import_trades()`:
1. Calls IBKR Flex `SendRequest`
2. Polls generated report URL
3. Parses XML when ready
4. Accepts both `Trade` and `TradeConfirm`
5. Maps fields into app format
6. Upserts into `trades`

### Trade normalization details
When parsing XML:
- `tradePrice` may come from `tradePrice` or fallback `price`
- `ibCommission` may come from `ibCommission` or fallback `commission`
- `openCloseIndicator` may be inferred from `code` if missing

### Snake/camel mapping
Python DB layer maps UI-style camelCase fields to Postgres snake_case.
Important mapping lives in:
- `cli/db/ibkr_db.py`
- `web/src/lib/supabase.ts`

If you add/rename trade fields, update both places.

### FIFO realized P&L algorithm
Implemented in:
- `cli/ibkr_module.py` -> `IBKRModule.calculate_pnl()`
- `web/src/lib/utils/fifo.ts` -> `calculatePnL()`

The web layer mirrors the same inventory/FIFO idea, so future fixes must consider both implementations.

Rules:
- inventory is grouped by **`symbol`**
- lots are matched **FIFO**
- only opposite-signed trades close prior lots
- same-signed trades add to inventory
- per-row derived fields are calculated in memory:
  - `realized_pnl`
  - `remaining_qty`

Important notes:
- P&L uses `quantity`, `tradePrice`, `multiplier`
- commissions are displayed but not explicitly netted in FIFO calc formula
- derived P&L is **not persisted back** to the database

### Additional IBKR derived fields
After loading trades:
- `USD.CAD` is filtered out entirely in the CLI flow
- `credit = remaining_qty * tradePrice * multiplier * -1`
- `mtm_price` is set only for **non-option** rows
- `mtm_value = mtm_price * remaining_qty`

Web utility equivalents exist in `web/src/lib/utils/fifo.ts`:
- `calculateCredit()`
- `applyMtmPrices()`
- `groupByUnderlying()`
- `calculatePositions()`
- `calculateTotals()`

### MTM rules
`process_mtm_update()`:
- updates **non-option** symbols only (`putCall` not `C`/`P`)
- uses `yahooquery.Ticker(...).price`
- prefers `regularMarketPrice`
- falls back to `regularMarketPreviousClose`
- saves prices into `market_price`

### Position grouping logic
Position views are grouped by **`underlyingSymbol`**, not raw `symbol`.
Within each group, rows are split into:
- stock rows (`putCall` not `C`/`P`)
- call rows (`putCall == 'C'`)
- put rows (`putCall == 'P'`)

This is a key mental model for how the app thinks about “positions”.

The same grouping rule is explicitly mirrored in web code via `groupByUnderlying()` and `calculatePositions()`.

### Stats behavior
#### Daily stats
- grouped by trade date
- includes weekdays even when P&L is zero
- includes weekends only if P&L is non-zero
- hardcoded start date: **2026-01-05**

#### Weekly stats
- resampled as **week ending Friday** (`W-FRI`)
- hardcoded first week filter: **2026-01-09**

These hardcoded dates are business assumptions, not generic logic.

### IBKR commands in CLI
Main ones:
- import daily / weekly trades
- update MTM
- show `performance` / `pf` year-performance tables in `$` and `%`
- list positions in multiple sort modes
- list trades
- show daily/weekly stats
- inspect a single symbol
- edit `delta` / `und_price`

### IBKR performance file
Year-performance uses:
- `cli/data/ibkr_performance_2026.csv`

Expected CSV format:
```csv
date,type,amount
2026-01-01,start,372834
2026-01-08,deposit,27398
```

Supported `type` values:
- `start`
- `deposit`
- `withdrawal`
- `flow` (signed amount)

Current rule:
- calls/puts unrealized PnL is intentionally ignored and shown as `0`
- percentage denominator is `starting_value + net_deposits_withdrawals_since_start`

### IBKR gotchas
- `symbol_targets` dependency is missing from schema script
- duplicate `except Exception` block exists in `process_mtm_update()`
- market price update ignores options by design
- `remaining_qty`, `credit`, `mtm_value`, `realized_pnl` are computed after fetch, not stored as canonical DB fields
- there are **duplicated finance calculations** across Python and TypeScript, so logic drift is a real risk

---

# 2) FBN

Primary files:
- `cli/fbn_module.py`
- `cli/db/fbn_db.py`
- `web/src/types/index.ts`

### What it does
Tracks monthly snapshots for several predefined accounts, then derives:
- monthly deposit / asset / fee / pnl / pct
- yearly rollups
- monthly and yearly asset matrices by account

### Fixed account catalog
The app has a predefined account list. This matters because UI ordering and summaries assume it.

Accounts:
- `MARGE`
- `REER`
- `CRI`
- `REEE`
- `CELI`
- `MM MARGE`
- `MM CELI`
- `GFZ CAD`
- `GFZ USD`

Portfolios/currencies are fixed in code.

### Currency conversion rule
Before aggregation:
- rows where `currency == 'USD'` are converted to CAD by multiplying relevant numeric fields by `rate`

Converted columns include:
- `investment`
- `deposit`
- `asset`
- `fee`
- `dividend`
- `interest`
- `tax`
- `other`
- `cash`
- `distribution`

### Monthly P&L logic
For aggregated month rows:
- `prev_asset = prior month asset`
- `pnl = asset - deposit - prev_asset`
- `pct = pnl / prev_asset` when `prev_asset != 0`, else `0`

### Yearly rollup logic
For each year:
- `deposit` = sum of yearly monthly deposits
- `fee` = sum of yearly monthly fees
- `asset` = asset of last month in the year
- then same `prev_asset` / `pnl` / `pct` logic is applied year-over-year

### Data entry workflow
`add_monthly_data()` is interactive:
1. select target month/date
2. pick account(s)
3. load existing values if present
4. enter numeric fields
5. validate values visually
6. save

### Save semantics
`fbn_db.save_account_entry()` does **delete then insert** on `(date, account)`.
It does not use a single DB-side upsert.

This is fine for single-user operation, but it is not ideal for concurrency.

### FBN gotchas
- account catalog is duplicated in more than one place (CLI + web types)
- currency conversion happens in memory before reporting
- save path is not transactional upsert; it is delete-then-insert behavior

---

# 3) Equity

Primary files:
- `cli/equity_module.py`
- `cli/db/equity_db.py`
- `web/src/types/index.ts`

### What it does
Stores dated asset snapshots and computes:
- CAD-equivalent balances
- post-tax net balances
- summaries by account/category
- pivot tables over time

### Core fields
Each entry has:
- `date`
- `description`
- `account`
- `category`
- `currency`
- `rate`
- `balance`
- `tax`

### Derived metrics
On load:
- `balance_cad = balance * rate`
- `balance_net = balance_cad * (1 - tax)`

### SAT special case
If `currency == 'SAT'`:
- `balance * rate` is additionally divided by `100_000_000`

Interpretation:
- `balance` is in satoshis
- `rate` is assumed to be BTC price in CAD

### Supported categories
Defined in TS types and mirrored in CLI behavior:
- `Bitcoin`
- `Cash`
- `Immobilier`
- `FBN`
- `IBKR`
- `BZ`

### Supported accounts
- `Personnel`
- `Gestion FZ`

### Equity workflows
- add entry
- list entries by date
- edit/delete an entry selected from current date view
- copy all entries from one date to another with `rate=0` and `balance=0`
- render pivot tables:
  - CAD by account
  - CAD by category
  - Net by account
  - Net by category

### Equity gotchas
- edit/delete only work after loading a date-specific current subset
- copy creates template-like rows with zeroed financial values
- sorting is by description on load

---

## Web app: inspected implementation details

Primary inspected files:
- `web/src/app/layout.tsx`
- `web/src/app/page.tsx`
- `web/src/app/login/page.tsx`
- `web/src/lib/auth.tsx`
- `web/src/lib/error-context.tsx`
- `web/src/lib/supabase.ts`
- `web/src/lib/utils/fifo.ts`
- `web/src/lib/utils/format.ts`
- `web/src/types/index.ts`
- `web/src/components/ui/Button.tsx`
- `web/src/components/ui/Input.tsx`
- `web/src/components/ui/Spinner.tsx`
- `web/src/components/ui/Table.tsx`
- `web/src/app/globals.css`

### Auth model
`AuthProvider`:
- calls `supabase.auth.getSession()` on mount
- subscribes to `onAuthStateChange`
- exposes:
  - `user`
  - `session`
  - `loading`
  - `signIn(email, password)`
  - `signOut()`

### Routing behavior
Root page (`web/src/app/page.tsx`) is a client redirect page:
- if logged in -> `/ibkr`
- if not -> `/login`

### Error model
`ErrorProvider` stores a single app-level error object:
- `{ message, timestamp }`

This is lightweight UI state, not a deep error/reporting system.

### Supabase client behavior
`web/src/lib/supabase.ts`:
- creates a singleton client from `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- enables session persistence and token refresh
- also exports snake/camel conversion helpers for DB payloads

### Important web caveat
This line matters:
```ts
export const supabase = typeof window !== "undefined" ? getSupabaseClient() : null!;
```
Meaning:
- it is meant for **client-side use only**
- importing it in a server context is unsafe

If you add server components/actions/route handlers, do **not** rely on this export directly.

### Important timestamp caveat
`web/src/lib/utils/format.ts` contains a deliberate workaround for timestamp handling:
- IBKR trade times are treated as **New York local time**
- timestamps appear to be stored in `TIMESTAMPTZ` without a proper offset
- PostgreSQL/Supabase then return them with `Z` / `+00:00`
- the frontend strips the timezone suffix and reparses the raw components as local New York time via `parseAsNY()`

This is a signal that the data model currently has a timezone correctness problem that is being patched in presentation code.

### UI system
The UI layer is simple and custom:
- theme via CSS vars in `globals.css`
- reusable `Button`, `Input`, `Spinner`, and generic `Table`
- `Table.tsx` supports:
  - declarative columns
  - custom cell renderers
  - optional sortable headers
  - row click handlers
  - dynamic row classes
- `NumericCell` helper color-codes positive values blue and negative values orange
- Gruvbox palette is hardcoded at the CSS variable level
- `.data-table` and `.row-dimmed` classes exist for table displays

---

## Cross-layer type and naming conventions

### Trade field naming mismatch is intentional
Python/UI logic uses camel-ish names such as:
- `tradeID`
- `accountId`
- `underlyingSymbol`
- `tradePrice`
- `openCloseIndicator`

Database uses snake_case:
- `trade_id`
- `account_id`
- `underlying_symbol`
- `trade_price`
- `open_close_indicator`

Mapping exists in both:
- `cli/db/ibkr_db.py`
- `web/src/lib/supabase.ts`

If a field appears missing or broken between layers, check mapping drift first.

### Shared constants duplicated across layers
Examples:
- FBN accounts
- equity categories/accounts/currencies

If changing business enums, update both CLI and web definitions.

---

## Running the project

### CLI
```bash
pip install -r cli/requirements.txt
python cli/main.py
```

### Web
```bash
cd web
npm install
npm run dev
```

### Windows helper
```bash
./t.bat
```
Runs the CLI entrypoint.

---

## Recommended debugging entrypoints

### If login/auth breaks
Check:
- `shared/config.py`
- `shared/supabase_client.py`
- `web/src/lib/auth.tsx`
- `web/src/lib/supabase.ts`
- environment variables

### If trade import breaks
Check:
- `IBKR_TOKEN`
- `QUERY_ID_DAILY` / `QUERY_ID_WEEKLY`
- `cli/ibkr_module.py::import_trades`
- XML parsing assumptions in `process_xml()`

### If P&L looks wrong
Check:
- `cli/ibkr_module.py::calculate_pnl`
- symbol grouping (`symbol` vs `underlyingSymbol`)
- sign of `quantity`
- multiplier handling
- filtered symbols like `USD.CAD`

### If target allocation / diff view breaks
Check:
- `cli/db/ibkr_db.py::fetch_symbol_targets`
- whether `symbol_targets` exists in Supabase

### If FBN totals look wrong
Check:
- currency conversion by `rate`
- first-month `prev_asset = 0` behavior
- delete-then-insert save behavior

### If equity totals look wrong
Check:
- SAT conversion rule
- `tax` expected as fraction (`0.0` to `1.0`)
- current date subset behavior for edit/delete flows

---

## Things likely worth improving later

These are not necessarily bugs, but they are important engineering hotspots:

1. **Create/migrate `symbol_targets` table** in schema.
2. **Unify business logic** so CLI and web do not drift.
3. Replace FBN delete+insert with a true upsert.
4. Move hardcoded reporting start dates out of IBKR stats logic.
5. Centralize shared enums/constants across Python and TypeScript.
6. Add tests around FIFO P&L and financial calculations.
7. Decide on a single source of truth for FIFO/position math, or extract shared logic to reduce Python/TS drift.
8. Fix IBKR timestamp storage/normalization so `parseAsNY()` is not needed as a workaround.
9. Make web Supabase usage safe for server/client boundaries.

---

## Reality check: README drift

The README is directionally correct, but some inspected code is more specific than the README and some details may have evolved.
Examples:
- README says Next.js 14+, actual `package.json` is **Next.js 16.1.4**
- code depends on `symbol_targets`, but schema file does not define it

Prefer the source files over README when they disagree.

---

## Bottom line

This app is best understood as:

- a **Supabase-backed portfolio database**
- a **Python Rich CLI** containing the original mature domain workflows
- a **Next.js frontend** that handles auth, theming, typed UI access, and now also includes duplicated IBKR calculation helpers

If you are making changes, first decide whether the truth for that behavior currently lives in:
- **CLI business logic**,
- **duplicated web finance utilities**, or
- **web presentation/auth code**

For IBKR calculations, do not assume there is only one implementation. Check both Python and TypeScript before changing behavior.
