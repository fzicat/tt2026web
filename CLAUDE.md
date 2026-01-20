# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Applications

**CLI App:**
```bash
python ./cli/main.py
```

**Web App:**
coming soon

## Dependencies

Install dependencies:
```bash
pip install -r requirements.txt
```

Required packages: `rich`, `pandas`, `requests`, `yahooquery`, `supabase`

## Architecture

TradeTools is a trading portfolio management application.
CLI is a terminal-based application built with Rich for UI rendering.
Web, not yet implemented, will be a web-based application built with Next.js and React.
Both will share the same database on Supabase.

## CLI Architecture

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

## Web Architecture

Coming soon

## Configuration

`shared/config.py` contains:
- Supabase credentials (URL and key)
- IBKR Flex Query credentials (token and query IDs)
