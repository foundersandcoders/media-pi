import subprocess

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from daemon.process import running_pid

from ..paths import RECORD


class StatusPanel(Widget):
    def compose(self) -> ComposeResult:
        yield Static("", id="status")

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(5, self.refresh_status)

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # chunk being edited — scaffold, remove on implementation
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # TODO (Plan 2): add a recording_status() helper that parses record.sh
    # status into {recording, scheduled, end_time}, so ControlsPanel can decide
    # whether a manual stop needs the ConfirmStop prompt.
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    def refresh_status(self) -> None:
        result = subprocess.run([RECORD, "status"], capture_output=True, text=True)
        recorder = result.stdout.strip() or result.stderr.strip()
        pid = running_pid()
        daemon = f"daemon: running (pid {pid})" if pid else "daemon: stopped"
        self.query_one("#status", Static).update(f"{recorder}\n{daemon}")
