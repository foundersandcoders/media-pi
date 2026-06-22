import subprocess

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

from ..paths import RECORD, UPLOAD


class ControlsPanel(Widget):
    class ActionCompleted(Message):
        pass

    def compose(self) -> ComposeResult:
        yield Button("Start", id="start", variant="primary", flat=True)
        yield Button("Stop", id="stop", variant="primary", flat=True)
        yield Button("Upload last", id="upload", variant="primary", flat=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            subprocess.run([RECORD, "start"])
        elif event.button.id == "stop":
            subprocess.run([RECORD, "stop"])
        elif event.button.id == "upload":
            last = subprocess.run(
                [RECORD, "last"], capture_output=True, text=True
            ).stdout.strip()
            if last:
                subprocess.run([UPLOAD, last])
        self.post_message(self.ActionCompleted())
