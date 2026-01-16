# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Applications

**CLI App:**
```bash
python main.py
```

**Web App:**
```bash
uvicorn web.main:app --reload
```
Then open http://127.0.0.1:8000

## Dependencies

Install dependencies:
```bash
pip install -r requirements.txt
```

Required packages: `rich`, `pandas`, `requests`, `fastapi`, `uvicorn`, `pydantic`

Optional: `yahooquery` for fetching market prices (IBKR MTM feature)

## Architecture

TradeTools v3 is a terminal-based trading portfolio management application built with Rich for UI rendering.

### Core Components

**Main Application (`main.py`)**
- `TradeToolsApp`: Main application class with Rich Console and Layout
- Uses Gruvbox color theme throughout
- Main loop: render layout -> get prompt -> process command
- `skip_render` flag allows modules to bypass layout rendering for large outputs

**Module System**
- `base_module.py`: Abstract `Module` class defining the interface
  - `handle_command(command)`: Process user input
  - `get_output()`: Return content for the body panel
  - `get_prompt()`: Return the command prompt string
- Modules switch via `app.switch_module(ModuleInstance)`
- Circular imports avoided by local imports in command handlers

**Available Modules**
- `HomeModule`: Main menu, routes to other modules (i, f, e commands)
- `IBKRModule`: Interactive Brokers trade management
- `FBNModule`: FBN account tracking (monthly/yearly stats)
- `EquityModule`: Personal equity/asset tracking

### Database Layer

Databases are stored in `./data/` folder, shared between CLI and web apps.

CLI db handlers (`*_db_handler.py`) use `shared.config.DB_PATH` for database location:
- `ibkr_db_handler.py` -> `data/ibkr.db` (trades, market_price tables)
- `fbn_db_handler.py` -> `data/fbn.db` (fbn table)
- `equity_db_handler.py` -> `data/equity.db` (equity table)

Pattern: `init_db()` creates tables, `fetch_*()` returns DataFrames, `save_*()` inserts/updates

### Web Application (`web/`)

FastAPI-based web app with vanilla HTML/CSS/JS frontend:
- `web/main.py`: FastAPI entry point, serves static files and templates
- `web/db.py`: Database connection layer
- `web/routers/ibkr.py`: IBKR REST API routes
- `web/services/ibkr_service.py`: Business logic (ports CLI's PnL calculation)
- `web/templates/index.html`: Single-page app HTML
- `web/static/css/style.css`: Gruvbox dark theme styling
- `web/static/js/app.js`: Frontend JavaScript

API endpoints: `/api/ibkr/positions`, `/api/ibkr/positions/{symbol}`, `/api/ibkr/trades`, `/api/ibkr/import`, `/api/ibkr/mtm`, `/api/ibkr/stats/daily`, `/api/ibkr/stats/weekly`

### IBKR Module Specifics

- Imports trades via IBKR Flex Query API (XML parsing)
- FIFO-based PnL calculation in `calculate_pnl()`
- Tracks positions for stocks and options (putCall field: C/P or empty)
- MTM (Mark-to-Market) via yahooquery for current prices
- `target_percent` dict defines portfolio allocation targets

### UI Patterns

- Long output: Use `self.app.console.print()` directly and set `self.app.skip_render = True`
- Short output: Set `self.output_content` (string or Rich renderable like Table)
- Navigation: `q` returns to parent module, `qq` exits application

## Configuration

`shared/config.py` contains:
- IBKR Flex Query credentials (token and query IDs)
- `DB_PATH`: Path to shared database folder (`./data/`)
