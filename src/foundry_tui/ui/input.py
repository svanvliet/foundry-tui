"""Input components."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import TextArea, OptionList
from textual.widgets.option_list import Option
from textual.message import Message
from textual.events import Key

# Slash commands: (command, description)
SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/models", "Select a different model"),
    ("/system", "View/set system prompt"),
    ("/tools", "List registered tools"),
    ("/load", "Browse saved conversations"),
    ("/save", "Save current conversation"),
    ("/new", "Start a new conversation"),
    ("/clear", "Clear chat history"),
    ("/copy", "Copy last response to clipboard"),
    ("/export", "Export conversation to JSON"),
    ("/help", "Show help"),
    ("/quit", "Exit the application"),
]


class CommandMenu(OptionList):
    """Dropdown completion menu for slash commands."""

    DEFAULT_CSS = """
    CommandMenu {
        layer: overlay;
        dock: bottom;
        margin-bottom: 5;
        margin-left: 2;
        margin-right: 2;
        max-height: 14;
        height: auto;
        border: solid $primary-darken-1;
        background: $surface;
        display: none;
    }

    CommandMenu:focus {
        border: solid $primary;
    }

    CommandMenu > .option-list--option-highlighted {
        background: $primary-darken-2;
        color: $text;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._all_commands = SLASH_COMMANDS

    def show_filtered(self, prefix: str) -> None:
        """Show commands matching prefix, or all if just '/'."""
        self.clear_options()

        search = prefix.lstrip("/").lower()
        matches = [
            (cmd, desc)
            for cmd, desc in self._all_commands
            if not search or cmd.lstrip("/").startswith(search)
        ]

        if not matches:
            self.display = False
            return

        for cmd, desc in matches:
            self.add_option(Option(f"{cmd}  [dim]{desc}[/dim]", id=cmd))

        self.display = True
        self.highlighted = 0

    def hide(self) -> None:
        """Hide the menu."""
        self.display = False


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

    def _get_command_menu(self) -> CommandMenu | None:
        """Get the command menu widget if it exists."""
        try:
            return self.screen.query_one(CommandMenu)
        except Exception:
            return None

    def _menu_is_visible(self) -> bool:
        menu = self._get_command_menu()
        return menu is not None and menu.display

    async def on_key(self, event: Key) -> None:
        """Handle key events before TextArea processes them."""
        menu = self._get_command_menu()

        # When menu is visible, route navigation keys to it
        if self._menu_is_visible() and menu is not None:
            if event.key == "up":
                event.stop()
                event.prevent_default()
                menu.action_cursor_up()
                return
            elif event.key == "down":
                event.stop()
                event.prevent_default()
                menu.action_cursor_down()
                return
            elif event.key == "tab":
                event.stop()
                event.prevent_default()
                self._accept_completion(menu)
                return
            elif event.key == "escape":
                event.stop()
                event.prevent_default()
                menu.hide()
                return
            elif event.key == "enter":
                event.stop()
                event.prevent_default()
                self._accept_completion(menu)
                return

        if event.key == "enter":
            # Plain enter submits
            event.stop()
            event.prevent_default()
            if menu:
                menu.hide()
            self._submit()
        # shift+enter, ctrl+enter etc. will pass through and add newlines

    def _accept_completion(self, menu: CommandMenu) -> None:
        """Accept the currently highlighted completion."""
        highlighted = menu.highlighted
        if highlighted is not None:
            option = menu.get_option_at_index(highlighted)
            cmd = option.id
            # Replace the text with the completed command
            self.clear()
            self.insert(f"{cmd} ")
        menu.hide()

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update command menu as text changes."""
        menu = self._get_command_menu()
        if menu is None:
            return

        text = self.text.strip()

        # Show menu only when text starts with / and is a single word (no space yet)
        if text.startswith("/") and " " not in text:
            menu.show_filtered(text)
        else:
            menu.hide()

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
