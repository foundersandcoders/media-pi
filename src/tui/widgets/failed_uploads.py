import subprocess

from rich.console import Group
from rich.panel import Panel as RichPanel
from rich.text import Text
from textual.widgets import Static

from daemon.db import load_status_ids, set_status

from ..db import get_connection
from ..formatters import format_date, format_size
from ..paths import UPLOAD
from ..queries import get_failed_videos
from .mixins import ArrowNavigable

_HEADER = f"{'cohort':<14}  {'name':<12}  {'pt':>2}  {'size':>6}  {'date':>5}  status"


class FailedUploads(ArrowNavigable, Static):
    can_focus = True
    _focused: bool = False

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

    def on_focus(self) -> None:
        self._focused = True
        self.update(self._build())

    def on_blur(self) -> None:
        self._focused = False
        self.update(self._build())

    def _build(self):
        color = "#ffffff" if self._focused else "#888888"

        if not self._rows:
            return Text("  no failed uploads", style=color)

        # "  " = 1 char for │ + 1 char for Panel's default left padding
        parts = [Text("  " + _HEADER, style=color), Text("")]
        for i, row in enumerate(self._rows):
            line = (
                f"{row['cohort']:<14}  "
                f"{row['name']:<12}  "
                f"{row['part']:>2}  "
                f"{format_size(row['video_size']):>6}  "
                f"{format_date(row['recorded_at']):>5}  "
                f"failed"
            )
            content = Group(
                Text(line, style=color),
                Text(f"  └─ {row['error_message'] or '—'}", style=color),
            )
            border = color if i == self._selected else "#000000"
            parts.append(RichPanel(content, style=border))
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
        row = self._rows[self._selected]
        proc = subprocess.run([UPLOAD, row["file_path"]])
        # Generic handling for now (matches the daemon) — uploaded on success,
        # failed otherwise. See docs/dev/error-handling.md for the planned scheme.
        status_name = "uploaded" if proc.returncode == 0 else "failed"
        with get_connection() as conn:
            ids = load_status_ids(conn)
            set_status(conn, row["id"], ids[status_name])
        self._rows = get_failed_videos()
        self._selected = min(self._selected, max(0, len(self._rows) - 1))
        self.update(self._build())
