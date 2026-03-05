"""Persistent memory storage using a human-readable Markdown file.

Memories are stored at ~/.foundry-tui/memories.md with one ## section per memory.
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("foundry_tui")

MEMORY_DIR = Path.home() / ".foundry-tui"
MEMORY_FILE = MEMORY_DIR / "memories.md"

HEADER = "# Foundry TUI Memories\n"


@dataclass
class Memory:
    """A single stored memory."""

    id: str
    content: str
    source_model: str
    created_at: datetime


def _ensure_file() -> None:
    """Create the memories file with header if it doesn't exist."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(HEADER + "\n")


def load_memories() -> list[Memory]:
    """Parse memories.md and return all memories."""
    if not MEMORY_FILE.exists():
        return []

    text = MEMORY_FILE.read_text(encoding="utf-8")
    memories: list[Memory] = []

    # Split on ## headings (memory IDs)
    sections = re.split(r"^## ", text, flags=re.MULTILINE)

    for section in sections[1:]:  # skip header before first ##
        lines = section.strip().split("\n")
        if not lines:
            continue

        memory_id = lines[0].strip()
        source_model = ""
        created_at = datetime.now(timezone.utc)
        content_lines: list[str] = []
        past_metadata = False

        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("- **Saved**:"):
                ts_str = stripped.replace("- **Saved**:", "").strip()
                try:
                    created_at = datetime.fromisoformat(ts_str)
                except ValueError:
                    pass
            elif stripped.startswith("- **Source**:"):
                source_model = stripped.replace("- **Source**:", "").strip()
            elif stripped == "" and not past_metadata:
                # Blank line after metadata marks start of content
                if source_model or content_lines:
                    past_metadata = True
            else:
                past_metadata = True
                content_lines.append(line)

        content = "\n".join(content_lines).strip()
        if content:
            memories.append(Memory(
                id=memory_id,
                content=content,
                source_model=source_model,
                created_at=created_at,
            ))

    return memories


def save_memory(content: str, source_model: str) -> Memory:
    """Append a new memory to the file and return it."""
    _ensure_file()

    # Use timestamp + counter suffix to ensure unique IDs within same second
    ts = int(time.time())
    existing = load_memories()
    suffix = sum(1 for m in existing if m.id.startswith(f"mem_{ts}"))
    memory_id = f"mem_{ts}" if suffix == 0 else f"mem_{ts}_{suffix}"
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    block = (
        f"\n## {memory_id}\n"
        f"- **Saved**: {timestamp}\n"
        f"- **Source**: {source_model}\n"
        f"\n"
        f"{content}\n"
    )

    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(block)

    logger.info("Memory saved: %s (%d chars) via %s", memory_id, len(content), source_model)

    return Memory(id=memory_id, content=content, source_model=source_model, created_at=now)


def delete_memory(memory_id: str) -> bool:
    """Remove a memory by ID. Returns True if found and deleted."""
    if not MEMORY_FILE.exists():
        return False

    text = MEMORY_FILE.read_text(encoding="utf-8")

    # Match the ## section for this memory ID (up to next ## or end of file)
    pattern = rf"\n## {re.escape(memory_id)}\n.*?(?=\n## |\Z)"
    new_text, count = re.subn(pattern, "", text, count=1, flags=re.DOTALL)

    if count == 0:
        return False

    MEMORY_FILE.write_text(new_text, encoding="utf-8")
    logger.info("Memory deleted: %s", memory_id)
    return True


def clear_memories() -> int:
    """Delete all memories. Returns the count of deleted memories."""
    memories = load_memories()
    count = len(memories)

    if count > 0:
        _ensure_file()
        MEMORY_FILE.write_text(HEADER + "\n")
        logger.info("All %d memories cleared", count)

    return count


def search_memories(query: str) -> list[Memory]:
    """Search memories by case-insensitive substring match."""
    query_lower = query.lower()
    return [m for m in load_memories() if query_lower in m.content.lower()]


def memory_count() -> int:
    """Return the number of stored memories (fast, no full parse)."""
    if not MEMORY_FILE.exists():
        return 0
    text = MEMORY_FILE.read_text(encoding="utf-8")
    return len(re.findall(r"^## mem_", text, flags=re.MULTILINE))
