"""Module for the REPL command loop."""
import asyncio

from . import handlers


class REPL:
    """A REPL for interacting with the Charge Point."""

    def __init__(self, charge_point):
        self.charge_point = charge_point
        self.commands = {
            "status": handlers.status,
            "logs": handlers.logs,
            "connect": handlers.connect,
            "authorize": handlers.authorize,
            "event": handlers.event,
            "charge": handlers.charge,
            "stop_charge": handlers.stop_charge,
            "disconnect": handlers.disconnect,
            "quit": handlers.quit,
            "exit": handlers.quit,
            "help": self.help,
        }

    async def run(self):
        """Run the REPL loop."""
        while True:
            try:
                cmd_line = await asyncio.to_thread(input, "› ")
                parts = cmd_line.strip().split()
                if not parts:
                    continue

                cmd_name = parts[0].lower()
                args = parts[1:]

                command = self.commands.get(cmd_name)
                if command:
                    await command(self.charge_point, *args)
                else:
                    print(f"Unknown command: {cmd_name}")

            except (EOFError, KeyboardInterrupt):
                await handlers.quit(self.charge_point)
                break
            except Exception as e:
                print(f"Error: {e}")

    async def help(self, *args):
        """Display help message."""
        print("Available commands:")
        for cmd in self.commands:
            print(f"  - {cmd}")
