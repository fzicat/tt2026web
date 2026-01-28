import pandas as pd

import requests
import time
import xml.etree.ElementTree as ET
from rich.table import Table
from rich.console import Group
from rich.panel import Panel
from shared import config
from cli.db import ibkr_db
from base_module import Module

class IBKRModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.trades_df = pd.DataFrame()
        self.position_map = {}
        self.current_symbol = None
        self.output_content = "IBKR Module Active\nType 'help' or 'h' for a list of commands."
        
        # Hardcoded target percentages
        self.target_percent = {
            'NVDA': 10.0,
            'GOOGL': 10.0,
            'TSLA': 10.0,
            'PLTR': 5.0,
            'CRCL': 5.0,
            'GLD': 5.0,
            'IWM': 5.0,
            'AMD': 4.0,
            'COIN': 4.0,
            'MSTR': 4.0,
            'DIS': 4.0,
            'COST': 4.0,
            'ABBV': 4.0,
            'MSFT': 3.0,
            'COPX': 3.0,
            'AVGO': 2.0,
            'INTC': 2.0,
            'GLW': 2.0,
            'IBIT': 2.0,
            'SOFI': 2.0,
            'AMZN': 2.0,
            'LLY': 2.0,
            'MRK': 2.0,
            'ORCL': 1.0,
            'META': 1.0,
            'NFLX': 1.0,
            'FCX': 1.0,
        }
        
        self.load_trades()

    def load_trades(self):
        self.trades_df = ibkr_db.fetch_all_trades_as_df()
        if not self.trades_df.empty:
            # Filter out USD.CAD
            self.trades_df = self.trades_df[self.trades_df['symbol'] != 'USD.CAD']
            
            self.calculate_pnl()
            
            # Calculate Credit: remaining_qty * price * multiplier * -1
            m = self.trades_df['multiplier'].fillna(1.0)
            self.trades_df['credit'] = self.trades_df['remaining_qty'] * self.trades_df['tradePrice'] * m * -1

            # MTM Logic
            self.trades_df['mtm_price'] = 0.0
            
            market_prices = ibkr_db.fetch_latest_market_prices()
            
            # Map prices for non-option trades
            mask = ~self.trades_df['putCall'].isin(['C', 'P'])
            self.trades_df.loc[mask, 'mtm_price'] = self.trades_df.loc[mask, 'symbol'].map(market_prices).fillna(0.0)
            
            # Calculate MTM Value
            self.trades_df['mtm_value'] = self.trades_df['mtm_price'] * self.trades_df['remaining_qty']

        count = len(self.trades_df)
        self.app.console.print(f"[info]Trades loaded: {count}[/]")

    def calculate_pnl(self):
        if self.trades_df.empty:
            return

        # Initialize columns
        self.trades_df['realized_pnl'] = 0.0
        self.trades_df['remaining_qty'] = 0.0

        # Inventory: symbol -> list of dicts {idx, qty, price}
        inventory = {}

        for idx, row in self.trades_df.iterrows():
            symbol = row['symbol']
            qty = row['quantity']
            price = row['tradePrice']
            multiplier = row['multiplier']
            
            # Ensure safe floats
            qty = float(qty) if qty is not None else 0.0
            price = float(price) if price is not None else 0.0
            multiplier = float(multiplier) if multiplier is not None else 1.0

            if symbol not in inventory:
                inventory[symbol] = []

            # Determine if we are increasing or decreasing/closing position
            # We assume FIFO matching against opposite sign
            
            # If inventory is empty, always open/add
            if not inventory[symbol]:
                self.trades_df.at[idx, 'remaining_qty'] = qty
                inventory[symbol].append({'idx': idx, 'qty': qty, 'price': price})
                continue

            # Check head of inventory
            head = inventory[symbol][0]
            # Same sign means adding to position
            if (qty > 0 and head['qty'] > 0) or (qty < 0 and head['qty'] < 0):
                self.trades_df.at[idx, 'remaining_qty'] = qty
                inventory[symbol].append({'idx': idx, 'qty': qty, 'price': price})
            else:
                # Opposite sign: Close/Reduce position
                qty_to_process = qty # e.g. -100 (Sell)
                total_pnl = 0.0

                while qty_to_process != 0 and inventory[symbol]:
                    item = inventory[symbol][0]
                    open_qty = item['qty']   # e.g. 50 (Buy)
                    open_price = item['price']
                    open_idx = item['idx']

                    # Check match amount
                    # We are reducing open_qty by some amount
                    # signs are opposite. 
                    
                    if abs(qty_to_process) >= abs(open_qty):
                        # Fully consume this open lot
                        match_qty = -open_qty # The amount of the current trade used to close the open lot
                        
                        term_pnl = -(price - open_price) * match_qty * multiplier
                        total_pnl += term_pnl
                        
                        qty_to_process -= match_qty
                        
                        # Update matched open lot
                        self.trades_df.at[open_idx, 'remaining_qty'] = 0
                        inventory[symbol].pop(0)
                        
                    else:
                        # Partially consume open lot
                        term_pnl = -(price - open_price) * qty_to_process * multiplier
                        total_pnl += term_pnl
                        
                        # Update Inventory item
                        item['qty'] += qty_to_process
                        self.trades_df.at[open_idx, 'remaining_qty'] = item['qty']
                        
                        qty_to_process = 0
                
                self.trades_df.at[idx, 'realized_pnl'] = total_pnl

                # If we still have quantity left after closing everything, it becomes new position
                if qty_to_process != 0:
                    self.trades_df.at[idx, 'remaining_qty'] = qty_to_process
                    inventory[symbol].append({'idx': idx, 'qty': qty_to_process, 'price': price})

    def process_mtm_update(self):
        if self.trades_df.empty:
            self.output_content = "[info]No trades to update.[/]"
            return

        self.app.console.print("[info]Fetching market prices...[/]")
        
        # Filter for non-option trades (Stocks)
        mask = ~self.trades_df['putCall'].isin(['C', 'P'])
        symbols_to_update = self.trades_df.loc[mask, 'symbol'].unique()
        
        if len(symbols_to_update) == 0:
            self.output_content = "[info]No non-option positions found.[/]"
            return

        try:
            tickers_str = " ".join(symbols_to_update)
            # Use yahooquery instead of yfinance
            try:
                from yahooquery import Ticker
            except ImportError:
                self.output_content = "[error]yahooquery not installed. Please install it with: pip install yahooquery[/]"
                return

            self.app.console.print(f"[info]Fetching data for {len(symbols_to_update)} symbols using yahooquery...[/]")
            
            t = Ticker(symbols_to_update, asynchronous=True)
            data = t.price
            
            # data is a dict: {symbol: {key: value, ...}}
            # We want 'regularMarketPrice'
            
            if not isinstance(data, dict):
                 self.output_content = f"[error]Unexpected response from yahooquery: {type(data)}[/]"
                 return

            current_time = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            count = 0
            
            for sym, info in data.items():
                # info might be a string if error, or dict if success
                if isinstance(info, dict):
                    price = info.get('regularMarketPrice')
                    if price is None:
                        # Fallback to previousClose or other fields
                        price = info.get('regularMarketPreviousClose')
                        
                    if price is not None:
                        self.app.console.print(f"[debug]Price for {sym}: {price}[/]")
                        ibkr_db.save_market_price(sym, float(price), current_time)
                        count += 1
                    else:
                        self.app.console.print(f"[warn]No price found for {sym}[/]")
                else:
                    self.app.console.print(f"[warn]Could not fetch data for {sym}: {info}[/]")

            self.output_content = f"Updated prices for {count} symbols."
            self.load_trades()
            
        except Exception as e:
            self.output_content = f"[error]Error fetching prices: {e}[/]"
            
        except Exception as e:
            self.output_content = f"[error]Error fetching prices: {e}[/]"

    
    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            # Local import to avoid circular dependency
            from home_module import HomeModule
            self.app.switch_module(HomeModule(self.app))
        elif cmd in ['qq', 'quit quit']:
            self.app.quit()
        elif cmd in ['h', 'help']:
            self.output_content = '''IBKR commands:\n
        - I   | import     > Import daily trades
        - I W | import w   > Import weekly trades
        - M   | mtm        > Get Mark-to-Market Values
        - SD  | stats day  > Daily PnL Stats
        - SW  | stats week > Weekly PnL Stats
        - L   | list       > List all positions
        - T   | trades     > List all trades
        - R   | reload     > Reload trades from DB
        - P x | p <sym>    > List positions for a symbol
        - DEB | debug      > Debug (print trades_df)
        - H   | help       > Show this message
        - Q   | quit       > Return to main menu
        - QQ  | quit quit  > Exit the application'''
        elif cmd in ['m', 'mtm']:
            self.process_mtm_update()
        elif cmd in ['sd', 'stats day']:
            self.stats_daily()
        elif cmd in ['sw', 'stats week']:
            self.stats_weekly()
        elif cmd in ['deb', 'debug']:
            self.debug()
        elif cmd in ['t', 'trades']:
            self.list_all_trades()
        elif cmd in ['r', 'reload']:
            self.load_trades()
            self.output_content = f"Trades reloaded. Total: {len(self.trades_df)}"
        elif cmd.startswith('p '):
            parts = command.split()
            if len(parts) >= 2:
                symbol = parts[1].upper()
                self.list_position(symbol)
            else:
                self.output_content = "[error]Usage: p <symbol>[/]"
        elif cmd in ['i', 'import']:
            self.import_trades(config.QUERY_ID_DAILY, "Daily")
        elif cmd in ['i w', 'import w', 'import weekly']:
            self.import_trades(config.QUERY_ID_WEEKLY, "Weekly")
        elif cmd in ['l', 'lm', 'list', 'list mtm']:
            self.list_all_positions(order_by='mtm', ascending=False)
        elif cmd in ['lv', 'list value']:
            self.list_all_positions(order_by='value', ascending=False)
        elif cmd in ['ls', 'list symbol']:
            self.list_all_positions(order_by='symbol', ascending=True)
        elif cmd in ['lq', 'list quantity']:
            self.list_all_positions(order_by='s_qty', ascending=False)
        elif cmd.startswith('e ') or cmd.startswith('edit '):
            parts = command.split()
            if len(parts) >= 2:
                try:
                    idx = int(parts[1])
                    self.edit_trade(idx)
                except ValueError:
                    self.output_content = "[error]Usage: edit <index>[/]"
            else:
                self.output_content = "[error]Usage: edit <index>[/]"
        elif cmd == "":
            pass
        else:
            self.output_content = f"Unknown command: {command}\nType 'help' for valid commands."

    def import_trades(self, query_id, label):
        self.app.console.print(f"[info]Requesting {label} trades report...[/]")
        token = config.IBKR_TOKEN
        
        # Step 1: Send Request
        url_req = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={token}&q={query_id}&v=3"
        try:
            resp = requests.get(url_req)
            resp.raise_for_status()
            
            # Use ElementTree.fromstring directly
            root = ET.fromstring(resp.content)
            
            # Check for Status
            status = root.find('Status')
            if status is not None and status.text == 'Success':
                ref_code = root.find('ReferenceCode').text
                base_url = root.find('Url').text
                self.app.console.print(f"[info]Report requested. Reference Code: {ref_code}. Waiting for generation...[/]")
            else:
                err_code = root.find('ErrorCode').text if root.find('ErrorCode') is not None else "Unknown"
                err_msg = root.find('ErrorMessage').text if root.find('ErrorMessage') is not None else "Unknown Error"
                self.output_content = f"[error]Error requesting report: {err_code} - {err_msg}[/]"
                return

            # Step 2: Get Statement
            # Retry loop
            url_dl = f"{base_url}?q={ref_code}&t={token}&v=3"
            print(url_dl)
            
            max_retries = 10
            for i in range(max_retries):
                time.sleep(2) # Wait a bit
                resp_dl = requests.get(url_dl)
                if resp_dl.status_code == 200:
                    # Check if it is actual XML content we want or still processing
                    if b'<FlexStatement' in resp_dl.content or b'<FlexQueryResponse' in resp_dl.content:
                        self.process_xml(resp_dl.content)
                        return
                    else:
                        self.app.console.print("[info]Waiting for report...[/]")
                else:
                    self.app.console.print(f"[info]Waiting for report... (Status: {resp_dl.status_code})[/]")
            
            self.output_content = "[error]Timeout waiting for report generation.[/]"

        except Exception as e:
            self.output_content = f"[error]Exception during import: {e}[/]"

    def process_xml(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
            # Use iteration to be namespace agnostic and handle both Trade and TradeConfirm
            trades_list = [elem for elem in root.iter() if elem.tag.endswith('Trade') or elem.tag.endswith('TradeConfirm')]
            
            if not trades_list:
                self.output_content = "[info]No trades found in the report.[/]"
                return

            count_new = 0
            for trade in trades_list:
                data = trade.attrib # ElementTree attributes are a dictionary
                
                # Sanitize numeric fields
                safe_float = lambda k: float(data[k]) if data.get(k) and data[k].strip() else None
                
                # Map alternate field names if present (TradeConfirm vs Trade)
                trade_price = safe_float('tradePrice') if 'tradePrice' in data else safe_float('price')
                ib_commission = safe_float('ibCommission') if 'ibCommission' in data else safe_float('commission')
                
                open_close = data.get('openCloseIndicator')
                if open_close is None and 'code' in data:
                    c_val = data.get('code', '')
                    if 'O' in c_val: 
                        open_close = 'O'
                    elif 'C' in c_val: 
                        open_close = 'C'

                row = {
                    'tradeID': data.get('tradeID'),
                    'accountId': data.get('accountId'),
                    'underlyingSymbol': data.get('underlyingSymbol'),
                    'symbol': data.get('symbol'),
                    'description': data.get('description'),
                    'expiry': data.get('expiry'),
                    'putCall': data.get('putCall'),
                    'strike': safe_float('strike'),
                    'dateTime': data.get('dateTime'),
                    'quantity': safe_float('quantity'),
                    'tradePrice': trade_price,
                    'multiplier': safe_float('multiplier'),
                    'ibCommission': ib_commission,
                    'currency': data.get('currency'),
                    'notes': data.get('notes'),
                    'openCloseIndicator': open_close
                }
                
                if ibkr_db.save_trade(row):
                    count_new += 1
            
            
            self.output_content = f"Import complete. {count_new} new trades imported."
            self.load_trades()
            
        except Exception as e:
            self.output_content = f"[error]Error parsing XML or saving to DB: {e}[/]"

    def list_position(self, symbol):
        try:
            if self.trades_df.empty:
                df = pd.DataFrame()
            else:
                mask = (self.trades_df['symbol'] == symbol) | (self.trades_df['underlyingSymbol'] == symbol)
                # Sort by date ascending (oldest on top)
                df = self.trades_df[mask].copy()
                df['dateTime'] = pd.to_datetime(df['dateTime'], errors='coerce')
                df = df.sort_values(by='dateTime', ascending=False)

            if df.empty:
                self.output_content = f"[info]No trades found for {symbol}[/]"
                return

            # Partition DataFrames
            # stock_df: putCall is not 'C' or 'P'
            # options_df: putCall is 'C' or 'P'
            stock_df = df[~df['putCall'].isin(['C', 'P'])]
            options_df = df[df['putCall'].isin(['C', 'P'])]
            
            # Further partition options into open and closing trades
            open_options_df = options_df[options_df['openCloseIndicator'] == 'O']
            closing_options_df = options_df[options_df['openCloseIndicator'] == 'C']

            # Calculate Summaries (using original partitions for backward compatibility)
            call_df = df[df['putCall'] == 'C']
            put_df = df[df['putCall'] == 'P']
            
            stock_rem_qty_sum = stock_df['remaining_qty'].sum() if not stock_df.empty else 0.0
            call_rem_qty_sum = call_df['remaining_qty'].sum() if not call_df.empty else 0.0
            put_rem_qty_sum = put_df['remaining_qty'].sum() if not put_df.empty else 0.0

            stock_pnl_sum = stock_df['realized_pnl'].sum() if not stock_df.empty else 0.0
            call_pnl_sum = call_df['realized_pnl'].sum() if not call_df.empty else 0.0
            put_pnl_sum = put_df['realized_pnl'].sum() if not put_df.empty else 0.0

            # Book Price Calculation
            # sum(stock_df.credit) / sum(stock_df.remaining_qty)
            stock_credit_sum = stock_df['credit'].sum() if not stock_df.empty else 0.0
            
            if stock_rem_qty_sum != 0:
                book_price = stock_credit_sum / stock_rem_qty_sum
            else:
                book_price = 0.0

            # Create Summary Table
            summary_table = Table(title=f"Position Summary: {symbol}", expand=False, row_styles=["", "on #1d2021"])
            summary_table.add_column("Symbol", style="bold yellow")
            summary_table.add_column("Book Price", justify="right")
            summary_table.add_column("Stk Rem Qty", justify="right", style="magenta")
            summary_table.add_column("Call Rem Qty", justify="right", style="magenta")
            summary_table.add_column("Put Rem Qty", justify="right", style="magenta")
            summary_table.add_column("Stk PnL", justify="right", style="bold red")
            summary_table.add_column("Call PnL", justify="right", style="bold red")
            summary_table.add_column("Put PnL", justify="right", style="bold red")

            summary_table.add_row(
                symbol,
                f"{book_price:.2f}",
                f"{stock_rem_qty_sum:.0f}",
                f"{call_rem_qty_sum:.0f}",
                f"{put_rem_qty_sum:.0f}",
                f"{stock_pnl_sum:.2f}",
                f"{call_pnl_sum:.2f}",
                f"{put_pnl_sum:.2f}"
            )

            self.current_symbol = symbol
            self.position_map = {}
            row_idx = 1

            # Helper function to create a detail table
            def create_detail_table(title):
                tbl = Table(title=title, expand=True)
                tbl.add_column("#", justify="right", style="cyan")
                tbl.add_column("Date", style="cyan")
                tbl.add_column("Desc")
                tbl.add_column("P/C", justify="center")
                tbl.add_column("Qty", justify="right", style="magenta")
                tbl.add_column("Price", justify="right", style="green")
                tbl.add_column("Comm", justify="right")
                tbl.add_column("O/C", justify="center")
                tbl.add_column("Realized PnL", justify="right")
                tbl.add_column("Remaining Qty", justify="right", style="blue")
                tbl.add_column("Credit", justify="right", style="blue")
                tbl.add_column("Delta", justify="right", style="yellow")
                tbl.add_column("Und Price", justify="right", style="yellow")
                return tbl

            # Helper function to add rows to a table
            def add_rows_to_table(tbl, data_df, apply_dim_style=False):
                nonlocal row_idx
                for _, row in data_df.iterrows():
                    # Format date: 2025-12-25 14:50
                    date_str = row['dateTime'].strftime('%Y-%m-%d %H:%M') if pd.notnull(row['dateTime']) else ""

                    # Store mapping
                    self.position_map[row_idx] = row['tradeID']

                    # Determine row style: dim if remaining_qty == 0 and apply_dim_style is True
                    rem_qty = row.get('remaining_qty', 0.0)
                    row_style = "dim italic" if apply_dim_style and rem_qty == 0 else None

                    # Format realized PnL with conditional color
                    realized_pnl = row.get('realized_pnl', 0.0)
                    if realized_pnl > 0:
                        pnl_str = f"[neutral_blue]{realized_pnl:.2f}[/neutral_blue]"
                    elif realized_pnl < 0:
                        pnl_str = f"[bright_red]{realized_pnl:.2f}[/bright_red]"
                    else:
                        pnl_str = ""

                    tbl.add_row(
                        str(row_idx),
                        date_str,
                        str(row['description']),
                        str(row['putCall']),
                        f"{row['quantity']:.0f}" if pd.notnull(row['quantity']) else "",
                        f"{row['tradePrice']:.2f}" if pd.notnull(row['tradePrice']) else "",
                        f"{row['ibCommission']:.2f}" if pd.notnull(row['ibCommission']) else "",
                        str(row['openCloseIndicator']),
                        pnl_str,
                        f"{rem_qty:.0f}" if rem_qty != 0 else "",
                        f"{row.get('credit', 0.0):.2f}" if row.get('credit', 0) != 0 else "",
                        f"{row.get('delta', 0.0):.4f}" if pd.notnull(row.get('delta')) else "",
                        f"{row.get('und_price', 0.0):.2f}" if pd.notnull(row.get('und_price')) else "",
                        style=row_style
                    )
                    row_idx += 1

            # Build the tables list
            tables = [summary_table]

            # Table 1: Open Options Trades (P/C with O/C = 'O')
            if not open_options_df.empty:
                open_options_table = create_detail_table(f"Open Options: {symbol}")
                add_rows_to_table(open_options_table, open_options_df, apply_dim_style=True)
                tables.append(open_options_table)

            # Table 2: Closing Options Trades (P/C with O/C = 'C')
            if not closing_options_df.empty:
                closing_options_table = create_detail_table(f"Closing Options: {symbol}")
                add_rows_to_table(closing_options_table, closing_options_df, apply_dim_style=False)
                tables.append(closing_options_table)

            # Table 3: Stock Trades (not P/C)
            if not stock_df.empty:
                stock_table = create_detail_table(f"Stock Trades: {symbol}")
                add_rows_to_table(stock_table, stock_df, apply_dim_style=True)
                tables.append(stock_table)
            
            self.output_content = Group(*tables)
        except Exception as e:
            self.output_content = f"[error]Error listing positions: {e}[/]"

    def edit_trade(self, idx):
        if idx not in self.position_map:
            self.output_content = f"[error]Invalid trade index: {idx}[/]"
            return

        trade_id = self.position_map[idx]
        
        # We need to find the current values to show (optional, but good UX)
        # But we can just ask for new values.
        
        self.app.console.print(f"[info]Editing trade #{idx} (ID: {trade_id})[/]")
        
        try:
            delta_str = self.app.console.input("[prompt]Enter Delta (float): [/]")
            und_price_str = self.app.console.input("[prompt]Enter Und Price (float): [/]")
            
            updates = {}
            if delta_str.strip():
                updates['delta'] = float(delta_str)
            if und_price_str.strip():
                updates['und_price'] = float(und_price_str)
                
            if updates:
                if ibkr_db.update_trade_fields(trade_id, updates):
                    self.app.console.print("[info]Trade updated successfully.[/]")
                    self.load_trades() # Reload DF
                    if self.current_symbol:
                        self.list_position(self.current_symbol) # Refresh view
                    else:
                        self.output_content = "Trade updated."
                else:
                    self.output_content = "[error]Failed to update trade.[/]"
            else:
                 self.output_content = "[info]No changes made.[/]"

        except ValueError:
            self.output_content = "[error]Invalid input (expected float).[/]"
        except Exception as e:
            self.output_content = f"[error]Error updating trade: {e}[/]"

    def debug(self):
        # Direct print to allow terminal scrolling
        self.app.console.clear()
        groups = self.trades_df.groupby('underlyingSymbol')
        for name, group in groups:
            print(name)
            print(group)
            print("\n")
        print("-----------\n")
        print(self.trades_df.to_string())
        # self.app.console.print(self.trades_df.to_string())
        
        # Skip the next render cycle in main loop to prevent clearing the screen
        self.app.skip_render = True

    def list_all_trades(self):
        try:
            if self.trades_df.empty:
                self.output_content = "[info]No trades loaded.[/]"
                return

            table = Table(title="All Trades", expand=True)
            table.add_column("Date", style="cyan")
            table.add_column("Symbol", style="bold yellow")
            table.add_column("Desc")
            table.add_column("Qty", justify="right", style="magenta")
            table.add_column("Price", justify="right", style="green")
            table.add_column("Comm", justify="right")
            table.add_column("O/C", justify="center")
            table.add_column("PnL", justify="right", style="bold red")
            table.add_column("Rem Qty", justify="right", style="blue")
            table.add_column("Delta", justify="right", style="yellow")
            table.add_column("Und Price", justify="right", style="yellow")

            for _, row in self.trades_df.iterrows():
                pnl = row.get('realized_pnl', 0.0)
                rem_qty = row.get('remaining_qty', 0.0)

                table.add_row(
                    str(row['dateTime']),
                    str(row['symbol']),
                    str(row['description']),
                    f"{row['quantity']:.0f}" if pd.notnull(row['quantity']) else "",
                    f"{row['tradePrice']:.2f}" if pd.notnull(row['tradePrice']) else "",
                    f"{row['ibCommission']:.2f}" if pd.notnull(row['ibCommission']) else "",
                    str(row['openCloseIndicator']),
                    f"{pnl:.2f}" if pnl != 0 else "",
                    f"{rem_qty:.0f}" if rem_qty != 0 else "",
                    f"{row.get('delta', 0.0):.4f}" if pd.notnull(row.get('delta')) else "",
                    f"{row.get('und_price', 0.0):.2f}" if pd.notnull(row.get('und_price')) else ""
                )

            # Direct print to allow terminal scrolling
            self.app.console.clear()
            self.app.console.print(table)
            
            # Skip the next render cycle in main loop to prevent clearing the screen
            self.app.skip_render = True

            # We do NOT set output_content here because it won't be displayed
            # (since render is skipped and the loop goes straight to input)
        except Exception as e:
            self.output_content = f"[error]Error listing trades: {e}[/]"

    def stats_daily(self):
        try:
            if self.trades_df.empty:
                self.output_content = "[info]No trades to analyze.[/]"
                return

            # Create a working copy
            df = self.trades_df.copy()
            df['dateTime'] = pd.to_datetime(df['dateTime'])
            
            # Extract date (normalize to midnight)
            df['date_only'] = df['dateTime'].dt.normalize()

            # Group by date and sum PnL
            daily_stats = df.groupby('date_only')['realized_pnl'].sum()

            if daily_stats.empty:
                 self.output_content = "[info]No realized PnL found.[/]"
                 return

            # Create full date range
            min_date = daily_stats.index.min()
            max_date = daily_stats.index.max()
            
            # Generate all calendar days to check for weekends with trades
            all_days = pd.date_range(start=min_date, end=max_date, freq='D')
            
            # Reindex to include all days, filling missing with 0
            daily_stats = daily_stats.reindex(all_days, fill_value=0.0)

            # Filter: Keep if Weekday (Mon=0, Sun=6) < 5 OR PnL != 0
            # This keeps all Mon-Fri (even if 0) and any Sat/Sun with non-zero PnL
            mask = (daily_stats.index.dayofweek < 5) | (daily_stats != 0)
            daily_stats = daily_stats[mask]

            # Prepare table
            table = Table(title="Daily Stats (PnL)", expand=False)
            table.add_column("Date", style="cyan")
            table.add_column("Day", style="yellow")
            table.add_column("Realized PnL", justify="right")

            total_pnl = 0.0

            for date, pnl in daily_stats.items():
                total_pnl += pnl
                day_name = date.strftime("%A")
                date_str = date.strftime("%Y-%m-%d")
                
                style = "blue" if pnl > 0 else "orange1" if pnl < 0 else "dim"
                pnl_str = f"{pnl:,.2f}" if pnl != 0 else "-"
                
                table.add_row(date_str, day_name, f"[{style}]{pnl_str}[/{style}]")

            table.add_section()
            style = "bold blue" if total_pnl > 0 else "bold orange1" if total_pnl < 0 else "white"
            table.add_row("TOTAL", "", f"[{style}]{total_pnl:,.2f}[/{style}]", style="bold")

            self.output_content = table
        except Exception as e:
            self.output_content = f"[error]Error calculating stats: {e}[/]"

    def stats_weekly(self):
        try:
            if self.trades_df.empty:
                 self.output_content = "[info]No trades to analyze.[/]"
                 return

            # Create working copy
            df = self.trades_df.copy()
            df['dateTime'] = pd.to_datetime(df['dateTime'])
            
            # Set index for resampling
            df.set_index('dateTime', inplace=True)
            
            # Resample by Week Ending Friday (W-FRI)
            weekly_stats = df['realized_pnl'].resample('W-FRI').sum()

            if weekly_stats.empty:
                self.output_content = "[info]No realized PnL found.[/]"
                return
            
            # Note: resample automatically fills the range with bins, but if there are gaps
            # at the beginning or end relative to a "clean" week, it handles it.
            # It also fills gaps with 0 if we sum() on empty bins.
            
            # Prepare table
            table = Table(title="Weekly Stats (PnL - Ending Friday)", expand=False)
            table.add_column("Week Ending", style="cyan")
            table.add_column("Realized PnL", justify="right")
            
            total_pnl = 0.0
            
            for date, pnl in weekly_stats.items():
                total_pnl += pnl
                date_str = date.strftime("%Y-%m-%d")
                
                # Highlight if non-zero
                style = "bold blue" if pnl > 0 else "bold orange1" if pnl < 0 else "dim"
                pnl_str = f"{pnl:,.2f}" if pnl != 0 else "-"
                
                table.add_row(date_str, f"[{style}]{pnl_str}[/{style}]")
                
            table.add_section()
            style = "bold blue" if total_pnl > 0 else "bold orange1" if total_pnl < 0 else "white"
            table.add_row("TOTAL", f"[{style}]{total_pnl:,.2f}[/{style}]", style="bold")
            
            self.output_content = table

        except Exception as e:
            self.output_content = f"[error]Error calculating weekly stats: {e}[/]"

    def list_all_positions(self, order_by='mtm', ascending=False):
        try:
            if self.trades_df.empty:
                self.output_content = "[info]No trades loaded.[/]"
                return

            # Group by underlyingSymbol
            # We assume underlyingSymbol is present. If NaN, it might be skipped.
            # Usually IBKR report provides it.
            groups = self.trades_df.groupby('underlyingSymbol')
            
            table = Table(title="All Positions", expand=False, row_styles=["", "on #1d2021"])
            table.add_column("Symbol", style="neutral_yellow")
            table.add_column("Value", justify="right", style="neutral_yellow")
            table.add_column("MTM", justify="right", style="neutral_blue")
            table.add_column("MTM %", justify="right")
            table.add_column("Tgt %", justify="right", style="neutral_aqua")
            table.add_column("Unrlzd PnL", justify="right")
            table.add_column("Stock", justify="right", style="neutral_purple")
            table.add_column("Call", justify="right", style="neutral_purple")
            table.add_column("Put", justify="right", style="neutral_purple")
            table.add_column("Stock Rlzd PnL", justify="right")
            table.add_column("Call Rlzd PnL", justify="right")
            table.add_column("Put Rlzd PnL", justify="right")

            data_rows = []

            for symbol, group in groups:
                 # Partition DataFrames
                 stock_df = group[~group['putCall'].isin(['C', 'P'])]
                 call_df = group[group['putCall'] == 'C']
                 put_df = group[group['putCall'] == 'P']

                 value = stock_df['credit'].sum() * -1
                 mtm = stock_df['mtm_value'].sum()
                 unrlzd_pnl = mtm - value
                 
                 s_qty = stock_df['remaining_qty'].sum()
                 c_qty = call_df['remaining_qty'].sum()
                 p_qty = put_df['remaining_qty'].sum()
                 
                 s_pnl = stock_df['realized_pnl'].sum()
                 c_pnl = call_df['realized_pnl'].sum()
                 p_pnl = put_df['realized_pnl'].sum()
                 
                 # Only add row if there is something interesting
                 if any(x != 0 for x in [value, mtm, s_qty, c_qty, p_qty, s_pnl, c_pnl, p_pnl]):
                     data_rows.append({
                        'symbol': symbol,
                        'value': value,
                        'mtm': mtm,
                        'unrlzd_pnl': unrlzd_pnl,
                        's_qty': s_qty,
                        'c_qty': c_qty,
                        'p_qty': p_qty,
                        's_pnl': s_pnl,
                        'c_pnl': c_pnl,
                        'p_pnl': p_pnl,
                        'target_pct': self.target_percent.get(symbol, 0.0)
                     })

            # Sort
            if order_by == 'value':
                data_rows.sort(key=lambda x: x['value'], reverse=not ascending)
            elif order_by == 'mtm':
                data_rows.sort(key=lambda x: x['mtm'], reverse=not ascending)
            elif order_by == 'symbol':
                data_rows.sort(key=lambda x: x['symbol'], reverse=not ascending)
            elif order_by == 's_qty':
                data_rows.sort(key=lambda x: x['s_qty'], reverse=not ascending)

            # Calculate totals
            total_value = sum(row['value'] for row in data_rows)
            total_mtm = sum(row['mtm'] for row in data_rows)
            total_unrlzd_pnl = sum(row['unrlzd_pnl'] for row in data_rows)
            total_s_qty = sum(row['s_qty'] for row in data_rows)
            total_c_qty = sum(row['c_qty'] for row in data_rows)
            total_p_qty = sum(row['p_qty'] for row in data_rows)
            total_s_pnl = sum(row['s_pnl'] for row in data_rows)
            total_c_pnl = sum(row['c_pnl'] for row in data_rows)
            total_p_pnl = sum(row['p_pnl'] for row in data_rows)
            total_target_pct = sum(row['target_pct'] for row in data_rows)

            def fmt_pnl(val):
                if val == 0: return ""
                if val > 0: return f"[neutral_blue]{val:,.2f}[/neutral_blue]"
                return f"[bright_red]{val:,.2f}[/bright_red]"

            for row in data_rows:
                # Calculate MTM % and determine color
                mtm_pct = row['mtm'] / total_mtm * 100 if total_mtm != 0 and row['mtm'] != 0 else 0
                target_pct = row['target_pct']
                
                # Determine MTM % color
                if target_pct != 0 and (mtm_pct <= 0.6 * target_pct or mtm_pct >= 1.4 * target_pct):
                    mtm_pct_color = "bright_red"
                elif target_pct != 0 and (mtm_pct <= 0.8 * target_pct or mtm_pct >= 1.2 * target_pct):
                    mtm_pct_color = "neutral_red"
                else:
                    mtm_pct_color = "neutral_blue"
                
                mtm_pct_str = f"[{mtm_pct_color}]{mtm_pct:.2f}%[/{mtm_pct_color}]" if mtm_pct != 0 else ""
                
                table.add_row(
                    str(row['symbol']),
                    f"{row['value']:,.2f}" if row['value'] != 0 else "",
                    f"{row['mtm']:,.2f}" if row['mtm'] != 0 else "",
                    mtm_pct_str,
                    f"{row['target_pct']:.2f}%" if row['target_pct'] != 0 else "",
                    fmt_pnl(row['unrlzd_pnl']),
                    f"{row['s_qty']:.0f}" if row['s_qty'] != 0 else "",
                    f"{row['c_qty']:.0f}" if row['c_qty'] != 0 else "",
                    f"{row['p_qty']:.0f}" if row['p_qty'] != 0 else "",
                    fmt_pnl(row['s_pnl']),
                    fmt_pnl(row['c_pnl']),
                    fmt_pnl(row['p_pnl'])
                )
            
            # Add totals row
            table.add_section()
            table.add_row(
                "TOTAL",
                f"{total_value:,.2f}",
                f"{total_mtm:,.2f}",
                f"{total_mtm / total_mtm * 100:.2f}%" if total_mtm != 0 else "",
                f"{total_target_pct:.2f}%" if total_target_pct != 0 else "",
                fmt_pnl(total_unrlzd_pnl),
                f"{total_s_qty:.0f}",
                f"{total_c_qty:.0f}",
                f"{total_p_qty:.0f}",
                fmt_pnl(total_s_pnl),
                fmt_pnl(total_c_pnl),
                fmt_pnl(total_p_pnl),
                style="bold"
            )
            
            self.output_content = table
            
        except Exception as e:
            self.output_content = f"[error]Error listing all positions: {e}[/]"

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][IBKR] >> [/]"
