from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header

from .widgets.controls import ControlsPanel
from .widgets.failed_uploads import FailedUploads
from .widgets.panel import Panel
from .widgets.status import StatusPanel
from .widgets.video_table import VideoTable


class MediaPiTUI(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("1", "focus_controls", "Controls"),
        ("2", "focus_failed", "Failed Uploads"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Panel(StatusPanel(), title="Status")
        yield Panel(ControlsPanel(), title="[1] Controls")
        yield Vertical(
            Panel(VideoTable(), title="Video Tracking"),
            Panel(FailedUploads(), title="[2] Failed Uploads"),
            id="data-panels",
        )

    def action_focus_controls(self) -> None:
        self.query_one("#start").focus()

    def action_focus_failed(self) -> None:
        self.query_one(FailedUploads).focus()

    def on_resize(self, event) -> None:
        self.query_one("#data-panels").set_class(event.size.width >= 120, "-wide")

    def on_controls_panel_action_completed(self) -> None:
        self.query_one(StatusPanel).refresh_status()


def main() -> None:
    MediaPiTUI().run()
