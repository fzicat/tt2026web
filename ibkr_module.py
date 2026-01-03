import pandas as pd
import requests
import time
import xml.etree.ElementTree as ET
from rich.table import Table
from rich.console import Group
from rich.panel import Panel
import config
import db_handler
from base_module import Module

class IBKRModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.trades_df = pd.DataFrame()
        self.output_content = "IBKR Module Active\nType 'help' or 'h' for a list of commands."
        self.load_trades()

    def load_trades(self):
        self.trades_df = db_handler.fetch_all_trades_as_df()
        if not self.trades_df.empty:
            self.calculate_pnl()
            # Calculate Credit: remaining_qty * price * multiplier * -1
            m = self.trades_df['multiplier'].fillna(1.0)
            self.trades_df['credit'] = self.trades_df['remaining_qty'] * self.trades_df['tradePrice'] * m * -1
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
    
    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            # Local import to avoid circular dependency
            from home_module import HomeModule
            self.app.switch_module(HomeModule(self.app))
        elif cmd in ['h', 'help']:
            self.output_content = "IBKR commands:\n - import (i): Import daily trades\n - import w (i w): Import weekly trades\n - list (l): List all positions\n - trades (t): List all trades\n - reload (r): Reload trades from DB\n - p <symbol>: List positions for a symbol\n - quit (q): Return to main menu\n - help (h): Show this message"
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
        elif cmd in ['l', 'list']:
            self.list_all_positions()
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
                
                if db_handler.save_trade(row):
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
                df = df.sort_values(by='dateTime', ascending=True)

            if df.empty:
                self.output_content = f"[info]No trades found for {symbol}[/]"
                return

            # Partition DataFrames
            # stock_df: putCall is not 'C' or 'P'
            # call_df: putCall is 'C'
            # put_df: putCall is 'P'
            stock_df = df[~df['putCall'].isin(['C', 'P'])]
            call_df = df[df['putCall'] == 'C']
            put_df = df[df['putCall'] == 'P']

            # Calculate Summaries
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

            # Detail Table (Existing)
            table = Table(title=f"Positions: {symbol}", expand=True, row_styles=["", "on #1d2021"])
            table.add_column("Date", style="cyan")
            table.add_column("Desc")
            table.add_column("P/C", justify="center")
            table.add_column("Qty", justify="right", style="magenta")
            table.add_column("Price", justify="right", style="green")
            table.add_column("Comm", justify="right")
            table.add_column("O/C", justify="center")
            table.add_column("Realized PnL", justify="right", style="bold red")
            table.add_column("Remaining Qty", justify="right", style="blue")
            table.add_column("Credit", justify="right", style="blue")

            for _, row in df.iterrows():
                # Format date: 2025-12-25 14:50
                date_str = row['dateTime'].strftime('%Y-%m-%d %H:%M') if pd.notnull(row['dateTime']) else ""

                table.add_row(
                    date_str,
                    str(row['description']),
                    str(row['putCall']),
                    f"{row['quantity']:.0f}" if pd.notnull(row['quantity']) else "",
                    f"{row['tradePrice']:.2f}" if pd.notnull(row['tradePrice']) else "",
                    f"{row['ibCommission']:.2f}" if pd.notnull(row['ibCommission']) else "",
                    str(row['openCloseIndicator']),
                    f"{row.get('realized_pnl', 0.0):.2f}" if row.get('realized_pnl', 0) != 0 else "",
                    f"{row.get('remaining_qty', 0.0):.0f}" if row.get('remaining_qty', 0) != 0 else "",
                    f"{row.get('credit', 0.0):.2f}" if row.get('credit', 0) != 0 else ""
                )
            
            self.output_content = Group(summary_table, table)
        except Exception as e:
            self.output_content = f"[error]Error listing positions: {e}[/]"

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
                    f"{rem_qty:.0f}" if rem_qty != 0 else ""
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

    def list_all_positions(self):
        try:
            if self.trades_df.empty:
                self.output_content = "[info]No trades loaded.[/]"
                return

            # Group by underlyingSymbol
            # We assume underlyingSymbol is present. If NaN, it might be skipped.
            # Usually IBKR report provides it.
            groups = self.trades_df.groupby('underlyingSymbol')
            
            table = Table(title="All Positions", expand=False, row_styles=["", "on #1d2021"])
            table.add_column("Symbol", style="bold yellow")
            table.add_column("Call (Qty)", justify="right", style="magenta")
            table.add_column("Stock (Qty)", justify="right", style="magenta")
            table.add_column("Put (Qty)", justify="right", style="magenta")
            table.add_column("Call Realized PnL", justify="right", style="bold red")
            table.add_column("Stock Realized PnL", justify="right", style="bold red")
            table.add_column("Put Realized PnL", justify="right", style="bold red")

            for symbol, group in groups:
                 # Partition DataFrames
                 stock_df = group[~group['putCall'].isin(['C', 'P'])]
                 call_df = group[group['putCall'] == 'C']
                 put_df = group[group['putCall'] == 'P']
                 
                 s_qty = stock_df['remaining_qty'].sum()
                 c_qty = call_df['remaining_qty'].sum()
                 p_qty = put_df['remaining_qty'].sum()
                 
                 s_pnl = stock_df['realized_pnl'].sum()
                 c_pnl = call_df['realized_pnl'].sum()
                 p_pnl = put_df['realized_pnl'].sum()
                 
                 # Only add row if there is something interesting
                 if any(x != 0 for x in [s_qty, c_qty, p_qty, s_pnl, c_pnl, p_pnl]):
                     table.add_row(
                        str(symbol),
                        f"{c_qty:.0f}" if c_qty != 0 else "",
                        f"{s_qty:.0f}" if s_qty != 0 else "",
                        f"{p_qty:.0f}" if p_qty != 0 else "",
                        f"{c_pnl:.2f}" if c_pnl != 0 else "",
                        f"{s_pnl:.2f}" if s_pnl != 0 else "",
                        f"{p_pnl:.2f}" if p_pnl != 0 else ""
                     )
            
            self.output_content = table
        except Exception as e:
            self.output_content = f"[error]Error listing all positions: {e}[/]"

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][IBKR]>> [/]"
