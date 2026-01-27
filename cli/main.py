import sys
import os
import argparse

# Add parent directory to path for shared module access
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from shared.supabase_client import login, is_authenticated
from home_module import HomeModule


class TradeToolsApp:
    def __init__(self, auto_login=None, auto_password=None, auto_module=None):
        # Store auto-login credentials
        self.auto_login = auto_login
        self.auto_password = auto_password
        self.auto_module = auto_module
        
        # Gruvbox theme definition
        gruvbox_theme = Theme({
            "base": "#ebdbb2 on #282828",
            "header.text": "bold #d79921",
            "header.bg": "#3c3836",
            "panel.border": "#a89984",
            "prompt": "bold #fabd2f",
            "error": "bold #cc241d",
            "info": "#83a598",
            "success": "bold #b8bb26",
            # Gruvbox colors
            "dark0_hard": "#1d2021",
            "dark0": "#282828",
            "dark0_soft": "#32302f",
            "dark1": "#3c3836",
            "dark2": "#504945",
            "dark3": "#665c54",
            "dark4": "#7c6f64",
            # Light colors
            "light0_hard": "#f9f5d7",
            "light0": "#fbf1c7",
            "light0_soft": "#f2e5bc",
            "light1": "#ebdbb2",
            "light2": "#d5c4a1",
            "light3": "#bdae93",
            "light4": "#a89984",
            # Neutral colors
            "neutral_red": "#cc241d",
            "neutral_green": "#98971a",
            "neutral_yellow": "#d79921",
            "neutral_blue": "#458588",
            "neutral_purple": "#b16286",
            "neutral_aqua": "#689d6a",
            "neutral_orange": "#d65d0e",
            # Bright colors
            "bright_red": "#fb4934",
            "bright_green": "#b8bb26",
            "bright_yellow": "#fabd2f",
            "bright_blue": "#83a598",
            "bright_purple": "#d3869b",
            "bright_aqua": "#8ec07c",
            "bright_orange": "#fe8019",
            # Faded colors
            "faded_red": "#9d0006",
            "faded_green": "#79740e",
            "faded_yellow": "#b57614",
            "faded_blue": "#076678",
            "faded_purple": "#8f3f71",
            "faded_aqua": "#427b58",
            "faded_orange": "#af3a03"
        })
        self.console = Console(theme=gruvbox_theme, style="base")
        self.running = True
        self.active_module = None
        self.skip_render = False

    def authenticate(self) -> bool:
        """Prompt user for login credentials and authenticate with Supabase."""
        self.console.clear()
        self.console.print(Panel(
            Text("TradeTools v3 - Login", justify="center", style="header.text"),
            style="on #3c3836",
            border_style="panel.border"
        ))
        self.console.print()

        # If auto-login credentials provided, use them
        if self.auto_login and self.auto_password:
            try:
                self.console.print("[info]Auto-authenticating...[/]")
                result = login(self.auto_login, self.auto_password)
                if result and result.get("user"):
                    self.console.print(f"[success]Welcome, {result['user'].email}![/]")
                    return True
                else:
                    self.console.print("[error]Auto-login failed. Falling back to manual login.[/]")
            except Exception as e:
                self.console.print(f"[error]Auto-login error: {e}. Falling back to manual login.[/]")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                email = self.console.input("[prompt]Email: [/]")
                password = self.console.input("[prompt]Password: [/]", password=True)

                self.console.print("[info]Authenticating...[/]")
                result = login(email, password)

                if result and result.get("user"):
                    self.console.print(f"[success]Welcome, {result['user'].email}![/]")
                    return True
                else:
                    self.console.print("[error]Login failed. Please try again.[/]")

            except Exception as e:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    self.console.print(f"[error]Authentication error: {e}[/]")
                    self.console.print(f"[info]Attempts remaining: {remaining}[/]")
                else:
                    self.console.print(f"[error]Authentication failed: {e}[/]")

        return False

    def switch_module(self, module):
        self.active_module = module

    def _switch_to_module(self, module_name):
        """Switch to a module by name."""
        module_name = module_name.lower()
        if module_name == 'ibkr':
            from ibkr_module import IBKRModule
            self.switch_module(IBKRModule(self))
        elif module_name == 'fbn':
            from fbn_module import FBNModule
            self.switch_module(FBNModule(self))
        elif module_name == 'equity':
            from equity_module import EquityModule
            self.switch_module(EquityModule(self))

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
        # Authenticate before proceeding
        if not self.authenticate():
            self.console.print("[error]Authentication failed. Exiting.[/]")
            return

        # Initialize the home module after authentication
        self.active_module = HomeModule(self)

        # If auto-module specified, switch to it
        if self.auto_module:
            self._switch_to_module(self.auto_module)

        while self.running:
            if not self.skip_render:
                self.console.clear()
                layout = self.get_layout()

                # Print the layout taking up most of the screen
                # Leave 1 line for the prompt
                self.console.print(layout, height=self.console.height - 2)

            self.skip_render = False


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


def parse_args():
    parser = argparse.ArgumentParser(description='TradeTools v3 - CLI Trading Application')
    parser.add_argument('-l', '--login', type=str, help='Email for auto-login')
    parser.add_argument('-p', '--password', type=str, help='Password for auto-login')
    parser.add_argument('-m', '--module', type=str, choices=['ibkr', 'fbn', 'equity'],
                        help='Module to open directly (ibkr, fbn, or equity)')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = TradeToolsApp(
        auto_login=args.login,
        auto_password=args.password,
        auto_module=args.module
    )
    app.run()
