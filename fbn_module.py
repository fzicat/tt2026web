import pandas as pd
from rich.table import Table
from rich.console import Group, Console
from base_module import Module
import fbn_db_handler

class FBNModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.df = pd.DataFrame()
        self.monthly_df = pd.DataFrame()
        self.yearly_df = pd.DataFrame()
        self.output_content = "FBN Module Active\nType 'help' or 'h' for a list of commands."
        
        self.load_fbn_data()

    def load_fbn_data(self):
        self.df = fbn_db_handler.fetch_fbn_data()
        
        if not self.df.empty:
            # Ensure date is datetime
            self.df['date'] = pd.to_datetime(self.df['date'])

            # Apply Currency Conversion (USD -> CAD)
            # Multiply columns by rate where currency is 'USD'
            cols_to_convert = ['investment', 'deposit', 'asset', 'fee', 'dividend', 'interest', 'tax', 'other', 'cash', 'distribution']
            mask = self.df['currency'] == 'USD'
            
            for col in cols_to_convert:
                self.df.loc[mask, col] = self.df.loc[mask, col] * self.df.loc[mask, 'rate']
            
            # Group by date for monthly aggregation
            # We want to sum specific columns across all accounts/portfolios for the monthly view
            monthly_groups = self.df.groupby('date')
            
            agg_data = []
            for date, group in monthly_groups:
                deposit = group['deposit'].sum()
                asset = group['asset'].sum()
                fee = group['fee'].sum()
                
                agg_data.append({
                    'date': date,
                    'deposit': deposit,
                    'asset': asset,
                    'fee': fee
                })
            
            self.monthly_df = pd.DataFrame(agg_data)
            self.monthly_df = self.monthly_df.sort_values(by='date')
            
            # Calculate PnL and Pct
            # pnl = asset - deposit - prev_asset
            # pct = pnl / prev_asset
            
            self.monthly_df['prev_asset'] = self.monthly_df['asset'].shift(1).fillna(0.0)
            
            # First month logic: pnl = asset - deposit (assuming prev_asset is 0)
            # But usually first month starts from 0 or initial deposit. 
            # If prev_asset is 0, we can't divide by it for pct.
            
            self.monthly_df['pnl'] = self.monthly_df['asset'] - self.monthly_df['deposit'] - self.monthly_df['prev_asset']
            
            # Avoid division by zero
            self.monthly_df['pct'] = self.monthly_df.apply(
                lambda row: (row['pnl'] / row['prev_asset']) * 100 if row['prev_asset'] != 0 else 0.0, 
                axis=1
            )
            
            # Prepare Yearly Data
            temp_df = self.monthly_df.copy()
            temp_df['year'] = temp_df['date'].dt.year
            
            yearly_groups = temp_df.groupby('year')
            yearly_agg = []
            
            for year, group in yearly_groups:
                deposit = group['deposit'].sum()
                fee = group['fee'].sum()
                asset = group.iloc[-1]['asset']
                
                yearly_agg.append({
                    'year': year,
                    'deposit': deposit,
                    'asset': asset,
                    'fee': fee
                })
                
            self.yearly_df = pd.DataFrame(yearly_agg)
            if not self.yearly_df.empty:
                self.yearly_df = self.yearly_df.sort_values('year')
                self.yearly_df['prev_asset'] = self.yearly_df['asset'].shift(1).fillna(0.0)
                self.yearly_df['pnl'] = self.yearly_df['asset'] - self.yearly_df['deposit'] - self.yearly_df['prev_asset']
                self.yearly_df['pct'] = self.yearly_df.apply(
                    lambda row: (row['pnl'] / row['prev_asset']) * 100 if row['prev_asset'] != 0 else 0.0, 
                    axis=1
                )
            
        else:
            self.app.console.print("[error]No FBN data found.[/]")

    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            # Local import to avoid circular dependency
            from home_module import HomeModule
            self.app.switch_module(HomeModule(self.app))
        elif cmd in ['qq', 'quit quit']:
            self.app.quit()
        elif cmd in ['h', 'help']:
            self.output_content = '''FBN commands:
        - LM  | list monthly > List monthly stats
        - LY  | list yearly  > List yearly stats
        - Q   | quit         > Return to main menu
        - QQ  | quit quit    > Exit the application'''
        elif cmd in ['lm', 'list monthly']:
            self.list_monthly()
        elif cmd in ['ly', 'list yearly']:
            self.list_yearly()
        elif cmd == "":
            pass
        else:
            self.output_content = f"Unknown command: {command}\nType 'help' for valid commands."

    def list_monthly(self):
        try:
            if self.monthly_df.empty:
                self.output_content = "[info]No monthly data available.[/]"
                return

            table = Table(title="FBN Monthly Stats", expand=False)
            table.add_column("Date", style="cyan")
            table.add_column("Deposit", justify="right")
            table.add_column("Asset", justify="right", style="magenta")
            table.add_column("Fee", justify="right")
            table.add_column("PnL", justify="right")
            table.add_column("Pct", justify="right")

            for _, row in self.monthly_df.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                
                deposit = row['deposit']
                asset = row['asset']
                fee = row['fee']
                pnl = row['pnl']
                pct = row['pct']
                
                # Formatting
                pnl_style = "bold blue" if pnl > 0 else "bold orange1" if pnl < 0 else "dim"
                pct_style = "bold blue" if pct > 0 else "bold orange1" if pct < 0 else "dim"
                
                table.add_row(
                    date_str,
                    f"{deposit:,.2f}" if deposit != 0 else "-",
                    f"{asset:,.2f}",
                    f"{fee:,.2f}" if fee != 0 else "-",
                    f"[{pnl_style}]{pnl:,.2f}[/{pnl_style}]",
                    f"[{pct_style}]{pct:,.2f}%[/{pct_style}]"
                )

            # Direct print if needed, or return via output_content
            # ibkr_module often does direct print for lists, let's stick to output_content for now unless it's too long
            # If it's too long, main.py layout handles scrolling? No, rich layout doesn't scroll natively without a pager.
            # ibkr_module used `self.app.console.print(table)` and `skip_render=True` for long lists. 
            # Given 10 years of monthly data ~ 120 rows, it might be long.
            
            self.app.console.clear()
            self.app.console.print(table)
            self.app.skip_render = True
            
        except Exception as e:
            self.output_content = f"[error]Error listing monthly stats: {e}[/]"

    def list_yearly(self):
        try:
            if self.yearly_df.empty:
                self.output_content = "[info]No yearly data available.[/]"
                return

            table = Table(title="FBN Yearly Stats", expand=False)
            table.add_column("Year", style="cyan")
            table.add_column("Deposit", justify="right")
            table.add_column("Asset", justify="right", style="magenta")
            table.add_column("Fee", justify="right")
            table.add_column("PnL", justify="right")
            table.add_column("Pct", justify="right")

            for _, row in self.yearly_df.iterrows():
                year_str = str(row['year'])
                
                deposit = row['deposit']
                asset = row['asset']
                fee = row['fee']
                pnl = row['pnl']
                pct = row['pct']
                
                # Formatting
                pnl_style = "bold blue" if pnl > 0 else "bold orange1" if pnl < 0 else "dim"
                pct_style = "bold blue" if pct > 0 else "bold orange1" if pct < 0 else "dim"
                
                table.add_row(
                    year_str,
                    f"{deposit:,.2f}" if deposit != 0 else "-",
                    f"{asset:,.2f}",
                    f"{fee:,.2f}" if fee != 0 else "-",
                    f"[{pnl_style}]{pnl:,.2f}[/{pnl_style}]",
                    f"[{pct_style}]{pct:,.2f}%[/{pct_style}]"
                )
            
            self.app.console.clear()
            self.app.console.print(table)
            self.app.skip_render = True
            
        except Exception as e:
            self.output_content = f"[error]Error listing yearly stats: {e}[/]"

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][FBN] >> [/]"
