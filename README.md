# TradeTools

A personal trading portfolio management app with two interfaces — a terminal CLI and a web dashboard — sharing the same Supabase database.

## Features

- **IBKR Trade Import** — Pull trades from Interactive Brokers via Flex Query API
- **FIFO P&L** — Automatic realized/unrealized profit & loss using FIFO matching
- **Mark-to-Market** — Live position pricing via Yahoo Finance
- **FBN Tracking** — Monthly and yearly account stats (investments, dividends, fees, etc.)
- **Equity Tracking** — Personal asset/balance tracking with pivot tables
- **Gruvbox Dark Theme** — Consistent dark theme across both interfaces

## Architecture

```
├── cli/          # Python terminal app (Rich)
├── web/          # Next.js web app (React + Tailwind)
├── shared/       # Shared Python config & Supabase client
└── scripts/      # DB schema & migration scripts
```

Both interfaces read and write to the same Supabase PostgreSQL database. The CLI is built with [Rich](https://github.com/Textualize/rich) for terminal rendering; the web app uses Next.js 14+ with the App Router.

## Prerequisites

- Python 3.10+
- Node.js 20+
- A [Supabase](https://supabase.com) project
- An [Interactive Brokers](https://www.interactivebrokers.com) account with Flex Query access (for IBKR features)

## Setup

### 1. Database

Run the schema script in your Supabase SQL Editor:

```sql
-- scripts/supabase_schema.sql
```

This creates the `trades`, `market_price`, `fbn`, and `equity` tables with row-level security.

### 2. Environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_KEY=<service-role-key>
SUPABASE_ANON_KEY=<anon-key>
IBKR_TOKEN=<your-ibkr-flex-token>
QUERY_ID_DAILY=<your-daily-query-id>
```

For the web app, create `web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
IBKR_TOKEN=<your-ibkr-flex-token>
QUERY_ID_DAILY=<your-daily-query-id>
```

### 3. CLI

```bash
pip install -r cli/requirements.txt
python cli/main.py
```

### 4. Web

```bash
cd web
npm install
npm run dev
```

The web app runs at `http://localhost:3000`.

## CLI Usage

The CLI uses a module system navigated by single-key commands:

| Key | Action |
|-----|--------|
| `i` | IBKR module |
| `f` | FBN module |
| `e` | Equity module |
| `q` | Back / quit module |
| `qq` | Exit app |

## Web Routes

| Route | Description |
|-------|-------------|
| `/ibkr` | Positions overview, import & MTM |
| `/ibkr/positions/[symbol]` | Position detail |
| `/ibkr/trades` | Trade history |
| `/ibkr/stats/daily` | Daily P&L stats |
| `/ibkr/stats/weekly` | Weekly P&L stats |
| `/fbn` | Monthly account stats |
| `/fbn/yearly` | Yearly rollup |
| `/fbn/entry` | Add/edit FBN entry |
| `/fbn/assets/monthly` | Monthly assets matrix |
| `/fbn/assets/yearly` | Yearly assets matrix |
| `/equity` | Equity entries |
| `/equity/entry` | Add/edit equity entry |
| `/equity/pivot` | Pivot table view |

## Tech Stack

**CLI:** Python · Rich · pandas · yahooquery · Supabase Python SDK

**Web:** Next.js 16 · React 19 · Tailwind CSS 4 · Supabase JS · TypeScript

**Database:** Supabase (PostgreSQL) with Row Level Security

## License

Private project.
