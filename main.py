import pandas as pd
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from rich.table import Table
import sys
import os
import requests
import time
import xml.etree.ElementTree as ET
import config
import db_handler

class Module:
    def __init__(self, app):
        self.app = app

    def handle_command(self, command):
        raise NotImplementedError

    def get_output(self):
        raise NotImplementedError

    def get_prompt(self):
        return "[prompt]>> [/]"

class MainModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.output_content = "Welcome to TradeTools v3\nType 'help' or 'h' for a list of commands."

    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            self.app.quit()
        elif cmd in ['h', 'help']:
            self.output_content = "Available commands:\n - ibkr (i): Switch to IBKR module\n - quit (q): Exit the application\n - help (h): Show this message"
        elif cmd in ['i', 'ibkr']:
            self.app.switch_module(IBKRModule(self.app))
        elif cmd == "":
            pass
        else:
            self.output_content = f"Unknown command: {command}\nType 'help' for valid commands."

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][MAIN]>> [/]"

class IBKRModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.output_content = "IBKR Module Active\nType 'help' or 'h' for a list of commands."

    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            self.app.switch_module(MainModule(self.app))
        elif cmd in ['h', 'help']:
            self.output_content = "IBKR commands:\n - import (i): Import daily trades\n - import w (i w): Import weekly trades\n - p <symbol>: List positions for a symbol\n - quit (q): Return to main menu\n - help (h): Show this message"
        elif cmd.startswith('p '):
            parts = command.split()
            if len(parts) >= 2:
                symbol = parts[1].upper()
                self.list_positions(symbol)
            else:
                self.output_content = "[error]Usage: p <symbol>[/]"
        elif cmd in ['i', 'import']:
            self.import_trades(config.QUERY_ID_DAILY, "Daily")
        elif cmd in ['i w', 'import w', 'import weekly']:
            self.import_trades(config.QUERY_ID_WEEKLY, "Weekly")
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
                    # Sometimes they return XML saying 'Warn' or 'processing'
                    # But usually if 200 and valid XML with Trade, good.
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

        except Exception as e:
            self.output_content = f"[error]Error parsing XML or saving to DB: {e}[/]"

    def list_positions(self, symbol):
        try:
            df = db_handler.get_trades_by_symbol(symbol)
            if df.empty:
                self.output_content = f"[info]No trades found for {symbol}[/]"
                return

            table = Table(title=f"Positions: {symbol}", expand=True)
            table.add_column("Date", style="cyan")
            table.add_column("Desc")
            table.add_column("Qty", justify="right", style="magenta")
            table.add_column("Price", justify="right", style="green")
            table.add_column("Comm", justify="right")
            table.add_column("O/C", justify="center")

            for _, row in df.iterrows():
                table.add_row(
                    str(row['dateTime']),
                    str(row['description']),
                    f"{row['quantity']:.0f}" if pd.notnull(row['quantity']) else "",
                    f"{row['tradePrice']:.2f}" if pd.notnull(row['tradePrice']) else "",
                    f"{row['ibCommission']:.2f}" if pd.notnull(row['ibCommission']) else "",
                    str(row['openCloseIndicator'])
                )
            
            self.output_content = table
        except Exception as e:
            self.output_content = f"[error]Error listing positions: {e}[/]"

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][IBKR]>> [/]"

class TradeToolsApp:
    def __init__(self):
        # Gruvbox theme definition
        gruvbox_theme = Theme({
            "base": "#ebdbb2 on #282828",
            "header.text": "bold #d79921",
            "header.bg": "#3c3836",
            "panel.border": "#a89984",
            "prompt": "bold #fabd2f",
            "error": "bold #cc241d",
            "info": "#83a598"
        })
        self.console = Console(theme=gruvbox_theme, style="base")
        self.running = True
        self.active_module = MainModule(self)

    def switch_module(self, module):
        self.active_module = module

    def get_layout(self):
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body")
        )
        
        # Header
        header_text = Text("TradeTools v3", justify="center", style="header.text")
        layout["header"].update(Panel(header_text, style="on #3c3836", border_style="panel.border"))
        
        # Body
        # Note: self.active_module.get_output() returns a string. 
        # If it contains markup, Panel(Text(...)) might not render it as markup by default unless style is applied, 
        # but Text() handles basic ANSI or we can pass markup=True to Panel or Text.
        # However, rich.Text doesn't parse markup by default? 
        # Better to pass string directly to Panel if it has markup, or use Text.from_markup()
        # The original code used Text(..., style=...)
        # I will change it to Text.from_markup to support colors in output
        
        output_data = self.active_module.get_output()
        # Handle both string (markup) and Renderable (like Table)
        if isinstance(output_data, str):
            content = Text.from_markup(output_data)
        else:
            content = output_data if output_data else ""

        body_panel = Panel(
            content,
            title="Output",
            border_style="panel.border",
            style="on #282828"
        )
        layout["body"].update(body_panel)
        
        return layout

    def run(self):
        db_handler.init_db()
        
        while self.running:
            self.console.clear()
            layout = self.get_layout()
            
            # Print the layout taking up most of the screen
            # Leave 1 line for the prompt
            self.console.print(layout, height=self.console.height - 2)
            
            try:
                # Prompt loop
                prompt = self.active_module.get_prompt()
                command = self.console.input(prompt)
                self.process_command(command)
            except KeyboardInterrupt:
                self.quit()

    def process_command(self, command):
        self.active_module.handle_command(command)

    def quit(self):
        self.running = False
        self.console.print("[error]Goodbye![/]")

if __name__ == "__main__":
    app = TradeToolsApp()
    app.run()
