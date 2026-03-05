"""Conversation picker modal for loading saved conversations."""

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from foundry_tui.storage.conversations import ConversationMetadata, list_conversations


class ConversationListView(ListView):
    """Custom ListView for conversations without IDs to avoid duplicates."""

    pass


class ConversationPicker(ModalScreen):
    """Modal screen for selecting a conversation to load."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    DEFAULT_CSS = """
    ConversationPicker {
        align: center middle;
    }

    ConversationPicker > Vertical {
        width: 80;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ConversationPicker #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    ConversationPicker #search {
        margin-bottom: 1;
    }

    ConversationPicker ConversationListView {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    ConversationPicker ListItem {
        padding: 0 1;
    }

    ConversationPicker ListItem:hover {
        background: $primary 20%;
    }

    ConversationPicker ListItem.-active {
        background: $primary 40%;
    }

    ConversationPicker #empty-message {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }

    ConversationPicker #footer {
        text-align: center;
        color: $text-muted;
    }

    ConversationPicker .conv-title {
        text-style: bold;
    }

    ConversationPicker .conv-meta {
        color: $text-muted;
    }

    ConversationPicker .conv-preview {
        color: $text-muted;
        text-style: italic;
    }
    """

    class ConversationSelected(Message):
        """Message sent when a conversation is selected."""

        def __init__(self, conversation_id: str) -> None:
            super().__init__()
            self.conversation_id = conversation_id

    class Cancelled(Message):
        """Message sent when picker is cancelled."""

        pass

    def __init__(self):
        super().__init__()
        self._conversations: list[ConversationMetadata] = []
        self._filtered: list[ConversationMetadata] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Load Conversation", id="title")
            yield Input(placeholder="Search conversations...", id="search")
            yield ConversationListView()
            yield Static("", id="empty-message")
            yield Static("↑↓ Navigate  Enter Select  Esc Cancel", id="footer")

    def on_mount(self) -> None:
        """Load conversations on mount."""
        self._conversations = list_conversations()
        self._filtered = self._conversations.copy()
        self._refresh_list()
        self.query_one("#search", Input).focus()

    def _refresh_list(self) -> None:
        """Refresh the conversation list."""
        list_view = self.query_one(ConversationListView)
        list_view.clear()

        empty_msg = self.query_one("#empty-message", Static)

        if not self._filtered:
            if not self._conversations:
                empty_msg.update("[dim]No saved conversations yet.[/dim]")
            else:
                empty_msg.update("[dim]No matching conversations.[/dim]")
            empty_msg.display = True
            return

        empty_msg.display = False

        for conv in self._filtered:
            # Format the date
            age = self._format_age(conv.updated_at)

            # Create list item content
            content = (
                f"[bold]{conv.title}[/bold]\n"
                f"[dim]{conv.model_name} · {conv.message_count} messages · {age}[/dim]"
            )
            if conv.preview:
                content += f"\n[italic dim]{conv.preview}[/italic dim]"

            item = ListItem(Static(content, markup=True))
            item.data = conv  # Store metadata for retrieval
            list_view.append(item)

    def _format_age(self, dt: datetime) -> str:
        """Format datetime as relative age."""
        now = datetime.now()
        diff = now - dt

        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                if minutes == 0:
                    return "just now"
                return f"{minutes}m ago"
            return f"{hours}h ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            return dt.strftime("%b %d, %Y")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter conversations based on search input."""
        query = event.value.lower().strip()

        if not query:
            self._filtered = self._conversations.copy()
        else:
            self._filtered = [
                conv
                for conv in self._conversations
                if query in conv.title.lower()
                or query in conv.model_name.lower()
                or query in conv.preview.lower()
            ]

        self._refresh_list()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle conversation selection from list."""
        if hasattr(event.item, "data") and event.item.data:
            conv = event.item.data
            self.dismiss()
            self.post_message(self.ConversationSelected(conv.id))

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "escape":
            event.stop()
            self.dismiss()
            self.post_message(self.Cancelled())
        elif event.key == "enter":
            # If list has focus and item is selected, select it
            list_view = self.query_one(ConversationListView)
            if list_view.highlighted_child:
                item = list_view.highlighted_child
                if hasattr(item, "data") and item.data:
                    event.stop()
                    self.dismiss()
                    self.post_message(self.ConversationSelected(item.data.id))

    def action_cancel(self) -> None:
        """Cancel the picker."""
        self.dismiss()
        self.post_message(self.Cancelled())

    def action_select(self) -> None:
        """Select current item."""
        list_view = self.query_one(ConversationListView)
        if list_view.highlighted_child:
            item = list_view.highlighted_child
            if hasattr(item, "data") and item.data:
                self.dismiss()
                self.post_message(self.ConversationSelected(item.data.id))
