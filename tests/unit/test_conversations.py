"""Unit tests for storage/conversations.py — Conversation save/load round-trip."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_tui.storage.conversations import (
    Conversation,
    ConversationMetadata,
    delete_conversation,
    generate_title,
    list_conversations,
    load_conversation,
    save_conversation,
)


@pytest.fixture
def conv_dir(tmp_path: Path) -> Path:
    """Create a temporary conversations directory."""
    d = tmp_path / "conversations"
    d.mkdir()
    return tmp_path


@pytest.fixture
def sample_conversation() -> Conversation:
    """Create a sample conversation for testing."""
    return Conversation(
        id="conv_20260311_120000",
        title="Test Conversation",
        model_id="gpt-4o",
        model_name="GPT-4o",
        provider="openai",
        system_prompt="You are helpful.",
        messages=[
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thanks!"},
        ],
        created_at=datetime(2026, 3, 11, 12, 0, 0),
        updated_at=datetime(2026, 3, 11, 12, 1, 0),
    )


class TestConversationRoundTrip:
    """Tests for saving and loading conversations."""

    def test_save_and_load_roundtrip(self, conv_dir: Path, sample_conversation: Conversation):
        """Saved conversation should be loadable and identical."""
        with patch(
            "foundry_tui.storage.conversations.get_conversations_dir",
            return_value=conv_dir / "conversations",
        ):
            save_conversation(sample_conversation)
            loaded = load_conversation(sample_conversation.id)

        assert loaded is not None
        assert loaded.id == sample_conversation.id
        assert loaded.title == sample_conversation.title
        assert loaded.model_id == sample_conversation.model_id
        assert loaded.model_name == sample_conversation.model_name
        assert loaded.provider == sample_conversation.provider
        assert loaded.system_prompt == sample_conversation.system_prompt
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["content"] == "Hello, how are you?"

    def test_load_nonexistent(self, conv_dir: Path):
        """Loading a nonexistent conversation should return None."""
        with patch(
            "foundry_tui.storage.conversations.get_conversations_dir",
            return_value=conv_dir / "conversations",
        ):
            assert load_conversation("conv_nonexistent") is None

    def test_list_conversations(self, conv_dir: Path, sample_conversation: Conversation):
        """List should include saved conversations."""
        with patch(
            "foundry_tui.storage.conversations.get_conversations_dir",
            return_value=conv_dir / "conversations",
        ):
            save_conversation(sample_conversation)
            convs = list_conversations()

        assert len(convs) == 1
        assert convs[0].id == sample_conversation.id
        assert convs[0].title == "Test Conversation"
        assert convs[0].message_count == 2

    def test_delete_conversation(self, conv_dir: Path, sample_conversation: Conversation):
        """Delete should remove the conversation file."""
        with patch(
            "foundry_tui.storage.conversations.get_conversations_dir",
            return_value=conv_dir / "conversations",
        ):
            save_conversation(sample_conversation)
            assert delete_conversation(sample_conversation.id) is True
            assert load_conversation(sample_conversation.id) is None

    def test_delete_nonexistent(self, conv_dir: Path):
        """Deleting a nonexistent conversation should return False."""
        with patch(
            "foundry_tui.storage.conversations.get_conversations_dir",
            return_value=conv_dir / "conversations",
        ):
            assert delete_conversation("conv_nonexistent") is False


class TestGenerateTitle:
    """Tests for title generation."""

    def test_from_user_message(self):
        """Title should come from first user message."""
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]
        assert generate_title(messages) == "What is Python?"

    def test_truncate_long_message(self):
        """Long messages should be truncated."""
        messages = [{"role": "user", "content": "A" * 100}]
        title = generate_title(messages)
        assert len(title) <= 50
        assert title.endswith("...")

    def test_no_user_message(self):
        """No user messages should return default title."""
        messages = [{"role": "assistant", "content": "Hello!"}]
        assert generate_title(messages) == "New conversation"

    def test_empty_messages(self):
        """Empty message list should return default title."""
        assert generate_title([]) == "New conversation"


class TestConversationMetadata:
    """Tests for ConversationMetadata.from_dict()."""

    def test_from_dict_full(self):
        """Full metadata dict should parse correctly."""
        data = {
            "id": "conv_123",
            "title": "My Chat",
            "model_id": "gpt-4o",
            "model_name": "GPT-4o",
            "provider": "openai",
            "created_at": "2026-03-11T12:00:00",
            "updated_at": "2026-03-11T12:01:00",
            "message_count": 4,
            "preview": "Hello, how are you?",
        }
        meta = ConversationMetadata.from_dict(data)
        assert meta.id == "conv_123"
        assert meta.title == "My Chat"
        assert meta.message_count == 4

    def test_from_dict_optional_fields(self):
        """Missing optional fields should get defaults."""
        data = {
            "id": "conv_456",
            "model_id": "gpt-4o",
            "created_at": "2026-03-11T12:00:00",
        }
        meta = ConversationMetadata.from_dict(data)
        assert meta.title == "Untitled"
        assert meta.model_name == "gpt-4o"  # Falls back to model_id
        assert meta.provider == "unknown"
        assert meta.message_count == 0
        assert meta.preview == ""
