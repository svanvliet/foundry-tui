"""Main Foundry TUI application."""

import json
from datetime import datetime
from pathlib import Path

import pyperclip
from textual.app import App, ComposeResult
from textual.widgets import Static

from foundry_tui.api.azure_openai import Message
from foundry_tui.api.client import ChatClient
from foundry_tui.config import Config
from foundry_tui.models import Model
from foundry_tui.storage.logger import get_logger, log_api_error, log_api_request, log_event
from foundry_tui.storage.conversations import (
    Conversation,
    generate_conversation_id,
    generate_title,
    load_conversation,
    save_conversation,
)
from foundry_tui.storage.persistence import (
    get_last_model_id,
    get_system_prompt,
    set_last_model_id,
    set_system_prompt,
)
from foundry_tui.ui.chat import ChatContainer, ChatLog, ChatMessage, StreamingMessage
from foundry_tui.ui.input import InputContainer, MessageInput
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
        self.config = config
        self.current_model = self._get_initial_model()
        self.messages: list[Message] = []
        self.total_tokens = 0
        self.is_streaming = False
        self._current_streaming_message: StreamingMessage | None = None
        self._last_response: str = ""  # Store last assistant response for /copy
        self._system_prompt: str | None = get_system_prompt()
        self._conversation_id: str | None = None  # Current conversation ID for auto-save

        # Initialize unified API client
        self.client = ChatClient(config=config)

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
        yield InputContainer()
        yield StatusBar()

    def _update_status_bar_model(self) -> None:
        """Update status bar with current model info."""
        status_bar = self.query_one(StatusBar)
        status_bar.set_model(
            name=self.current_model.name,
            category=self.current_model.category.value,
            provider=self.current_model.provider,
        )
        status_bar.warning_threshold = self.config.settings.cost_warning_threshold

    def on_mount(self) -> None:
        """Handle app mount."""
        # Set initial status
        self._update_status_bar_model()

        # Show welcome message
        chat_log = self.query_one(ChatLog)
        system_info = ""
        if self._system_prompt:
            preview = self._system_prompt[:50] + "..." if len(self._system_prompt) > 50 else self._system_prompt
            system_info = f"\nSystem prompt: [dim]{preview}[/dim]"
        welcome = Static(
            f"Welcome to Foundry TUI!\n\n"
            f"Current model: [bold]{self.current_model.name}[/bold] ({self.current_model.provider})"
            f"{system_info}\n"
            f"Type a message and press Enter to chat.\n"
            f"Commands: /models, /system, /load, /new, /clear, /copy, /export, /help, /quit",
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

        # Send to API and stream response
        await self._send_message(text)

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
        elif cmd in ("/help", "/h", "/?"):
            await self._show_help()
        else:
            await self._add_message("error", f"Unknown command: {command}")

    async def _clear_chat(self) -> None:
        """Clear the chat history."""
        self.messages.clear()
        self.total_tokens = 0
        self._last_response = ""

        chat_log = self.query_one(ChatLog)
        await chat_log.remove_children()

        # Reset token counter in status bar
        status_bar = self.query_one(StatusBar)
        status_bar.session_tokens = 0

        await self._add_message("system", "Chat cleared.")

    async def _new_conversation(self) -> None:
        """Start a new conversation."""
        # Auto-save current conversation before starting new one
        if self.messages:
            self._auto_save_conversation()

        self.messages.clear()
        self.total_tokens = 0
        self._last_response = ""
        self._conversation_id = None  # Reset conversation ID

        chat_log = self.query_one(ChatLog)
        await chat_log.remove_children()

        # Reset token counter in status bar
        status_bar = self.query_one(StatusBar)
        status_bar.session_tokens = 0

        await self._add_message(
            "system",
            f"New conversation started with [bold]{self.current_model.name}[/bold].",
        )

    async def _show_model_picker(self) -> None:
        """Show the model picker."""
        picker = ModelPicker(self.config.catalog, self.current_model)
        await self.push_screen(picker)

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
        messages_dict = [{"role": m.role, "content": m.content} for m in self.messages]
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
            self.messages.append(Message(role=msg["role"], content=msg["content"]))
            await self._add_message(msg["role"], msg["content"])

        # Find last assistant response for /copy
        for msg in reversed(conversation.messages):
            if msg["role"] == "assistant":
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

    async def _show_help(self) -> None:
        """Show help message."""
        help_text = (
            "[bold]Available Commands:[/bold]\n\n"
            "  /models, /m       - Select a different model\n"
            "  /system [prompt]  - View/set system prompt (/system clear to remove)\n"
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

    async def _send_message(self, text: str) -> None:
        """Send a message to the API and stream the response."""
        import asyncio

        # Add to message history
        self.messages.append(Message(role="user", content=text))

        # Build messages for API (include system prompt if set)
        api_messages = []
        if self._system_prompt:
            api_messages.append(Message(role="system", content=self._system_prompt))
        api_messages.extend(self.messages)

        # Log the request
        log_api_request(
            self.current_model.id,
            [{"role": m.role, "content": m.content[:100]} for m in api_messages],
        )

        # Update status - sending request
        status_bar = self.query_one(StatusBar)
        status_bar.set_sending()
        self.is_streaming = True

        # Start streaming message
        streaming_msg = await self._start_streaming_message()

        # Switch to thinking while waiting for first token
        status_bar.set_thinking()

        try:
            # Stream the response using unified client
            full_response = ""
            chunk_count = 0
            first_chunk = True

            async for chunk in self.client.stream_chat(
                model=self.current_model,
                messages=api_messages,
            ):
                if chunk.content:
                    # Switch to streaming on first content
                    if first_chunk:
                        status_bar.set_streaming()
                        first_chunk = False

                    full_response += chunk.content
                    streaming_msg.append(chunk.content)
                    chunk_count += 1

                    # Batch UI updates - flush display every 3 chunks
                    if chunk_count % 3 == 0:
                        streaming_msg.flush()
                        chat_container = self.query_one(ChatContainer)
                        chat_container.scroll_to_bottom()
                        # Yield to event loop to keep UI responsive
                        await asyncio.sleep(0)

            # Flush any remaining content and scroll
            streaming_msg.flush()
            chat_container = self.query_one(ChatContainer)
            chat_container.scroll_to_bottom()

            # Finalize the message with markdown rendering
            streaming_msg.finalize()

            # Store for /copy command
            self._last_response = full_response

            # Add to message history
            self.messages.append(Message(role="assistant", content=full_response))

            # Estimate token count (rough: ~4 chars per token)
            estimated_tokens = len(text) // 4 + len(full_response) // 4
            self.total_tokens += estimated_tokens
            status_bar.add_tokens(estimated_tokens)

            log_event(
                "Response received",
                model=self.current_model.id,
                response_len=len(full_response),
            )

            # Auto-save conversation
            self._auto_save_conversation()

            # Set ready
            status_bar.set_ready()

        except Exception as e:
            # Remove the streaming message and show error
            await streaming_msg.remove()
            error_msg = str(e)
            # Truncate very long error messages
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await self._add_message("error", f"API Error: {error_msg}")
            log_api_error(self.current_model.id, e)
            # Set error status (auto-resets to ready)
            status_bar.set_error()

        finally:
            self.is_streaming = False
            self._current_streaming_message = None

    def action_quit(self) -> None:
        """Quit the application."""
        log_event("App exiting")
        self.exit()

    async def action_clear_screen(self) -> None:
        """Clear the screen."""
        await self._clear_chat()

    def action_cancel(self) -> None:
        """Cancel current operation."""
        # For now, just focus input
        self.query_one(MessageInput).focus()
