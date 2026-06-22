from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from ..formatters import format_date, format_size
from ..queries import get_failed_videos

_HEADER = f"{'cohort':<14}  {'name':<12}  {'pt':>2}  {'size':>6}  {'date':>5}  status"


class FailedUploads(Static):
    can_focus = True

    def on_mount(self) -> None:
        self.update(self._build())

    def _build(self):
        rows = get_failed_videos()
        if not rows:
            return Text("no failed uploads", style="#888888")

        parts = [Text(_HEADER, style="#888888"), Text("")]
        for row in rows:
            line = (
                f"{row['cohort']:<14}  "
                f"{row['name']:<12}  "
                f"{row['part']:>2}  "
                f"{format_size(row['video_size']):>6}  "
                f"{format_date(row['recorded_at']):>5}  "
                f"failed"
            )
            parts.append(Text(line, style="#444444"))
            parts.append(Text(f"  └─ {row['error_message'] or '—'}", style="#888888"))
            parts.append(Text(""))
        return Group(*parts)
