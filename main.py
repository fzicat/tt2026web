from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
import ibkr_db_handler

from home_module import HomeModule

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
            "info": "#83a598",
        })
        self.console = Console(theme=gruvbox_theme, style="base")
        self.running = True
        self.active_module = HomeModule(self)
        self.skip_render = False

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
        ibkr_db_handler.init_db()
        
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

if __name__ == "__main__":
    app = TradeToolsApp()
    app.run()
