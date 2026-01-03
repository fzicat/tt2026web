class Module:
    def __init__(self, app):
        self.app = app

    def handle_command(self, command):
        raise NotImplementedError

    def get_output(self):
        raise NotImplementedError

    def get_prompt(self):
        return "[prompt]>> [/]"
