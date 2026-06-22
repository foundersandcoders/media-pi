from textual.widget import Widget


class Panel(Widget):
    def __init__(self, *children, title: str = "", **kwargs):
        super().__init__(*children, **kwargs)
        self.border_title = title
