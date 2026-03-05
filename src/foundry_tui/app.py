"""Main Foundry TUI application."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pyperclip
from textual.app import App, ComposeResult
from textual.widgets import Static

from foundry_tui.api.azure_openai import Message, ToolCall, ToolCallDelta, ToolCallFunction
from foundry_tui.api.client import ChatClient
from foundry_tui.config import Config
from foundry_tui.models import Model
from foundry_tui.storage.logger import get_logger, log_api_error, log_api_request, log_event, log_request_detail, log_token_usage
from foundry_tui.storage.conversations import (
    Conversation,
    generate_conversation_id,
    generate_title,
    load_conversation,
    save_conversation,
)
from foundry_tui.storage.persistence import (
    get_last_model_id,
    get_model_rate_limits,
    get_system_prompt,
    get_theme,
    set_last_model_id,
    set_system_prompt,
    set_theme,
)
from foundry_tui.storage.memory import load_memories, memory_count
from foundry_tui.tools import create_default_registry
from foundry_tui.tools.registry import ToolRegistry
from foundry_tui.ui.chat import ChatContainer, ChatLog, ChatMessage, StreamingMessage, ThinkingMessage, ToolCallMessage
from foundry_tui.ui.input import CommandMenu, InputContainer, MessageInput
from foundry_tui.ui.conversation_picker import ConversationPicker
from foundry_tui.ui.model_picker import ModelPicker
from foundry_tui.ui.status_bar import StatusBar


class FoundryApp(App):
    """The main Foundry TUI application."""

    TITLE = "Foundry TUI"
    CSS_PATH = Path(__file__).parent / "ui" / "styles.tcss"
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_screen", "Clear"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, config: Config):
        """Initialize the application."""
        super().__init__()
        self.theme = "nord"  # Set via reactive, not class variable
        self.config = config
        self.current_model = self._get_initial_model()
        self.messages: list[Message] = []
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.is_streaming = False
        self._current_streaming_message: StreamingMessage | None = None
        self._last_response: str = ""  # Store last assistant response for /copy
        self._system_prompt: str | None = get_system_prompt()
        self._conversation_id: str | None = None  # Current conversation ID for auto-save

        # Initialize unified API client
        self.client = ChatClient(config=config)

        # Initialize tool registry and embedding client
        self.tool_registry, self._embedding_client = create_default_registry(
            source_model=self.current_model.id
        )

        # Max tool loop iterations to prevent runaway loops
        self._max_tool_iterations = 10

        # Initialize logger
        self.logger = get_logger()
        log_event("App initialized", model=self.current_model.name)

    def _get_initial_model(self) -> Model:
        """Get the initial model (last used or default)."""
        last_model_id = get_last_model_id()
        if last_model_id:
            model = self.config.catalog.get_model(last_model_id)
            if model:
                return model
        return self.config.default_model

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield ChatContainer()
        yield CommandMenu()
        yield InputContainer()
        yield StatusBar()

    def _update_memory_count(self) -> None:
        """Refresh the memory count in the status bar."""
        self.query_one(StatusBar).set_memory_count(memory_count())

    async def _backfill_embeddings(self) -> None:
        """Embed any memories that don't have embeddings yet. Runs on startup."""
        from foundry_tui.storage.memory import load_embeddings, save_embedding

        if not self._embedding_client:
            return

        if not await self._embedding_client.is_available():
            return

        memories = load_memories()
        embeddings = load_embeddings()
        missing = [m for m in memories if m.id not in embeddings]

        if not missing:
            return

        log_event("Backfilling embeddings", count=len(missing))
        for mem in missing:
            try:
                vec = await self._embedding_client.embed(mem.content)
                save_embedding(mem.id, vec)
            except Exception:
                break  # stop on first failure (rate limit, etc.)

    def _update_status_bar_model(self) -> None:
        """Update status bar with current model info."""
        status_bar = self.query_one(StatusBar)
        status_bar.set_model(
            name=self.current_model.name,
            category=self.current_model.category.value,
            provider=self.current_model.provider,
        )
        status_bar.warning_threshold = self.config.settings.cost_warning_threshold
        # Update RPM limit from persisted config or catalog defaults
        limits = get_model_rate_limits(self.current_model.id)
        if limits:
            status_bar.set_rpm_limit(limits["rpm"])
        elif self.current_model.rate_limits:
            status_bar.set_rpm_limit(self.current_model.rate_limits.rpm_per_unit * 1)
        else:
            status_bar.set_rpm_limit(0)
        # Update tool count based on model capabilities
        if self.current_model.capabilities.tools and not self.tool_registry.is_empty():
            status_bar.set_tool_count(len(self.tool_registry.tool_names))
        else:
            status_bar.set_tool_count(0)
        # Update memory count
        status_bar.set_memory_count(memory_count())

    def on_mount(self) -> None:
        """Handle app mount."""
        # Apply saved theme
        saved_theme = get_theme()
        if saved_theme:
            self.theme = saved_theme

        # Set initial status
        self._update_status_bar_model()

        # Populate command menu with model names for /models completion
        cmd_menu = self.query_one(CommandMenu)
        cmd_menu.set_model_names([m.id for m in self.config.catalog.models])

        # Backfill embeddings for existing memories (non-blocking)
        if self._embedding_client:
            self.run_worker(self._backfill_embeddings(), exclusive=False)

        # Show welcome message
        chat_log = self.query_one(ChatLog)
        system_info = ""
        if self._system_prompt:
            preview = self._system_prompt[:50] + "..." if len(self._system_prompt) > 50 else self._system_prompt
            system_info = f"\nSystem prompt: [dim]{preview}[/dim]"
        tools_info = ""
        if not self.tool_registry.is_empty():
            count = len(self.tool_registry.tool_names)
            names = ", ".join(self.tool_registry.tool_names)
            tools_info = f"\n🔧 Tools: [dim]{names}[/dim] ({count} active)"
        welcome = Static(
            f"Welcome to Foundry TUI!\n\n"
            f"Current model: [bold]{self.current_model.name}[/bold] ({self.current_model.provider})"
            f"{system_info}{tools_info}\n"
            f"Type a message and press Enter to chat.\n"
            f"Commands: /models, /system, /tools, /load, /new, /clear, /copy, /export, /help, /quit",
            id="welcome",
        )
        chat_log.mount(welcome)

        # Focus the input
        self.query_one(MessageInput).focus()

    async def on_message_input_submitted(self, event: MessageInput.Submitted) -> None:
        """Handle message submission."""
        text = event.value

        # Handle commands
        if text.startswith("/"):
            await self._handle_command(text)
            return

        # Add user message to chat
        await self._add_message("user", text)

        # Send to API and stream response (run as background worker
        # so the event loop stays responsive for Ctrl+C, Escape, etc.)
        self.run_worker(self._send_message(text), exclusive=True)

    async def _handle_command(self, command: str) -> None:
        """Handle slash commands."""
        cmd_parts = command.strip().split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        log_event("Command", command=cmd)

        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd in ("/clear", "/c"):
            await self._clear_chat()
        elif cmd in ("/new", "/n"):
            await self._new_conversation()
        elif cmd in ("/models", "/m", "/model"):
            if args:
                await self._switch_model_by_name(args)
            else:
                await self._show_model_picker()
        elif cmd in ("/copy",):
            await self._copy_last_response()
        elif cmd in ("/export",):
            await self._export_conversation(args)
        elif cmd in ("/system", "/sys"):
            await self._handle_system_prompt(args)
        elif cmd in ("/conversations", "/convs", "/load"):
            await self._show_conversation_picker()
        elif cmd in ("/save",):
            await self._save_current_conversation(args)
        elif cmd in ("/tools", "/tool"):
            await self._handle_tools_command(args)
        elif cmd in ("/memory", "/mem"):
            await self._handle_memory_command(args)
        elif cmd in ("/theme",):
            await self._handle_theme_command(args)
        elif cmd in ("/help", "/h", "/?"):
            await self._show_help()
        else:
            await self._add_message("error", f"Unknown command: {command}")

    async def _clear_chat(self) -> None:
        """Clear the chat history."""
        self.messages.clear()
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self._last_response = ""

        chat_log = self.query_one(ChatLog)
        await chat_log.remove_children()

        # Reset token counter in status bar
        status_bar = self.query_one(StatusBar)
        status_bar.session_tokens = 0
        status_bar._prompt_tokens = 0
        status_bar._completion_tokens = 0
        status_bar._refresh_tokens()
        status_bar.reset_request_count()

        await self._add_message("system", "Chat cleared.")

    async def _new_conversation(self) -> None:
        """Start a new conversation."""
        # Auto-save current conversation before starting new one
        if self.messages:
            self._auto_save_conversation()

        self.messages.clear()
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self._last_response = ""
        self._conversation_id = None  # Reset conversation ID

        chat_log = self.query_one(ChatLog)
        await chat_log.remove_children()

        # Reset token counter in status bar
        status_bar = self.query_one(StatusBar)
        status_bar.session_tokens = 0
        status_bar._prompt_tokens = 0
        status_bar._completion_tokens = 0
        status_bar._refresh_tokens()
        status_bar.reset_request_count()

        await self._add_message(
            "system",
            f"New conversation started with [bold]{self.current_model.name}[/bold].",
        )

    async def _show_model_picker(self) -> None:
        """Show the model picker."""
        picker = ModelPicker(self.config.catalog, self.current_model)
        await self.push_screen(picker)

    async def _switch_model_by_name(self, name: str) -> None:
        """Switch to a model by ID or name."""
        name = name.strip().lower()
        model = self.config.catalog.get_model(name)
        if not model:
            # Fuzzy match on display name
            for m in self.config.catalog.models:
                if name in m.name.lower() or name in m.id.lower():
                    model = m
                    break
        if not model:
            await self._add_message("error", f"Unknown model: {name}")
            return

        old_model = self.current_model
        self.current_model = model
        set_last_model_id(model.id)
        self._update_status_bar_model()

        if old_model.id != model.id:
            log_event("Model changed", old=old_model.id, new=model.id)
            await self._add_message(
                "system",
                f"Switched to [bold]{model.name}[/bold] ({model.provider})",
            )

    async def _copy_last_response(self) -> None:
        """Copy the last assistant response to clipboard."""
        if not self._last_response:
            await self._add_message("system", "No response to copy.")
            return

        try:
            pyperclip.copy(self._last_response)
            # Show truncated preview
            preview = self._last_response[:100]
            if len(self._last_response) > 100:
                preview += "..."
            await self._add_message(
                "system", f"Copied to clipboard ({len(self._last_response)} chars)"
            )
            log_event("Copied to clipboard", chars=len(self._last_response))
        except Exception as e:
            await self._add_message("error", f"Failed to copy: {e}")

    async def _export_conversation(self, filename: str = "") -> None:
        """Export the conversation to a JSON file."""
        if not self.messages:
            await self._add_message("system", "No conversation to export.")
            return

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_id = self.current_model.id.replace(".", "-")
            filename = f"conversation_{timestamp}_{model_id}.json"

        # Ensure .json extension
        if not filename.endswith(".json"):
            filename += ".json"

        # Export to current directory or specified path
        export_path = Path(filename)

        try:
            conversation = {
                "id": f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "created_at": datetime.now().isoformat(),
                "model_id": self.current_model.id,
                "model_name": self.current_model.name,
                "provider": self.current_model.provider,
                "messages": [{"role": m.role, "content": m.content} for m in self.messages],
                "metadata": {
                    "total_messages": len(self.messages),
                    "exported_by": "foundry-tui",
                },
            }

            with open(export_path, "w") as f:
                json.dump(conversation, f, indent=2)

            await self._add_message(
                "system", f"Conversation exported to [bold]{export_path}[/bold]"
            )
            log_event("Exported conversation", path=str(export_path))

        except Exception as e:
            await self._add_message("error", f"Failed to export: {e}")

    async def _handle_system_prompt(self, args: str) -> None:
        """Handle /system command."""
        args = args.strip()

        if not args:
            # Show current system prompt
            if self._system_prompt:
                await self._add_message(
                    "system",
                    f"[bold]Current system prompt:[/bold]\n\n{self._system_prompt}",
                )
            else:
                await self._add_message(
                    "system",
                    "No system prompt set. Use [bold]/system <prompt>[/bold] to set one.",
                )
        elif args.lower() == "clear":
            # Clear system prompt
            self._system_prompt = None
            set_system_prompt(None)
            await self._add_message("system", "System prompt cleared.")
            log_event("System prompt cleared")
        else:
            # Set new system prompt
            self._system_prompt = args
            set_system_prompt(args)
            # Show truncated preview
            preview = args[:100] + "..." if len(args) > 100 else args
            await self._add_message(
                "system",
                f"System prompt set ({len(args)} chars):\n\n[dim]{preview}[/dim]",
            )
            log_event("System prompt set", length=len(args))

    async def _show_conversation_picker(self) -> None:
        """Show the conversation picker."""
        picker = ConversationPicker()
        await self.push_screen(picker)

    async def _save_current_conversation(self, title: str = "") -> None:
        """Manually save the current conversation with optional title."""
        if not self.messages:
            await self._add_message("system", "No conversation to save.")
            return

        self._auto_save_conversation(title.strip() if title else None)
        await self._add_message(
            "system",
            f"Conversation saved. Use [bold]/load[/bold] to browse saved conversations.",
        )

    def _auto_save_conversation(self, custom_title: str | None = None) -> None:
        """Auto-save the current conversation."""
        if not self.messages:
            return

        from datetime import datetime

        now = datetime.now()

        # Generate or reuse conversation ID
        if not self._conversation_id:
            self._conversation_id = generate_conversation_id()

        # Generate title from first user message if not provided
        messages_dict = [m.to_api_dict() for m in self.messages]
        title = custom_title or generate_title(messages_dict)

        # Create conversation object
        conversation = Conversation(
            id=self._conversation_id,
            title=title,
            model_id=self.current_model.id,
            model_name=self.current_model.name,
            provider=self.current_model.provider,
            system_prompt=self._system_prompt,
            messages=messages_dict,
            created_at=now,  # Will be overwritten if loading existing
            updated_at=now,
            metadata={
                "total_tokens": self.total_tokens,
            },
        )

        # Try to preserve original created_at if this is an existing conversation
        existing = load_conversation(self._conversation_id)
        if existing:
            conversation.created_at = existing.created_at

        save_conversation(conversation)
        log_event("Conversation auto-saved", id=self._conversation_id)

    async def _load_conversation(self, conversation_id: str) -> None:
        """Load a conversation by ID."""
        conversation = load_conversation(conversation_id)
        if not conversation:
            await self._add_message("error", f"Conversation not found: {conversation_id}")
            return

        # Auto-save current conversation before loading
        if self.messages:
            self._auto_save_conversation()

        # Clear current state
        self.messages.clear()
        self.total_tokens = 0
        self._last_response = ""

        chat_log = self.query_one(ChatLog)
        await chat_log.remove_children()

        # Load conversation state
        self._conversation_id = conversation.id
        self._system_prompt = conversation.system_prompt

        # Try to switch to the conversation's model
        model = self.config.catalog.get_model(conversation.model_id)
        if model:
            self.current_model = model
            self._update_status_bar_model()

        # Restore messages
        for msg in conversation.messages:
            role = msg["role"]
            content = msg.get("content") or ""
            tool_call_id = msg.get("tool_call_id")
            name = msg.get("name")

            # Restore tool_calls if present
            restored_tool_calls = None
            if msg.get("tool_calls"):
                restored_tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        type=tc.get("type", "function"),
                        function=ToolCallFunction(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        ),
                    )
                    for tc in msg["tool_calls"]
                ]

            self.messages.append(Message(
                role=role,
                content=content,
                tool_calls=restored_tool_calls,
                tool_call_id=tool_call_id,
                name=name,
            ))

            # Render in the UI
            if role == "tool":
                # Show tool results as collapsible blocks
                chat_log = self.query_one(ChatLog)
                tc_widget = ToolCallMessage(
                    tool_name=name or "tool",
                    arguments="{}",
                    result=content,
                )
                await chat_log.mount(tc_widget)
            elif role == "assistant" and restored_tool_calls:
                # Assistant message with tool calls (no text to show) — skip display
                pass
            elif content:
                await self._add_message(role, content)

        # Find last assistant response for /copy
        for msg in reversed(conversation.messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                self._last_response = msg["content"]
                break

        # Restore token count if available
        if "total_tokens" in conversation.metadata:
            self.total_tokens = conversation.metadata["total_tokens"]
            status_bar = self.query_one(StatusBar)
            status_bar.session_tokens = self.total_tokens

        await self._add_message(
            "system",
            f"Loaded conversation: [bold]{conversation.title}[/bold]\n"
            f"Model: {conversation.model_name} · {len(conversation.messages)} messages",
        )
        log_event("Conversation loaded", id=conversation_id)

    async def on_conversation_picker_conversation_selected(
        self, event: ConversationPicker.ConversationSelected
    ) -> None:
        """Handle conversation selection."""
        await self._load_conversation(event.conversation_id)
        self.query_one(MessageInput).focus()

    async def on_conversation_picker_cancelled(
        self, event: ConversationPicker.Cancelled
    ) -> None:
        """Handle conversation picker cancellation."""
        self.query_one(MessageInput).focus()

    async def on_model_picker_model_selected(self, event: ModelPicker.ModelSelected) -> None:
        """Handle model selection."""
        old_model = self.current_model
        self.current_model = event.model

        # Save to persistence
        set_last_model_id(event.model.id)

        # Update memory tool source model
        save_tool = self.tool_registry.get("save_memory")
        if save_tool and hasattr(save_tool, "set_source_model"):
            save_tool.set_source_model(event.model.id)

        # Update status bar
        self._update_status_bar_model()

        # Notify user
        if old_model.id != event.model.id:
            log_event("Model changed", old=old_model.id, new=event.model.id)
            await self._add_message(
                "system",
                f"Switched to [bold]{event.model.name}[/bold] ({event.model.provider})",
            )

        # Focus input
        self.query_one(MessageInput).focus()

    async def on_model_picker_provision_requested(
        self, event: ModelPicker.ProvisionRequested
    ) -> None:
        """Handle provision request."""
        await self._add_message(
            "system",
            "[yellow]Model provisioning is not yet implemented.[/yellow]\n"
            "Use the Azure portal to deploy additional models.",
        )
        self.query_one(MessageInput).focus()

    async def on_model_picker_cancelled(self, event: ModelPicker.Cancelled) -> None:
        """Handle picker cancellation."""
        self.query_one(MessageInput).focus()

    async def _handle_tools_command(self, args: str) -> None:
        """Handle the /tools command."""
        if not args:
            # List all tools
            if self.tool_registry.is_empty():
                await self._add_message("system", "No tools configured.\n\nSet TAVILY_API_KEY in .env for web search,\nor add custom tools to ~/.foundry-tui/tools.json")
                return

            supports_tools = self.current_model.capabilities.tools
            lines = ["[bold]Registered Tools:[/bold]\n"]
            for name in self.tool_registry.tool_names:
                tool = self.tool_registry.get(name)
                status = "[green]active[/green]" if supports_tools else "[dim]model doesn't support tools[/dim]"
                lines.append(f"  🔧 {name} — {tool.description[:60]}")
                lines.append(f"     Status: {status}")
            lines.append(f"\nModel: {self.current_model.name} (tools: {'✓' if supports_tools else '✗'})")
            await self._add_message("system", "\n".join(lines))

        elif args.startswith("info "):
            tool_name = args[5:].strip()
            tool = self.tool_registry.get(tool_name)
            if not tool:
                await self._add_message("error", f"Unknown tool: {tool_name}")
                return
            import json
            schema = json.dumps(tool.parameters, indent=2)
            await self._add_message("system", f"[bold]{tool.name}[/bold]\n\n{tool.description}\n\nParameters:\n{schema}")
        else:
            await self._add_message("error", "Usage: /tools, /tools info <name>")

    async def _handle_memory_command(self, args: str) -> None:
        """Handle the /memory command."""
        from foundry_tui.storage.memory import (
            clear_embeddings,
            clear_memories,
            delete_embedding as delete_emb,
            delete_memory as delete_mem,
            load_memories as load_mems,
            search_memories as search_mems,
        )

        if not args:
            # List all memories
            memories = load_mems()
            if not memories:
                await self._add_message("system", "No memories stored. Models will save memories as they learn about you.")
                return
            lines = [f"[bold]Stored Memories ({len(memories)}):[/bold]\n"]
            for m in memories:
                preview = m.content[:80] + "…" if len(m.content) > 80 else m.content
                lines.append(f"  [dim]{m.id}[/dim] ({m.source_model})")
                lines.append(f"    {preview}\n")
            lines.append("[dim]Use /memory delete <id> or /memory clear[/dim]")
            await self._add_message("system", "\n".join(lines))
            return

        sub_parts = args.strip().split(maxsplit=1)
        sub_cmd = sub_parts[0].lower()
        sub_args = sub_parts[1] if len(sub_parts) > 1 else ""

        if sub_cmd == "search" and sub_args:
            results = search_mems(sub_args)
            if not results:
                await self._add_message("system", f"No memories matching: {sub_args}")
            else:
                lines = [f"[bold]Search results for '{sub_args}' ({len(results)}):[/bold]\n"]
                for m in results:
                    lines.append(f"  [dim]{m.id}[/dim] ({m.source_model})")
                    lines.append(f"    {m.content}\n")
                await self._add_message("system", "\n".join(lines))

        elif sub_cmd == "delete" and sub_args:
            mem_id = sub_args.strip()
            if delete_mem(mem_id):
                delete_emb(mem_id)
                await self._add_message("system", f"Memory [bold]{mem_id}[/bold] deleted.")
                self._update_memory_count()
            else:
                await self._add_message("error", f"Memory not found: {mem_id}")

        elif sub_cmd == "clear":
            count = clear_memories()
            clear_embeddings()
            if count > 0:
                await self._add_message("system", f"Cleared [bold]{count}[/bold] memories.")
                self._update_memory_count()
            else:
                await self._add_message("system", "No memories to clear.")

        else:
            await self._add_message("error", "Usage: /memory, /memory search <query>, /memory delete <id>, /memory clear")

    async def _handle_theme_command(self, args: str) -> None:
        """Handle the /theme command."""
        available = sorted(self.available_themes)

        if not args:
            lines = [f"[bold]Current theme:[/bold] {self.theme}\n"]
            lines.append("[bold]Available themes:[/bold]\n")
            for name in available:
                marker = " [green]◀[/green]" if name == self.theme else ""
                lines.append(f"  {name}{marker}")
            lines.append("\nUsage: /theme <name>")
            await self._add_message("system", "\n".join(lines))
            return

        name = args.strip().lower()
        if name not in available:
            await self._add_message("error", f"Unknown theme: {name}\nUse /theme to see available themes.")
            return

        self.theme = name
        set_theme(name)
        await self._add_message("system", f"Theme changed to [bold]{name}[/bold].")

    async def _show_help(self) -> None:
        """Show help message."""
        help_text = (
            "[bold]Available Commands:[/bold]\n\n"
            "  /models, /m       - Select a different model\n"
            "  /system [prompt]  - View/set system prompt (/system clear to remove)\n"
            "  /tools            - List registered tools (/tools info <name> for details)\n"
            "  /memory           - List memories (/memory search, /memory delete, /memory clear)\n"
            "  /theme [name]     - View/change color theme\n"
            "  /load, /convs     - Browse and load saved conversations\n"
            "  /save [title]     - Save current conversation with optional title\n"
            "  /new, /n          - Start a new conversation\n"
            "  /clear, /c        - Clear chat history\n"
            "  /copy             - Copy last response to clipboard\n"
            "  /export [file]    - Export conversation to JSON\n"
            "  /help, /h, /?     - Show this help message\n"
            "  /quit, /exit, /q  - Exit the application\n\n"
            "[bold]Keyboard Shortcuts:[/bold]\n\n"
            "  Enter       - Send message\n"
            "  Shift+Enter - New line\n"
            "  Ctrl+C      - Quit\n"
            "  Ctrl+L      - Clear screen\n"
            "  Escape      - Cancel / Close picker\n\n"
            "[dim]Conversations are auto-saved after each response.[/dim]"
        )
        await self._add_message("system", help_text)

    async def _add_message(self, role: str, content: str) -> None:
        """Add a message to the chat log."""
        # Remove welcome message if present
        try:
            welcome = self.query_one("#welcome")
            await welcome.remove()
        except Exception:
            pass

        chat_log = self.query_one(ChatLog)
        message = ChatMessage(content, role)
        await chat_log.mount(message)

        # Scroll to bottom
        chat_container = self.query_one(ChatContainer)
        chat_container.scroll_to_bottom()

    async def _start_streaming_message(self) -> StreamingMessage:
        """Start a new streaming message."""
        # Remove welcome message if present
        try:
            welcome = self.query_one("#welcome")
            await welcome.remove()
        except Exception:
            pass

        chat_log = self.query_one(ChatLog)
        message = StreamingMessage()
        await chat_log.mount(message)

        self._current_streaming_message = message
        return message

    def _get_tool_definitions(self) -> list[dict] | None:
        """Get tool definitions if tools are available and model supports them."""
        if self.tool_registry.is_empty():
            return None
        if not self.current_model.capabilities.tools:
            return None
        return self.tool_registry.get_definitions()

    async def _build_system_prompt(self, user_message: str = "") -> str | None:
        """Build the system prompt with memory injection.

        Uses smart injection (top-5 by relevance) when >10 memories
        and embeddings are available. Otherwise injects all memories.
        """
        from foundry_tui.storage.memory import semantic_search

        parts: list[str] = []

        if self._system_prompt:
            parts.append(self._system_prompt)

        # Inject memories
        all_memories = load_memories()
        use_semantic = (
            self._embedding_client is not None
            and len(all_memories) > 10
            and user_message
        )

        if use_semantic:
            try:
                memories = await semantic_search(
                    user_message, self._embedding_client, top_k=5
                )
                log_event(
                    "Smart memory injection",
                    injected=len(memories),
                    total=len(all_memories),
                )
            except Exception:
                memories = all_memories
        else:
            memories = all_memories

        if memories:
            memory_lines = [
                "\n## Your memories about the user",
                "You have saved the following memories about the user. "
                "Use them to personalize responses.",
                "When you learn something new and important about the user, "
                "use save_memory to remember it.\n",
            ]
            for m in memories:
                memory_lines.append(f"- {m.content}")
            parts.append("\n".join(memory_lines))
        else:
            parts.append(
                "\nYou have no saved memories about the user yet. "
                "When you learn useful facts about the user (name, preferences, "
                "role, projects, etc.), use the save_memory tool to remember them "
                "for future conversations."
            )

        return "\n\n".join(parts) if parts else None

    def _assemble_tool_calls(self, deltas: list[ToolCallDelta]) -> list[ToolCall]:
        """Accumulate streaming tool call deltas into complete ToolCall objects."""
        calls: dict[int, dict] = {}
        for d in deltas:
            if d.index not in calls:
                calls[d.index] = {"id": "", "type": "function", "name": "", "arguments": ""}
            entry = calls[d.index]
            if d.id:
                entry["id"] = d.id
            if d.type:
                entry["type"] = d.type
            if d.function_name:
                entry["name"] += d.function_name
            if d.function_arguments:
                entry["arguments"] += d.function_arguments

        return [
            ToolCall(
                id=entry["id"],
                type=entry["type"],
                function=ToolCallFunction(name=entry["name"], arguments=entry["arguments"]),
            )
            for entry in sorted(calls.values(), key=lambda e: list(calls.keys())[list(calls.values()).index(e)])
        ]

    async def _send_message(self, text: str) -> None:
        """Send a message to the API and stream the response.

        Implements the tool calling loop: if the model returns tool_calls,
        execute each tool, append results, and call the API again until
        the model produces a final text response.
        """
        if self.is_streaming:
            return  # Prevent double-sends

        # Add to message history
        self.messages.append(Message(role="user", content=text))

        # Build messages for API (include system prompt + memories)
        api_messages: list[Message] = []
        system_content = await self._build_system_prompt(user_message=text)
        if system_content:
            api_messages.append(Message(role="system", content=system_content))
        api_messages.extend(self.messages)

        # Get tool definitions
        tool_defs = self._get_tool_definitions()

        # Update status - sending request
        status_bar = self.query_one(StatusBar)
        status_bar.set_sending()
        self.is_streaming = True

        try:
            import re

            iteration = 0
            max_429_retries = 3
            while iteration < self._max_tool_iterations:
                iteration += 1

                # Log full request detail for every API call (including tool-loop re-calls)
                log_request_detail(
                    self.current_model.id,
                    [m.to_api_dict() for m in api_messages],
                    tool_defs=tool_defs,
                )
                status_bar.increment_request_count()

                # Start streaming message
                streaming_msg = await self._start_streaming_message()
                status_bar.set_thinking()

                # Stream the response with 429 retry (separate from tool iteration count)
                full_response = ""
                chunk_count = 0
                first_chunk = True
                all_tc_deltas: list[ToolCallDelta] = []
                stream_usage = None  # Will be set from the final chunk
                rate_limit_retries = 0

                # Thinking tag parser state
                thinking_msg: ThinkingMessage | None = None
                in_thinking = False
                thinking_buffer = ""  # Buffer to detect <think> and </think> tags

                while True:
                    try:
                        async for chunk in self.client.stream_chat(
                            model=self.current_model,
                            messages=api_messages,
                            tools=tool_defs,
                        ):
                            if not self.is_streaming:
                                return  # Cancelled by user

                            if chunk.content:
                                if first_chunk:
                                    status_bar.set_streaming()
                                    first_chunk = False

                                full_response += chunk.content

                                # Parse <think>...</think> tags from streaming content
                                text_to_process = thinking_buffer + chunk.content
                                thinking_buffer = ""

                                while text_to_process:
                                    if in_thinking:
                                        # Look for </think> closing tag
                                        close_idx = text_to_process.find("</think>")
                                        if close_idx != -1:
                                            # Emit thinking content up to the tag
                                            if thinking_msg and close_idx > 0:
                                                thinking_msg.append(text_to_process[:close_idx])
                                            if thinking_msg:
                                                thinking_msg.finalize()
                                            in_thinking = False
                                            text_to_process = text_to_process[close_idx + 8:]
                                        elif text_to_process.endswith("<") or text_to_process.endswith("</") or text_to_process.endswith("</t") or text_to_process.endswith("</th") or text_to_process.endswith("</thi") or text_to_process.endswith("</thin") or text_to_process.endswith("</think"):
                                            # Might be a partial </think> tag — buffer it
                                            partial_start = max(text_to_process.rfind("<"), 0)
                                            if thinking_msg and partial_start > 0:
                                                thinking_msg.append(text_to_process[:partial_start])
                                            thinking_buffer = text_to_process[partial_start:]
                                            text_to_process = ""
                                        else:
                                            # All thinking content
                                            if thinking_msg:
                                                thinking_msg.append(text_to_process)
                                            text_to_process = ""
                                    else:
                                        # Look for <think> opening tag
                                        open_idx = text_to_process.find("<think>")
                                        if open_idx != -1:
                                            # Emit any regular content before the tag
                                            if open_idx > 0:
                                                streaming_msg.append(text_to_process[:open_idx])
                                            # Create thinking widget
                                            in_thinking = True
                                            thinking_msg = ThinkingMessage()
                                            chat_log = self.query_one(ChatLog)
                                            await chat_log.mount(thinking_msg, before=streaming_msg)
                                            status_bar.update_activity("💭 Reasoning...")
                                            text_to_process = text_to_process[open_idx + 7:]
                                        elif text_to_process.endswith("<") or text_to_process.endswith("<t") or text_to_process.endswith("<th") or text_to_process.endswith("<thi") or text_to_process.endswith("<thin") or text_to_process.endswith("<think"):
                                            # Might be a partial <think> tag — buffer it
                                            partial_start = text_to_process.rfind("<")
                                            if partial_start > 0:
                                                streaming_msg.append(text_to_process[:partial_start])
                                            thinking_buffer = text_to_process[partial_start:]
                                            text_to_process = ""
                                        else:
                                            # All regular content
                                            streaming_msg.append(text_to_process)
                                            text_to_process = ""

                                chunk_count += 1
                                if chunk_count % 3 == 0:
                                    if thinking_msg and in_thinking:
                                        thinking_msg.flush()
                                    streaming_msg.flush()
                                    chat_container = self.query_one(ChatContainer)
                                    chat_container.scroll_to_bottom()
                                    await asyncio.sleep(0)

                            if chunk.tool_calls:
                                all_tc_deltas.extend(chunk.tool_calls)

                            if chunk.usage:
                                stream_usage = chunk.usage

                        # Flush any remaining thinking buffer as regular content
                        if thinking_buffer:
                            if in_thinking and thinking_msg:
                                thinking_msg.append(thinking_buffer)
                                thinking_msg.finalize()
                            else:
                                streaming_msg.append(thinking_buffer)
                            thinking_buffer = ""

                        break  # Stream completed successfully
                    except Exception as rate_err:
                        error_str = str(rate_err)
                        if "429" in error_str and rate_limit_retries < max_429_retries:
                            rate_limit_retries += 1

                            # Log at ERROR level first with full message
                            log_api_error(self.current_model.id, rate_err)

                            # Parse retry-after from error message
                            retry_match = re.search(r"retry after (\d+) second", error_str, re.IGNORECASE)
                            wait_secs = int(retry_match.group(1)) if retry_match else 15
                            wait_secs = min(wait_secs, 90)

                            log_event(
                                "Rate limited (429) — will retry",
                                model=self.current_model.id,
                                retry_after=wait_secs,
                                attempt=f"{rate_limit_retries}/{max_429_retries}",
                                iteration=iteration,
                            )

                            # Remove the empty streaming message for a clean retry
                            try:
                                await streaming_msg.remove()
                            except Exception:
                                pass

                            # Show countdown in status bar, checking for cancellation
                            for remaining in range(wait_secs, 0, -1):
                                if not self.is_streaming:
                                    return  # User quit or cancelled
                                status_bar.update_activity(
                                    f"⏳ Rate limited — retrying in {remaining}s ({rate_limit_retries}/{max_429_retries})"
                                )
                                await asyncio.sleep(1)

                            if not self.is_streaming:
                                return

                            # Reset for retry (new streaming message, etc.)
                            streaming_msg = await self._start_streaming_message()
                            status_bar.set_sending()
                            full_response = ""
                            chunk_count = 0
                            first_chunk = True
                            all_tc_deltas = []
                            stream_usage = None
                            thinking_msg = None
                            in_thinking = False
                            thinking_buffer = ""
                            continue  # Retry within the inner while loop

                        elif "429" in error_str:
                            # Exhausted retries — log and show error to user
                            log_api_error(self.current_model.id, rate_err)
                            log_event(
                                "Rate limit retries exhausted",
                                model=self.current_model.id,
                                attempts=rate_limit_retries,
                            )
                            try:
                                await streaming_msg.remove()
                            except Exception:
                                pass
                            await self._add_message(
                                "error",
                                f"Rate limited after {rate_limit_retries} retries. "
                                f"Try again in a minute or switch to a model with higher RPM.",
                            )
                            status_bar.set_error()
                            return  # Exit _send_message entirely
                        else:
                            raise  # Re-raise non-429 errors

                # Flush remaining content
                streaming_msg.flush()
                chat_container = self.query_one(ChatContainer)
                chat_container.scroll_to_bottom()

                # Did the model request tool calls?
                if all_tc_deltas:
                    tool_calls = self._assemble_tool_calls(all_tc_deltas)

                    # Remove the streaming message (it may have partial/empty content)
                    if not full_response.strip():
                        await streaming_msg.remove()
                    else:
                        streaming_msg.finalize()

                    # Add assistant message with tool_calls to history
                    assistant_msg = Message(
                        role="assistant",
                        content=full_response or None,
                        tool_calls=tool_calls,
                    )
                    self.messages.append(assistant_msg)
                    api_messages.append(assistant_msg)

                    # Execute each tool call
                    chat_log = self.query_one(ChatLog)
                    for tc in tool_calls:
                        log_event("Tool call", tool=tc.function.name, arguments=tc.function.arguments[:200])

                        # Show collapsible tool call in UI
                        tc_widget = ToolCallMessage(
                            tool_name=tc.function.name,
                            arguments=tc.function.arguments,
                        )
                        await chat_log.mount(tc_widget)
                        chat_container.scroll_to_bottom()

                        # Update status
                        status_bar.update_activity(f"⚡ {tc.function.name}")

                        # Execute the tool
                        result = await self.tool_registry.execute(tc.function.name, tc.function.arguments)

                        # Update the widget with the result
                        tc_widget.set_result(result.content, error=result.error)

                        log_event(
                            "Tool result",
                            tool=tc.function.name,
                            error=result.error,
                            result_len=len(result.content),
                        )

                        # Refresh memory count if a memory tool was used
                        if tc.function.name in ("save_memory", "forget_memory"):
                            self._update_memory_count()

                        # Add tool result to message history
                        tool_msg = Message(
                            role="tool",
                            content=result.content,
                            tool_call_id=tc.id,
                            name=tc.function.name,
                        )
                        self.messages.append(tool_msg)
                        api_messages.append(tool_msg)

                    # Loop back to call the API again with tool results
                    status_bar.set_sending()
                    continue

                # No tool calls — this is the final text response
                streaming_msg.finalize()

                # Store for /copy command
                self._last_response = full_response

                # Add to message history
                self.messages.append(Message(role="assistant", content=full_response))

                # Token tracking: use real usage if available, estimate otherwise
                cached_tokens = 0
                if stream_usage:
                    prompt_tokens = stream_usage.prompt_tokens
                    completion_tokens = stream_usage.completion_tokens
                    total = stream_usage.total_tokens
                    cached_tokens = stream_usage.cached_tokens
                else:
                    prompt_tokens = len(text) // 4
                    completion_tokens = len(full_response) // 4
                    total = prompt_tokens + completion_tokens

                self.total_tokens += total
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                status_bar.add_tokens(total, prompt=prompt_tokens, completion=completion_tokens)

                # Build input breakdown for log
                breakdown: dict[str, int] = {}
                if self._system_prompt:
                    breakdown["system"] = len(self._system_prompt) // 4
                history_chars = sum(len(m.content or "") for m in self.messages[:-1])
                breakdown["history"] = history_chars // 4
                breakdown["user_msg"] = len(text) // 4
                if tool_defs:
                    breakdown["tool_defs"] = len(str(tool_defs)) // 4

                log_token_usage(
                    model=self.current_model.id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total,
                    cached_tokens=cached_tokens,
                    message_breakdown=breakdown,
                )

                log_event(
                    "Response received",
                    model=self.current_model.id,
                    response_len=len(full_response),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cached_tokens=cached_tokens,
                    total_tokens=total,
                    source="actual" if stream_usage else "estimated",
                )

                # Auto-save conversation
                self._auto_save_conversation()
                status_bar.set_ready()
                break  # Done

            else:
                # Max iterations reached
                await self._add_message(
                    "error",
                    f"Tool loop stopped after {self._max_tool_iterations} iterations",
                )
                status_bar.set_error()

        except Exception as e:
            # Remove the streaming message and show error
            try:
                await streaming_msg.remove()
            except Exception:
                pass
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await self._add_message("error", f"API Error: {error_msg}")
            log_api_error(self.current_model.id, e)
            status_bar.set_error()

        finally:
            self.is_streaming = False
            self._current_streaming_message = None

    def action_quit(self) -> None:
        """Quit the application."""
        self.is_streaming = False  # Break any retry countdown loops
        log_event("App exiting")
        self.exit()

    async def action_clear_screen(self) -> None:
        """Clear the screen."""
        await self._clear_chat()

    def action_cancel(self) -> None:
        """Cancel current operation (retry countdown, streaming, etc.)."""
        if self.is_streaming:
            self.is_streaming = False  # Breaks retry countdown and streaming loops
            log_event("Operation cancelled by user")
            status_bar = self.query_one(StatusBar)
            status_bar.set_ready()
        self.query_one(MessageInput).focus()
