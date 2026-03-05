"""Input components."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import TextArea, OptionList
from textual.widgets.option_list import Option
from textual.message import Message
from textual.events import Key

# Slash commands: (command, description, accepts_args)
SLASH_COMMANDS: list[tuple[str, str, bool]] = [
    ("/models", "Select a different model", True),
    ("/system", "View/set system prompt", True),
    ("/tools", "List registered tools", True),
    ("/load", "Browse saved conversations", False),
    ("/save", "Save current conversation", True),
    ("/new", "Start a new conversation", False),
    ("/clear", "Clear chat history", False),
    ("/copy", "Copy last response to clipboard", False),
    ("/export", "Export conversation to JSON", True),
    ("/help", "Show help", False),
    ("/quit", "Exit the application", False),
]

# Commands that accept args → map to subcommand completions
# Additional dynamic completions (e.g. model names) are injected at runtime
STATIC_ARG_COMPLETIONS: dict[str, list[tuple[str, str]]] = {
    "/system": [("clear", "Remove system prompt")],
    "/tools": [("info", "Show tool details")],
}


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
        self._mode: str = "command"  # "command" or "arg"
        self._current_cmd: str = ""
        self._model_names: list[str] = []

    def set_model_names(self, names: list[str]) -> None:
        """Set available model names for /models completion."""
        self._model_names = names

    def show_commands(self, prefix: str) -> None:
        """Show commands matching prefix."""
        self._mode = "command"
        self.clear_options()

        search = prefix.lstrip("/").lower()
        matches = [
            (cmd, desc)
            for cmd, desc, _ in self._all_commands
            if not search or cmd.lstrip("/").startswith(search)
        ]

        if not matches:
            self.display = False
            return

        for cmd, desc in matches:
            self.add_option(Option(f"{cmd}  [dim]{desc}[/dim]", id=cmd))

        self.display = True
        self.highlighted = 0

    def show_args(self, cmd: str, arg_prefix: str) -> None:
        """Show argument completions for a command."""
        self._mode = "arg"
        self._current_cmd = cmd
        self.clear_options()

        candidates: list[tuple[str, str]] = []

        if cmd == "/models":
            # Dynamic model name completions
            search = arg_prefix.lower()
            candidates = [
                (name, "")
                for name in self._model_names
                if not search or name.lower().startswith(search)
            ]
        elif cmd in STATIC_ARG_COMPLETIONS:
            search = arg_prefix.lower()
            candidates = [
                (arg, desc)
                for arg, desc in STATIC_ARG_COMPLETIONS[cmd]
                if not search or arg.lower().startswith(search)
            ]

        if not candidates:
            self.display = False
            return

        for arg, desc in candidates:
            label = f"{arg}  [dim]{desc}[/dim]" if desc else arg
            self.add_option(Option(label, id=arg))

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
                self._accept_completion(menu, submit=False)
                return
            elif event.key == "escape":
                event.stop()
                event.prevent_default()
                menu.hide()
                return
            elif event.key == "enter":
                event.stop()
                event.prevent_default()
                self._accept_completion(menu, submit=True)
                return

        if event.key == "enter":
            # Plain enter submits
            event.stop()
            event.prevent_default()
            if menu:
                menu.hide()
            self._submit()
        # shift+enter, ctrl+enter etc. will pass through and add newlines

    def _accept_completion(self, menu: CommandMenu, submit: bool) -> None:
        """Accept the currently highlighted completion.

        submit=True: fill in and submit immediately (Enter)
        submit=False: fill in and keep cursor for further typing (Tab)
        """
        highlighted = menu.highlighted
        if highlighted is None:
            menu.hide()
            if submit:
                self._submit()
            return

        option = menu.get_option_at_index(highlighted)
        value = option.id

        if menu._mode == "command":
            # Check if this command accepts args
            accepts_args = any(
                a for cmd, _, a in SLASH_COMMANDS if cmd == value
            )

            if submit:
                # Enter: submit the command directly
                self.clear()
                self.insert(value)
                menu.hide()
                self._submit()
            else:
                # Tab: fill in command, keep typing for args
                self.clear()
                self.insert(f"{value} ")
                menu.hide()
        else:
            # Arg mode — fill in the arg
            cmd = menu._current_cmd
            if submit:
                self.clear()
                self.insert(f"{cmd} {value}")
                menu.hide()
                self._submit()
            else:
                self.clear()
                self.insert(f"{cmd} {value} ")
                menu.hide()

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update command menu as text changes."""
        menu = self._get_command_menu()
        if menu is None:
            return

        text = self.text.strip()

        if not text.startswith("/"):
            menu.hide()
            return

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()

        if len(parts) == 1 and " " not in self.text:
            # Still typing the command name — show command completions
            menu.show_commands(text)
        elif len(parts) >= 1 and " " in self.text:
            # Command is complete, show arg completions
            arg_prefix = parts[1] if len(parts) > 1 else ""
            # Only show arg menu for commands that support it
            known_cmd = any(c for c, _, _ in SLASH_COMMANDS if c == cmd)
            if known_cmd:
                menu.show_args(cmd, arg_prefix)
            else:
                menu.hide()
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
