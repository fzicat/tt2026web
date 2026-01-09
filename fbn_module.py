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

        self.accounts = [
            {'name': 'MARGE', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'REER', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'CRI', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'REEE', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'CELI', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'MPM', 'portfolio': 'Personnel', 'currency': 'CAD'},
            {'name': 'GFZ CAD', 'portfolio': 'Gestion FZ', 'currency': 'CAD'},
            {'name': 'GFZ USD', 'portfolio': 'Gestion FZ', 'currency': 'USD'},
        ]

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
        elif cmd in ['lm', 'list monthly']:
            self.list_monthly()
        elif cmd in ['ly', 'list yearly']:
            self.list_yearly()
        elif cmd in ['a', 'add', 'e', 'edit']:
            self.add_monthly_data()
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

    def add_monthly_data(self):
        self.app.console.clear()
        self.app.console.print("[bold cyan]--- Add/Edit Monthly Data ---[/]")
        
        # 1. Date Selection
        target_date = self.get_target_date()
        if not target_date:
            self.output_content = "[info]Operation cancelled.[/]"
            return

        self.app.console.print(f"[info]Selected Date: {target_date.strftime('%Y-%m-%d')}[/]")

        # 2. Account Loop replaced by Menu Selection
        while True:
            self.app.console.print("\n[bold]Select Account to Edit:[/]")
            for idx, acc in enumerate(self.accounts, 1):
                self.app.console.print(f" {idx}. {acc['name']} ([dim]{acc['currency']}[/dim])")
            
            choice = self.app.console.input("\n[prompt]Select account # (or 'q' to finish) >> [/]").lower()
            
            if choice in ['q', 'quit']:
                break
            
            try:
                idx = int(choice)
                if 1 <= idx <= len(self.accounts):
                    account_info = self.accounts[idx-1]
                    self.process_account_entry(account_info, target_date)
                else:
                    self.app.console.print("[error]Invalid selection.[/]")
            except ValueError:
                self.app.console.print("[error]Invalid input.[/]")
        
        # Refresh Data
        self.load_fbn_data()
        self.output_content = "[success]Data entry completed and reloaded.[/]"

    def get_target_date(self):
        from datetime import datetime, timedelta
        import calendar

        # Default: Last day of previous month
        today = datetime.now()
        first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month = first - timedelta(days=1)
        default_date_str = last_month.strftime("%Y-%m-%d") # Use full date for internal consistency, user thinks in month/year

        date_input = self.app.console.input(f"[prompt]Enter date (YYYY-MM-DD) or Month/Year (MM/YYYY) [[dim]{default_date_str}[/dim]] >> [/]")
        
        if not date_input:
            return last_month
            
        try:
             # Try YYYY-MM-DD
            return datetime.strptime(date_input, "%Y-%m-%d")
        except ValueError:
            pass
            
        try:
            # Try MM/YYYY -> convert to last day of that month
            month, year = map(int, date_input.split('/'))
            last_day = calendar.monthrange(year, month)[1]
            return datetime(year, month, last_day)
        except ValueError:
            self.app.console.print("[error]Invalid date format.[/]")
            return None

    def process_account_entry(self, account_info, date):
        acc_name = account_info['name']
        currency = account_info['currency']
        
        self.app.console.print(f"\n[bold magenta]--- Account: {acc_name} ({currency}) ---[/]")
        
        # Get existing row if any
        existing_row = pd.Series()
        if not self.df.empty:
            mask = (self.df['date'] == date) & (self.df['account'] == acc_name)
            if mask.any():
                existing_row = self.df[mask].iloc[0]
                
        # 2. Print current asset value if available
        current_asset = existing_row.get('asset', 'N/A')
        if current_asset != 'N/A':
             self.app.console.print(f"Current Asset Value: [bold]{current_asset:,.2f}[/]")
        else:
             self.app.console.print(f"Current Asset Value: [dim]N/A[/]")

        # 3. Values Input
        fields = ['investment', 'deposit', 'interest', 'dividend', 'distribution', 'tax', 'fee', 'other', 'cash', 'asset']
        values = {}
        
        for field in fields:
            default = existing_row.get(field, 0.0) if not existing_row.empty else 0.0
            val_input = self.app.console.input(f"{field.capitalize()} [[dim]{default}[/dim]] >> ")
            try:
                values[field] = float(val_input) if val_input else float(default)
            except ValueError:
                self.app.console.print(f"[warning]Invalid number, using default: {default}[/]")
                values[field] = float(default)

        if acc_name == 'GFZ USD':
            rate_default = existing_row.get('rate', 1.0) if not existing_row.empty else 1.0
            rate_input = self.app.console.input(f"Rate [[dim]{rate_default}[/dim]] >> ")
            try:
                values['rate'] = float(rate_input) if rate_input else float(rate_default)
            except ValueError:
                 values['rate'] = float(rate_default)
        else:
            values['rate'] = 1.0 # Default for CAD

        # 4. Validation
        variation_encaisse = sum([values[k] for k in ['investment', 'deposit', 'interest', 'dividend', 'distribution', 'tax', 'fee', 'other']])
        total_placements = values['asset'] - values['cash']
        
        self.app.console.print("\n[bold]Validation:[/]")
        self.app.console.print(f"Variation Encaisse: [cyan]{variation_encaisse:,.2f}[/]")
        self.app.console.print(f"Total Placements:   [cyan]{total_placements:,.2f}[/]")
        
        confirm = self.app.console.input("[prompt]Confirm these values? (Y/n/r[retry]) >> [/]").lower()
        
        if confirm == 'n':
            self.app.console.print("[info]Skipping this account.[/]")
            return
        elif confirm == 'r':
            return self.process_account_entry(account_info, date) # Recursive retry
            
        # 5. Insert or Replace
        entry_data = {
            'date': date.strftime("%Y-%m-%d"),
            'account': acc_name,
            'portfolio': account_info['portfolio'],
            'currency': currency,
            **values
        }
        
        fbn_db_handler.save_account_entry(entry_data)
        self.app.console.print(f"[success]Saved entry for {acc_name}[/]")

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][FBN] >> [/]"
