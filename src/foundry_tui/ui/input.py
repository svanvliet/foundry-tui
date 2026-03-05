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

    DEFAULT_CSS = """
    InputContainer {
        height: auto;
        max-height: 10;
        padding: 0 1;
        background: $surface;
    }

    InputContainer > .input-prompt {
        width: 2;
        height: 100%;
        content-align: left middle;
        padding: 1 0 0 0;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the input container."""
        super().__init__(**kwargs)
        self.id = "input-container"

    def compose(self) -> ComposeResult:
        """Compose the input container."""
        from textual.widgets import Static

        yield Static("[#7aa2f7]❯[/#7aa2f7]", classes="input-prompt", markup=True)
        yield MessageInput()
