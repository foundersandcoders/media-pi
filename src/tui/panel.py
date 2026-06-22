from textual.widget import Widget


class Panel(Widget):
    DEFAULT_CSS = """
    Panel {
        border: solid $primary;
        padding: 1;
        height: auto;
    }
    """

    def __init__(self, *children, title: str = "", **kwargs):
        super().__init__(*children, **kwargs)
        self.border_title = title
