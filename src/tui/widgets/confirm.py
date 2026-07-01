"""Confirmation modal for stopping a scheduled recording.

Textual 8.2.7 has no ModalScreen, so this is a plain Screen pushed with
App.push_screen_wait, whose return value is whatever dismiss() is called with.

STUB (Plan 1): layout + wiring land in Plan 2.
"""

# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# new file — scaffold, remove on implementation
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

from textual.screen import Screen


class ConfirmStop(Screen[bool]):
    # in: end_time (iso) -> shows "scheduled to run until HH:MM"
    # out (via dismiss): True = stop anyway, False = keep recording
    # should render the end time + Yes/No buttons
    # should dismiss(True) on Yes; dismiss(False) on No or Esc

    def __init__(self, end_time: str) -> None:
        super().__init__()
        self._end_time = end_time

    def compose(self):  # TODO (Plan 2): Yes/No buttons + "runs until HH:MM" message
        ...

    def on_button_pressed(self, event) -> None:  # TODO (Plan 2)
        # self.dismiss(event.button.id == "confirm-yes")
        ...
