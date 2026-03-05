"""Chat display components."""

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static


# Role indicators with colors (Rich markup)
ROLE_INDICATORS = {
    "user": "[#7aa2f7]❯[/#7aa2f7] [bold #7aa2f7]You[/bold #7aa2f7]",
    "assistant": "[#9ece6a]◆[/#9ece6a] [bold #9ece6a]Assistant[/bold #9ece6a]",
    "error": "[#ff6b6b]✗[/#ff6b6b] [bold #ff6b6b]Error[/bold #ff6b6b]",
    "system": "[#e0af68]●[/#e0af68] [bold #e0af68]System[/bold #e0af68]",
}


class ChatMessage(Vertical):
    """A single chat message with role indicator and content."""

    DEFAULT_CSS = """
    ChatMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
    }

    ChatMessage > .role-indicator {
        height: 1;
        padding: 0;
    }

    ChatMessage > .message-content {
        padding: 0 0 0 2;
    }
    """

    def __init__(
        self,
        content: str,
        role: str,
        **kwargs,
    ):
        """Initialize a chat message.

        Args:
            content: The message content (supports markdown for assistant).
            role: The message role (user, assistant, error, system).
        """
        super().__init__(**kwargs)
        self.role = role
        self.raw_content = content
        self._rendered_content = content
        self.add_class("message")
        self.add_class(f"message-{role}")

    def compose(self) -> ComposeResult:
        """Compose the message with role indicator and content."""
        # Role indicator
        indicator = ROLE_INDICATORS.get(self.role, f"● {self.role.title()}")
        yield Static(indicator, classes="role-indicator", markup=True)

        # Content - markdown for assistant, plain for others
        if self.role == "assistant":
            yield Static(Markdown(self.raw_content), classes="message-content")
        else:
            yield Static(self.raw_content, classes="message-content", markup=True)


class StreamingMessage(Vertical):
    """A message that can be updated with streaming content."""

    DEFAULT_CSS = """
    StreamingMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
    }

    StreamingMessage > .role-indicator {
        height: 1;
        padding: 0;
    }

    StreamingMessage > .message-content {
        padding: 0 0 0 2;
    }
    """

    def __init__(self, **kwargs):
        """Initialize a streaming message."""
        super().__init__(**kwargs)
        self.add_class("message")
        self.add_class("message-assistant")
        self._content = ""
        self._pending_update = False
        self._content_widget: Static | None = None

    def compose(self) -> ComposeResult:
        """Compose the streaming message."""
        indicator = ROLE_INDICATORS["assistant"]
        yield Static(indicator, classes="role-indicator", markup=True)
        yield Static("▌", classes="message-content")

    def on_mount(self) -> None:
        """Get reference to content widget after mount."""
        self._content_widget = self.query_one(".message-content", Static)

    def append(self, text: str) -> None:
        """Append text to the message (batched updates)."""
        self._content += text
        self._pending_update = True

    def flush(self) -> None:
        """Flush pending updates to the display."""
        if self._pending_update and self._content_widget:
            display_content = self._content + "▌" if self._content else "▌"
            self._content_widget.update(display_content)
            self._pending_update = False

    @property
    def content(self) -> str:
        """Get the current content."""
        return self._content

    def finalize(self) -> None:
        """Finalize the message with markdown rendering."""
        if self._content_widget:
            self._content_widget.update(Markdown(self._content))


class ChatLog(Vertical):
    """Container for chat messages."""

    def __init__(self, **kwargs):
        """Initialize the chat log."""
        super().__init__(**kwargs)
        self.id = "chat-log"


class ChatContainer(ScrollableContainer):
    """Scrollable container for chat log."""

    def __init__(self, **kwargs):
        """Initialize the chat container."""
        super().__init__(**kwargs)
        self.id = "chat-container"

    def compose(self) -> ComposeResult:
        """Compose the chat container."""
        yield ChatLog()

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat."""
        self.scroll_end(animate=False)
