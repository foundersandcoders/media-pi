from textual.app import App, ComposeResult
from textual.widgets import Header

from .controls import ControlsPanel
from .panel import Panel
from .status import StatusPanel


class MediaPiTUI(App):
    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Panel(StatusPanel(), title="Status")
        yield Panel(ControlsPanel(), title="Controls")

    def on_controls_panel_action_completed(self) -> None:
        self.query_one(StatusPanel).refresh_status()


def main() -> None:
    MediaPiTUI().run()
