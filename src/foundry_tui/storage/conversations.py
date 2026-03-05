"""Conversation persistence and management."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from foundry_tui.storage.persistence import get_config_dir


def get_conversations_dir() -> Path:
    """Get the conversations directory."""
    conv_dir = get_config_dir() / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    return conv_dir


@dataclass
class ConversationMetadata:
    """Metadata for a saved conversation."""

    id: str
    title: str
    model_id: str
    model_name: str
    provider: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    preview: str  # First ~50 chars of first user message

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMetadata":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title", "Untitled"),
            model_id=data["model_id"],
            model_name=data.get("model_name", data["model_id"]),
            provider=data.get("provider", "unknown"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data.get("updated_at", data["created_at"])),
            message_count=data.get("message_count", 0),
            preview=data.get("preview", ""),
        )


@dataclass
class Conversation:
    """A saved conversation."""

    id: str
    title: str
    model_id: str
    model_name: str
    provider: str
    system_prompt: str | None
    messages: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title", "Untitled"),
            model_id=data["model_id"],
            model_name=data.get("model_name", data["model_id"]),
            provider=data.get("provider", "unknown"),
            system_prompt=data.get("system_prompt"),
            messages=data.get("messages", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data.get("updated_at", data["created_at"])),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "provider": self.provider,
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def get_preview(self) -> str:
        """Get a preview of the conversation (first user message)."""
        for msg in self.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "") or ""
                return content[:50] + "..." if len(content) > 50 else content
        return ""


def generate_conversation_id() -> str:
    """Generate a unique conversation ID."""
    return f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_title(messages: list[dict[str, Any]]) -> str:
    """Generate a title from the first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # Take first line, truncate to 50 chars
            first_line = content.split("\n")[0].strip()
            if len(first_line) > 50:
                return first_line[:47] + "..."
            return first_line if first_line else "New conversation"
    return "New conversation"


def save_conversation(conversation: Conversation) -> Path:
    """Save a conversation to disk."""
    conv_dir = get_conversations_dir()
    file_path = conv_dir / f"{conversation.id}.json"

    with open(file_path, "w") as f:
        json.dump(conversation.to_dict(), f, indent=2)

    return file_path


def load_conversation(conversation_id: str) -> Conversation | None:
    """Load a conversation by ID."""
    conv_dir = get_conversations_dir()
    file_path = conv_dir / f"{conversation_id}.json"

    if not file_path.exists():
        return None

    try:
        with open(file_path) as f:
            data = json.load(f)
        return Conversation.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation by ID."""
    conv_dir = get_conversations_dir()
    file_path = conv_dir / f"{conversation_id}.json"

    if file_path.exists():
        file_path.unlink()
        return True
    return False


def list_conversations() -> list[ConversationMetadata]:
    """List all saved conversations, sorted by updated_at descending."""
    conv_dir = get_conversations_dir()
    conversations = []

    for file_path in conv_dir.glob("conv_*.json"):
        try:
            with open(file_path) as f:
                data = json.load(f)

            # Build metadata from conversation data
            messages = data.get("messages", [])
            preview = ""
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    preview = content[:50] + "..." if len(content) > 50 else content
                    break

            metadata = ConversationMetadata(
                id=data["id"],
                title=data.get("title", "Untitled"),
                model_id=data["model_id"],
                model_name=data.get("model_name", data["model_id"]),
                provider=data.get("provider", "unknown"),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data.get("updated_at", data["created_at"])),
                message_count=len(messages),
                preview=preview,
            )
            conversations.append(metadata)
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by updated_at descending (most recent first)
    conversations.sort(key=lambda c: c.updated_at, reverse=True)
    return conversations
