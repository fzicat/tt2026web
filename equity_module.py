import pandas as pd
from rich.table import Table
from base_module import Module
import equity_db_handler
from datetime import datetime

class EquityModule(Module):
    def __init__(self, app):
        super().__init__(app)
        self.equity_df = pd.DataFrame()
        self.output_content = "Equity Module Active\nType 'help' for commands."
        self.load_equity_data()

    def load_equity_data(self):
        self.equity_df = equity_db_handler.fetch_equity_data()
        if not self.equity_df.empty:
            self.equity_df['date'] = pd.to_datetime(self.equity_df['date'])
            # Calculated columns
            self.equity_df['balance_cad'] = self.equity_df['balance'] * self.equity_df['rate']
            
            # Special handling for SAT (Satoshis)
            # Assuming rate is BTC price, convert sats to BTC then multiply by rate
            mask_sat = self.equity_df['currency'] == 'SAT'
            self.equity_df.loc[mask_sat, 'balance_cad'] = self.equity_df.loc[mask_sat, 'balance_cad'] / 100_000_000.0
            
            self.equity_df['balance_net'] = self.equity_df['balance_cad'] * (1 - self.equity_df['tax'])
        else:
             # Create empty with expected columns if DB is empty to avoid KeyError later
            self.equity_df = pd.DataFrame(columns=['id', 'date', 'description', 'account', 'category', 'currency', 'rate', 'balance', 'tax', 'balance_cad', 'balance_net'])

    def handle_command(self, command):
        cmd = command.lower().strip()
        if cmd in ['q', 'quit']:
            from home_module import HomeModule
            self.app.switch_module(HomeModule(self.app))
        elif cmd == 'qq':
            self.app.quit()
        elif cmd in ['h', 'help']:
            self.output_content = '''Equity Commands:
    - a | add  : Add a new entry
    - l | list : List entries by date
    - q | quit : Return to main menu
    - qq       : Exit to prompt'''
        elif cmd in ['a', 'add']:
            self.add_entry()
        elif cmd in ['l', 'list']:
            self.list_unique_dates()
        elif cmd == "":
            pass
        else:
            self.output_content = f"Unknown command: {command}"

    def add_entry(self):
        self.app.console.clear()
        self.app.console.print("[bold cyan]--- Add Equity Entry ---[/]")
        
        default_date_str = datetime.now().strftime("%Y-%m-%d")
        
        while True:
            # 1. Date
            date_in = self.app.console.input(f"Date [[dim]{default_date_str}[/dim]] >> ")
            date_val = date_in if date_in else default_date_str
            
            # 2. Description
            desc_val = self.app.console.input("Description >> ")
            
            # 3. Account
            self.app.console.print("Accounts: [1] Personnel, [2] Gestion FZ, [3] BZ")
            acc_choice = self.app.console.input("Account >> ")
            acc_map = {'1': 'Personnel', '2': 'Gestion FZ', '3': 'BZ', 'personnel': 'Personnel', 'gestion fz': 'Gestion FZ', 'bz': 'BZ'}
            account_val = acc_map.get(acc_choice.lower(), acc_choice) # Fallback to input if not mapped, though prompts implies strict choice, flexibility is good. User prompt said "choices: ...", usually implies select or type. 
            
            # 4. Category
            self.app.console.print("Categories: [1] Bitcoin, [2] Cash, [3] Immobilier, [4] FBN, [5] IBKR, [6] BZ")
            cat_choice = self.app.console.input("Category >> ")
            cat_map = {'1': 'Bitcoin', '2': 'Cash', '3': 'Immobilier', '4': 'FBN', '5': 'IBKR', '6': 'BZ'}
            # Handle text input or number
            category_val = cat_map.get(cat_choice, cat_choice) # Simplistic mapping, could be more robust
            # Let's clean up case if they typed text
            if category_val.lower() == 'bitcoin': category_val = 'Bitcoin'
            elif category_val.lower() == 'cash': category_val = 'Cash'
            elif category_val.lower() == 'immobilier': category_val = 'Immobilier'
            elif category_val.lower() == 'fbn': category_val = 'FBN'
            elif category_val.lower() == 'ibkr': category_val = 'IBKR'
            
            # 5. Currency
            self.app.console.print("Currency: [1] CAD, [2] USD, [3] SAT")
            cur_choice = self.app.console.input("Currency [[dim]CAD[/dim]] >> ").lower()
            if cur_choice == '2' or cur_choice == 'usd':
                currency_val = 'USD'
            elif cur_choice == '3' or cur_choice == 'sat':
                currency_val = 'SAT'
            else:
                currency_val = 'CAD'
                
            # 6. Rate
            rate_def = "1.0"
            rate_in = self.app.console.input(f"Rate [[dim]{rate_def}[/dim]] >> ")
            try:
                rate_val = float(rate_in) if rate_in else 1.0
            except ValueError:
                rate_val = 1.0
                
            # 7. Balance
            bal_in = self.app.console.input("Balance >> ")
            try:
                balance_val = float(bal_in) if bal_in else 0.0
            except ValueError:
                balance_val = 0.0
                
            # 8. Tax
            tax_in = self.app.console.input("Tax (0.0 - 1.0) [[dim]0.0[/dim]] >> ")
            try:
                tax_val = float(tax_in) if tax_in else 0.0
            except ValueError:
                tax_val = 0.0
                
            # Save
            entry = {
                'date': date_val,
                'description': desc_val,
                'account': account_val,
                'category': category_val,
                'currency': currency_val,
                'rate': rate_val,
                'balance': balance_val,
                'tax': tax_val
            }
            
            if equity_db_handler.save_equity_entry(entry):
                self.app.console.print("[success]Entry added![/]")
            else:
                self.app.console.print("[error]Failed to add entry.[/]")
                
            # Again?
            again = self.app.console.input("\nAdd another with same date? (y/n) >> ").lower()
            if again == 'y':
                default_date_str = date_val
            else:
                break
                
        self.load_equity_data()
        self.output_content = "Data updated."

    def list_unique_dates(self):
        if self.equity_df.empty:
            self.output_content = "[info]No equity data found.[/]"
            return

        # Unique dates
        unique_dates = sorted(self.equity_df['date'].unique(), reverse=True)
        
        self.app.console.clear()
        self.app.console.print("[bold cyan]--- Select Date ---[/]")
        
        for i, dt in enumerate(unique_dates, 1):
            dt_str = pd.to_datetime(dt).strftime('%Y-%m-%d')
            self.app.console.print(f"{i}. {dt_str}")
            
        choice = self.app.console.input("\nSelect number >> ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(unique_dates):
                selected_date = unique_dates[idx]
                self.show_table_for_date(selected_date)
            else:
                self.output_content = "[error]Invalid selection.[/]"
        except ValueError:
             self.output_content = "[error]Invalid input.[/]"
             
    def show_table_for_date(self, date_val):
        # Filter
        mask = self.equity_df['date'] == date_val
        subset = self.equity_df[mask]
        
        date_str = pd.to_datetime(date_val).strftime('%Y-%m-%d')
        table = Table(title=f"Equity entries for {date_str}")
        
        table.add_column("Account", style="cyan")
        table.add_column("Category", style="magenta")
        table.add_column("Desc")
        table.add_column("Curr")
        table.add_column("Bal", justify="right")
        table.add_column("Rate", justify="right")
        table.add_column("Bal CAD", justify="right", style="green")
        table.add_column("Tax", justify="right")
        table.add_column("Bal Net", justify="right", style="bold green")
        
        for _, row in subset.iterrows():
            table.add_row(
                str(row['account']),
                str(row['category']),
                str(row['description']),
                str(row['currency']),
                f"{row['balance']:,.2f}",
                f"{row['rate']:.2f}",
                f"{row['balance_cad']:,.2f}",
                f"{row['tax']:.2f}",
                f"{row['balance_net']:,.2f}"
            )
            
        # Add totals
        total_bal_cad = subset['balance_cad'].sum()
        total_bal_net = subset['balance_net'].sum()
        
        table.add_section()
        table.add_row(
            "TOTAL", "", "", "", "", "",
            f"{total_bal_cad:,.2f}",
            "",
            f"{total_bal_net:,.2f}",
            style="bold"
        )
        
        self.app.console.clear()
        self.app.console.print(table)
        self.app.skip_render = True
        self.output_content = "" # Cleared by direct print

    def get_output(self):
        return self.output_content

    def get_prompt(self):
        return "[prompt][EQUITY] >> [/]"
