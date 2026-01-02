import sqlite3
import pandas as pd
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
import sys
import os

# Database setup
def init_db():
    conn = sqlite3.connect("tradetools.db")
    # Placeholder for future tables
    conn.close()

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
            self.output_content = "IBKR commands:\n - quit (q): Return to main menu\n - help (h): Show this message"
        elif cmd == "":
            pass
        else:
            self.output_content = f"Unknown command: {command}\nType 'help' for valid commands."

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
        body_panel = Panel(
            Text(self.active_module.get_output(), style="#ebdbb2"),
            title="Output",
            border_style="panel.border",
            style="on #282828"
        )
        layout["body"].update(body_panel)
        
        return layout

    def run(self):
        init_db()
        
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
