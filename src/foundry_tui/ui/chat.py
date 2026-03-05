"""Chat display components."""

import json

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static, Collapsible
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


class ToolCallMessage(Collapsible):
    """Collapsible widget showing a tool call and its result."""

    def __init__(
        self,
        tool_name: str,
        arguments: str,
        result: str | None = None,
        error: bool = False,
        **kwargs,
    ):
        """Initialize a tool call display.

        Args:
            tool_name: Name of the tool invoked.
            arguments: JSON string of arguments.
            result: Tool execution result (None while pending).
            error: Whether the result is an error.
        """
        self._tool_name = tool_name
        self._arguments = arguments
        self._result = result
        self._error = error

        # Format a short argument summary for the title
        arg_summary = self._format_arg_summary(arguments)
        title = f"⚡ {tool_name}({arg_summary})"

        # Build the body content
        body = self._build_body()

        super().__init__(Static(body, markup=False), title=title, collapsed=True, **kwargs)
        self.add_class("tool-call-message")
        if error:
            self.add_class("tool-call-error")

    def _format_arg_summary(self, arguments: str) -> str:
        """Create a compact summary of arguments for the title."""
        try:
            args = json.loads(arguments) if arguments else {}
            parts = []
            for k, v in args.items():
                val = json.dumps(v) if not isinstance(v, str) else f'"{v}"'
                if len(val) > 40:
                    val = val[:37] + '..."'
                parts.append(val)
            return ", ".join(parts)
        except (json.JSONDecodeError, TypeError):
            return arguments[:50] if arguments else ""

    def _build_body(self) -> str:
        """Build the body text with arguments and result."""
        lines = ["Arguments:"]
        try:
            formatted = json.dumps(json.loads(self._arguments), indent=2)
            lines.append(formatted)
        except (json.JSONDecodeError, TypeError):
            lines.append(self._arguments or "(none)")

        lines.append("")
        if self._result is not None:
            label = "Error:" if self._error else "Result:"
            lines.append(label)
            lines.append(self._result)
        else:
            lines.append("⏳ Executing...")

        return "\n".join(lines)

    def set_result(self, result: str, error: bool = False) -> None:
        """Update the tool call with its execution result."""
        self._result = result
        self._error = error
        if error:
            self.add_class("tool-call-error")

        # Update body content
        body_widget = self.query_one(Static)
        body_widget.update(self._build_body())


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
