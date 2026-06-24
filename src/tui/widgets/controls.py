import subprocess

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

from ..paths import DAEMON_SERVICE, RECORD
from .mixins import ArrowNavigable
from .panel import Panel


class ControlsPanel(ArrowNavigable, Widget):
    BINDINGS = [
        *ArrowNavigable.BINDINGS,
        ("tab", "noop"),
        ("shift+tab", "noop"),
    ]

    class ActionCompleted(Message):
        pass

    def action_noop(self) -> None:
        pass

    def compose(self) -> ComposeResult:
        yield Panel(
            Button("Start", id="start", variant="primary", flat=True),
            Button("Stop", id="stop", variant="primary", flat=True),
            title="Recording",
        )
        yield Panel(
            Button("Start", id="daemon-start", variant="primary", flat=True),
            Button("Stop", id="daemon-stop", variant="primary", flat=True),
            title="Daemon",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # daemon controls use `sudo -n`: a missing sudoers rule fails fast instead
        # of prompting for a password on stdin and hanging the TUI.
        cmds = {
            "start": [RECORD, "start"],
            "stop": [RECORD, "stop"],
            "daemon-start": ["sudo", "-n", "systemctl", "start", DAEMON_SERVICE],
            "daemon-stop": ["sudo", "-n", "systemctl", "stop", DAEMON_SERVICE],
        }
        cmd = cmds.get(event.button.id)
        if cmd:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                msg = result.stderr.strip() or f"{event.button.id} failed"
                self.app.notify(msg, severity="error")
        self.post_message(self.ActionCompleted())
