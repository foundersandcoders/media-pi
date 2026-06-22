from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from .formatters import format_date, format_size
from .queries import get_all_videos


class VideoTable(Static):
    def on_mount(self) -> None:
        self.update(self._build())

    def _build(self):
        rows = get_all_videos()
        table = Table(
            show_header=True,
            header_style="#888888",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("cohort")
        table.add_column("name")
        table.add_column("pt", justify="right")
        table.add_column("size", justify="right")
        table.add_column("date", justify="right")
        table.add_column("status")

        for row in rows:
            style = "#888888"
            table.add_row(
                Text(row["cohort"], style=style),
                Text(row["name"], style=style),
                Text(str(row["part"]), style=style),
                Text(format_size(row["video_size"]), style=style),
                Text(format_date(row["recorded_at"]), style=style),
                Text(row["status"], style=style),
            )
        return table
