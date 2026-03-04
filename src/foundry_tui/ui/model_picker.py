"""Model picker with fuzzy search."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

from foundry_tui.models import Model, ModelCatalog, ModelCategory


class ModelOption(ListItem):
    """A selectable model option."""

    def __init__(self, model: Model, **kwargs):
        """Initialize the model option."""
        super().__init__(**kwargs)
        self.model = model

    def compose(self) -> ComposeResult:
        """Compose the model option."""
        # Category indicator
        if self.model.category.value == "reasoning":
            cat_badge = "[magenta]◆[/magenta]"
        else:
            cat_badge = "[cyan]●[/cyan]"

        # Build capability badges
        badges = []
        if self.model.capabilities.tools:
            badges.append("[green]tools[/green]")
        if self.model.capabilities.vision:
            badges.append("[blue]vision[/blue]")

        context_str = self._format_context(self.model.context_window)
        badges_str = " ".join(badges)

        yield Static(
            f" {cat_badge} {self.model.name:<24} "
            f"[dim]{self.model.provider:<10}[/dim] "
            f"[cyan]{context_str:<6}[/cyan] "
            f"{badges_str}",
            markup=True,
        )

    def _format_context(self, tokens: int) -> str:
        """Format context window size."""
        if tokens >= 1_000_000:
            return f"{tokens // 1_000_000}M"
        elif tokens >= 1_000:
            return f"{tokens // 1_000}k"
        return str(tokens)


class ProvisionOption(ListItem):
    """Placeholder for provisioning new models."""

    def compose(self) -> ComposeResult:
        """Compose the provision option."""
        yield Static(
            " [yellow]＋[/yellow] [dim italic]Deploy additional models...[/dim italic]",
            markup=True,
        )


class ModelsListView(ListView):
    """Custom ListView for models to avoid ID conflicts."""

    pass


class ModelPicker(ModalScreen):
    """Modal screen for selecting a model."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
    ]

    CSS = """
    ModelPicker {
        align: center middle;
    }

    .picker-container {
        width: 70;
        height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    .picker-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    .search-input {
        margin-bottom: 1;
    }

    ModelsListView {
        height: 1fr;
    }

    .picker-help {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: $primary 20%;
    }

    ListView:focus > ListItem.--highlight {
        background: $primary 40%;
    }
    """

    class ModelSelected(Message):
        """Model was selected."""

        def __init__(self, model: Model) -> None:
            """Initialize the message."""
            self.model = model
            super().__init__()

    class ProvisionRequested(Message):
        """User requested to provision a new model."""

        pass

    class Cancelled(Message):
        """Selection was cancelled."""

        pass

    def __init__(self, catalog: ModelCatalog, current_model: Model | None = None):
        """Initialize the model picker."""
        super().__init__()
        self.catalog = catalog
        self.current_model = current_model
        self.filtered_models: list[Model] = list(catalog.models)

    def compose(self) -> ComposeResult:
        """Compose the model picker."""
        with Vertical(classes="picker-container"):
            yield Label("Select Model", classes="picker-title")
            yield Input(placeholder="Type to filter...", classes="search-input")
            yield ModelsListView()
            yield Static(
                "[cyan]●[/cyan] Chat  [magenta]◆[/magenta] Reasoning  │  ↑↓ Navigate  Enter Select  Esc Cancel",
                classes="picker-help",
            )

    def on_mount(self) -> None:
        """Handle mount."""
        self._update_list()
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self._filter_models(event.value)
        self._update_list()

    def _filter_models(self, query: str) -> None:
        """Filter models based on query."""
        query = query.lower().strip()
        if not query:
            self.filtered_models = list(self.catalog.models)
            return

        self.filtered_models = []
        for model in self.catalog.models:
            # Fuzzy match against name, provider, and id
            searchable = f"{model.name} {model.provider} {model.id}".lower()
            if self._fuzzy_match(query, searchable):
                self.filtered_models.append(model)

    def _fuzzy_match(self, query: str, text: str) -> bool:
        """Simple fuzzy matching."""
        # All query characters must appear in order
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                query_idx += 1
        return query_idx == len(query)

    def _update_list(self) -> None:
        """Update the model list display."""
        list_view = self.query_one(ModelsListView)

        # Clear existing items
        list_view.clear()

        # Group models by category
        chat_models = [m for m in self.filtered_models if m.category == ModelCategory.CHAT]
        reasoning_models = [
            m for m in self.filtered_models if m.category == ModelCategory.REASONING
        ]

        # Chat models section
        for model in chat_models:
            list_view.append(ModelOption(model))

        # Reasoning models section
        for model in reasoning_models:
            list_view.append(ModelOption(model))

        # Provision option
        list_view.append(ProvisionOption())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        if isinstance(event.item, ModelOption):
            self.post_message(self.ModelSelected(event.item.model))
            self.dismiss()
        elif isinstance(event.item, ProvisionOption):
            self.post_message(self.ProvisionRequested())

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.post_message(self.Cancelled())
        self.dismiss()

    def action_select(self) -> None:
        """Select current item."""
        try:
            list_view = self.query_one(ModelsListView)
            if list_view.highlighted_child:
                list_view.action_select_cursor()
        except Exception:
            pass

    async def on_key(self, event) -> None:
        """Handle key events for navigation."""
        if event.key in ("down", "up"):
            try:
                list_view = self.query_one(ModelsListView)
                if event.key == "down":
                    list_view.action_cursor_down()
                elif event.key == "up":
                    list_view.action_cursor_up()
                event.stop()
            except Exception:
                pass
        elif event.key == "enter":
            # Handle selection directly
            event.stop()
            try:
                list_view = self.query_one(ModelsListView)
                highlighted = list_view.highlighted_child
                if isinstance(highlighted, ModelOption):
                    self.post_message(self.ModelSelected(highlighted.model))
                    self.dismiss()
                elif isinstance(highlighted, ProvisionOption):
                    self.post_message(self.ProvisionRequested())
            except Exception:
                pass
