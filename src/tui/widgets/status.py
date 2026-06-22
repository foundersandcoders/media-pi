import subprocess

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ..paths import RECORD


class StatusPanel(Widget):
    def compose(self) -> ComposeResult:
        yield Static("", id="status")

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(5, self.refresh_status)

    def refresh_status(self) -> None:
        result = subprocess.run([RECORD, "status"], capture_output=True, text=True)
        self.query_one("#status", Static).update(
            result.stdout.strip() or result.stderr.strip()
        )
