"""Input components."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import TextArea
from textual.message import Message
from textual.events import Key


class MessageInput(TextArea):
    """Multi-line text input for messages."""

    class Submitted(Message):
        """Message submitted event."""

        def __init__(self, value: str) -> None:
            """Initialize the message."""
            self.value = value
            super().__init__()

    def __init__(self, **kwargs):
        """Initialize the input."""
        super().__init__(**kwargs)
        self.id = "message-input"

    async def on_key(self, event: Key) -> None:
        """Handle key events before TextArea processes them."""
        if event.key == "enter":
            # Plain enter submits
            event.stop()
            event.prevent_default()
            self._submit()
        # shift+enter, ctrl+enter etc. will pass through and add newlines

    def _submit(self) -> None:
        """Submit the current input."""
        value = self.text.strip()
        if value:
            self.post_message(self.Submitted(value))
            self.clear()


class InputContainer(Horizontal):
    """Container for the input area."""

    def __init__(self, **kwargs):
        """Initialize the input container."""
        super().__init__(**kwargs)
        self.id = "input-container"

    def compose(self) -> ComposeResult:
        """Compose the input container."""
        yield MessageInput()
