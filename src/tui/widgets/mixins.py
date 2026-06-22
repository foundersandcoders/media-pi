from textual.widgets import Button


class ArrowNavigable:
    """Cycles focus through child Button widgets using arrow keys."""

    BINDINGS = [
        ("right,down", "next_item"),
        ("left,up", "prev_item"),
    ]

    def action_next_item(self) -> None:
        buttons = list(self.query(Button))  # type: ignore[attr-defined]
        focused = self.app.focused  # type: ignore[attr-defined]
        if focused in buttons:
            buttons[(buttons.index(focused) + 1) % len(buttons)].focus()

    def action_prev_item(self) -> None:
        buttons = list(self.query(Button))  # type: ignore[attr-defined]
        focused = self.app.focused  # type: ignore[attr-defined]
        if focused in buttons:
            buttons[(buttons.index(focused) - 1) % len(buttons)].focus()
