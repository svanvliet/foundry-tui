"""Chat display components."""

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static
from textual.reactive import reactive


class ChatMessage(Static):
    """A single chat message with markdown rendering."""

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
        # Render markdown for assistant messages, plain text for others
        if role == "assistant":
            rendered = Markdown(content)
        else:
            rendered = content

        super().__init__(rendered, markup=(role != "assistant"), **kwargs)
        self.role = role
        self.raw_content = content
        self.add_class("message")
        self.add_class(f"message-{role}")

        # Set border title based on role
        role_titles = {
            "user": "You",
            "assistant": "Assistant",
            "error": "Error",
            "system": "System",
        }
        self.border_title = role_titles.get(role, role.title())


class StreamingMessage(Static):
    """A message that can be updated with streaming content."""

    def __init__(self, **kwargs):
        """Initialize a streaming message."""
        super().__init__("▌", **kwargs)
        self.add_class("message")
        self.add_class("message-assistant")
        self.border_title = "Assistant"
        self._content = ""
        self._pending_update = False

    def append(self, text: str) -> None:
        """Append text to the message (batched updates)."""
        self._content += text
        # Mark that we need an update, but don't trigger immediately
        self._pending_update = True

    def flush(self) -> None:
        """Flush pending updates to the display."""
        if self._pending_update:
            display_content = self._content + "▌" if self._content else "▌"
            self.update(display_content)
            self._pending_update = False

    @property
    def content(self) -> str:
        """Get the current content."""
        return self._content

    def finalize(self) -> None:
        """Finalize the message with markdown rendering."""
        # Render final content as markdown
        self.update(Markdown(self._content))


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
