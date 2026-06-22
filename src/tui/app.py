from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header

from .controls import ControlsPanel
from .failed_uploads import FailedUploads
from .panel import Panel
from .status import StatusPanel
from .video_table import VideoTable


class MediaPiTUI(App):
    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Panel(StatusPanel(), title="Status")
        yield Panel(ControlsPanel(), title="Controls")
        yield Vertical(
            Panel(VideoTable(), title="Video Tracking"),
            Panel(FailedUploads(), title="Failed Uploads"),
            id="data-panels",
        )

    def on_resize(self, event) -> None:
        self.query_one("#data-panels").set_class(event.size.width >= 120, "-wide")

    def on_controls_panel_action_completed(self) -> None:
        self.query_one(StatusPanel).refresh_status()


def main() -> None:
    MediaPiTUI().run()
