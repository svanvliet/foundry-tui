"""Status bar component with animated spinner."""

from enum import Enum

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class ActivityState(str, Enum):
    """Activity states for the status bar."""

    READY = "ready"
    SENDING = "sending"
    THINKING = "thinking"
    STREAMING = "streaming"
    ERROR = "error"


# Braille spinner frames
SPINNER_FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]


class StatusBar(Horizontal):
    """Status bar showing model info, activity state, and token counts."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0 1;
        width: 100%;
    }

    StatusBar > Static {
        height: 1;
        width: auto;
    }

    StatusBar > #sb-activity {
        margin-left: 1;
    }

    StatusBar > #sb-tokens {
        margin-left: 1;
    }

    StatusBar > #sb-rpm {
        margin-left: 1;
    }

    StatusBar > #sb-provider {
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the status bar."""
        super().__init__(**kwargs)
        self._spinner_frame = 0
        self._model_name = "No model"
        self._model_category = "chat"
        self._provider = ""
        self._activity = ActivityState.READY
        self._custom_activity: str | None = None
        self._session_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._warning_threshold = 10000
        self._tool_count = 0
        self._rpm_limit: int = 0
        self._request_count: int = 0
        self._mounted = False

    def compose(self) -> ComposeResult:
        """Compose the status bar."""
        yield Static("[cyan]●[/cyan] No model", id="sb-model")
        yield Static("│ [green]✓[/green] Ready", id="sb-activity")
        yield Static("│ Session: 0 tokens", id="sb-tokens")
        yield Static("", id="sb-rpm")
        yield Static("", id="sb-tools")
        yield Static("", id="sb-provider")

    def on_mount(self) -> None:
        """Initialize after mount."""
        self._mounted = True
        self._refresh_all()
        # Start spinner timer
        self.set_interval(0.1, self._tick_spinner)

    def _tick_spinner(self) -> None:
        """Advance spinner and refresh activity if needed."""
        if self._activity not in (ActivityState.READY, ActivityState.ERROR):
            self._spinner_frame = (self._spinner_frame + 1) % len(SPINNER_FRAMES)
            self._refresh_activity()

    def _refresh_all(self) -> None:
        """Refresh all status bar sections."""
        if not self._mounted:
            return
        self._refresh_model()
        self._refresh_activity()
        self._refresh_tokens()
        self._refresh_rpm()
        self._refresh_tools()
        self._refresh_provider()

    def _refresh_model(self) -> None:
        """Refresh model display."""
        if not self._mounted:
            return
        icon = "●" if self._model_category == "chat" else "◆"
        color = "cyan" if self._model_category == "chat" else "magenta"
        self.query_one("#sb-model", Static).update(
            f"[{color}]{icon}[/{color}] {self._model_name}"
        )

    def _refresh_activity(self) -> None:
        """Refresh activity display."""
        if not self._mounted:
            return
        widget = self.query_one("#sb-activity", Static)

        if self._activity == ActivityState.READY:
            widget.update("│ [green]✓[/green] Ready")
        elif self._activity == ActivityState.ERROR:
            widget.update("│ [red]✗[/red] Error")
        else:
            spinner = SPINNER_FRAMES[self._spinner_frame]
            if self._custom_activity:
                state_text = self._custom_activity
            else:
                state_text = {
                    ActivityState.SENDING: "Sending...",
                    ActivityState.THINKING: "Thinking...",
                    ActivityState.STREAMING: "Receiving...",
                }.get(self._activity, "Working...")
            widget.update(f"│ [yellow]{spinner}[/yellow] {state_text}")

    def _refresh_tokens(self) -> None:
        """Refresh token count display with input/output breakdown."""
        if not self._mounted:
            return
        widget = self.query_one("#sb-tokens", Static)

        if self._session_tokens == 0:
            widget.update("│ Tokens: 0")
            return

        # Color based on threshold
        ratio = self._session_tokens / self._warning_threshold if self._warning_threshold > 0 else 0
        if ratio < 0.5:
            color = "green"
        elif ratio < 0.8:
            color = "yellow"
        else:
            color = "red"

        total = f"{self._session_tokens:,}"
        prompt = f"{self._prompt_tokens:,}"
        completion = f"{self._completion_tokens:,}"
        widget.update(f"│ Tokens: [{color}]{total}[/{color}] [dim](↑{prompt} ↓{completion})[/dim]")

    def _refresh_rpm(self) -> None:
        """Refresh RPM / request count display."""
        if not self._mounted:
            return
        widget = self.query_one("#sb-rpm", Static)
        if self._rpm_limit <= 0:
            widget.update("")
            return

        ratio = self._request_count / self._rpm_limit
        if ratio < 0.5:
            color = "green"
        elif ratio < 0.8:
            color = "yellow"
        else:
            color = "red"

        widget.update(f"│ RPM: [{color}]{self._request_count}[/{color}][dim]/{self._rpm_limit}[/dim]")

    def _refresh_provider(self) -> None:
        """Refresh provider display."""
        if not self._mounted:
            return
        widget = self.query_one("#sb-provider", Static)
        if self._provider:
            widget.update(f"│ [dim]{self._provider}[/dim]")
        else:
            widget.update("")

    def _refresh_tools(self) -> None:
        """Refresh tool count display."""
        if not self._mounted:
            return
        widget = self.query_one("#sb-tools", Static)
        if self._tool_count > 0:
            widget.update(f"│ 🔧 {self._tool_count}")
        else:
            widget.update("")

    # Public API
    def set_model(self, name: str, category: str = "chat", provider: str = "") -> None:
        """Set the current model info."""
        self._model_name = name
        self._model_category = category
        self._provider = provider
        self._refresh_model()
        self._refresh_provider()

    @property
    def session_tokens(self) -> int:
        return self._session_tokens

    @session_tokens.setter
    def session_tokens(self, value: int) -> None:
        self._session_tokens = value
        self._refresh_tokens()

    @property
    def warning_threshold(self) -> int:
        return self._warning_threshold

    @warning_threshold.setter
    def warning_threshold(self, value: int) -> None:
        self._warning_threshold = value

    def add_tokens(self, count: int, prompt: int = 0, completion: int = 0) -> None:
        """Add to the session token count with optional breakdown."""
        self._session_tokens += count
        self._prompt_tokens += prompt
        self._completion_tokens += completion
        self._refresh_tokens()

    def set_ready(self) -> None:
        """Set status to ready."""
        self._activity = ActivityState.READY
        self._custom_activity = None
        self._refresh_activity()

    def set_sending(self) -> None:
        """Set status to sending."""
        self._activity = ActivityState.SENDING
        self._custom_activity = None
        self._refresh_activity()

    def set_thinking(self) -> None:
        """Set status to thinking."""
        self._activity = ActivityState.THINKING
        self._custom_activity = None
        self._refresh_activity()

    def set_streaming(self) -> None:
        """Set status to streaming/receiving."""
        self._activity = ActivityState.STREAMING
        self._custom_activity = None
        self._refresh_activity()

    def set_error(self) -> None:
        """Set status to error (will auto-reset to ready)."""
        self._activity = ActivityState.ERROR
        self._custom_activity = None
        self._refresh_activity()
        # Auto-reset to ready after 2 seconds
        self.set_timer(2.0, self.set_ready)

    def update_activity(self, text: str) -> None:
        """Show custom activity text with a spinner (persists until state change)."""
        if not self._mounted:
            return
        self._custom_activity = text
        self._activity = ActivityState.THINKING  # Keep spinner running
        self._refresh_activity()

    def set_rpm_limit(self, limit: int) -> None:
        """Set the RPM limit for the current model."""
        self._rpm_limit = limit
        self._refresh_rpm()

    def increment_request_count(self) -> None:
        """Increment the request counter and refresh display."""
        self._request_count += 1
        self._refresh_rpm()

    def reset_request_count(self) -> None:
        """Reset the request counter."""
        self._request_count = 0
        self._refresh_rpm()

    def set_tool_count(self, count: int) -> None:
        """Set the number of active tools."""
        self._tool_count = count
        self._refresh_tools()
