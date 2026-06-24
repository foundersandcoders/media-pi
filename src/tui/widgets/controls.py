import subprocess

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

from ..paths import RECORD
from .mixins import ArrowNavigable


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
        yield Button("Start", id="start", variant="primary", flat=True)
        yield Button("Stop", id="stop", variant="primary", flat=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            subprocess.run([RECORD, "start"])
        elif event.button.id == "stop":
            subprocess.run([RECORD, "stop"])
        self.post_message(self.ActionCompleted())
