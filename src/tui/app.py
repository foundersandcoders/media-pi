from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical

from .db import SENTINEL_FILE, notify_change
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
        yield Panel(StatusPanel(), title="Status")
        yield Panel(ControlsPanel(), title="[1] Controls")
        yield Vertical(
            Panel(VideoTable(), title="Video Tracking"),
            Panel(FailedUploads(), title="[2] Failed Uploads"),
            id="data-panels",
        )

    def on_mount(self) -> None:
        # Create the sentinel up front so awatch has an existing path to watch
        # (and a stable inode — we only ever touch it, never delete it).
        notify_change()
        self._watch_db_changes()

    @work(exclusive=True)
    async def _watch_db_changes(self) -> None:
        """Reload the data widgets whenever a writer touches the sentinel."""
        from watchfiles import awatch

        async for _ in awatch(str(SENTINEL_FILE)):
            self.reload_data()

    def reload_data(self) -> None:
        self.query_one(VideoTable).reload()
        self.query_one(FailedUploads).reload()

    def action_focus_controls(self) -> None:
        self.query_one("#start").focus()

    def action_focus_failed(self) -> None:
        self.query_one(FailedUploads).focus()

    def on_resize(self, event) -> None:
        self.query_one("#data-panels").set_class(event.size.width >= 120, "-wide")

    def on_controls_panel_action_completed(self) -> None:
        # systemctl returns before the daemon writes its PID file, so refresh now
        # and again shortly after to catch the daemon coming up/down. set_timer is
        # non-blocking; the 5s StatusPanel poll is the final backstop.
        status = self.query_one(StatusPanel)
        status.refresh_status()
        self.set_timer(1.5, status.refresh_status)


def main() -> None:
    MediaPiTUI().run()
