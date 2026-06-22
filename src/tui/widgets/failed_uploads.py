import subprocess

from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from ..formatters import format_date, format_size
from ..paths import UPLOAD
from ..queries import get_failed_videos
from .mixins import ArrowNavigable

_HEADER = f"{'cohort':<14}  {'name':<12}  {'pt':>2}  {'size':>6}  {'date':>5}  status"


class FailedUploads(ArrowNavigable, Static):
    can_focus = True

    BINDINGS = [
        *ArrowNavigable.BINDINGS,
        ("enter", "upload_selected"),
        ("tab", "noop"),
        ("shift+tab", "noop"),
    ]

    def on_mount(self) -> None:
        self._rows = get_failed_videos()
        self._selected = 0
        self.update(self._build())

    def _build(self):
        if not self._rows:
            return Text("no failed uploads", style="#888888")

        parts = [Text(_HEADER, style="#888888"), Text("")]
        for i, row in enumerate(self._rows):
            style = "#ffffff" if i == self._selected else "#444444"
            line = (
                f"{row['cohort']:<14}  "
                f"{row['name']:<12}  "
                f"{row['part']:>2}  "
                f"{format_size(row['video_size']):>6}  "
                f"{format_date(row['recorded_at']):>5}  "
                f"failed"
            )
            parts.append(Text(line, style=style))
            parts.append(Text(f"  └─ {row['error_message'] or '—'}", style="#888888"))
            parts.append(Text(""))
        return Group(*parts)

    def action_noop(self) -> None:
        pass

    def action_next_item(self) -> None:
        if self._rows:
            self._selected = (self._selected + 1) % len(self._rows)
            self.update(self._build())

    def action_prev_item(self) -> None:
        if self._rows:
            self._selected = (self._selected - 1) % len(self._rows)
            self.update(self._build())

    def action_upload_selected(self) -> None:
        if not self._rows:
            return
        file_path = self._rows[self._selected]["file_path"]
        subprocess.run([UPLOAD, file_path])
        self._rows = get_failed_videos()
        self._selected = min(self._selected, max(0, len(self._rows) - 1))
        self.update(self._build())
