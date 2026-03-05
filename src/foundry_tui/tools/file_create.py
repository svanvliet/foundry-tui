"""File creation tool — lets models save files to ~/Downloads/."""

import logging
import os
import re
from pathlib import Path

from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

# Sandbox directory
DOWNLOADS_DIR = Path.home() / "Downloads"

# Max content size: 10 MB
MAX_CONTENT_BYTES = 10 * 1024 * 1024

# Max collision suffix attempts
MAX_SUFFIX_ATTEMPTS = 100

# Blocked binary executable extensions
BLOCKED_EXTENSIONS = frozenset({
    ".exe", ".bat", ".com", ".msi",  # Windows
    ".dll", ".so", ".dylib",          # Shared libraries
})

# Characters not allowed in filenames (beyond path separators)
UNSAFE_FILENAME_RE = re.compile(r'[<>:"|?*\x00-\x1f]')


def sanitize_filename(raw: str) -> str:
    """Sanitize a filename: strip path separators, control chars, enforce length."""
    # Strip path separators and parent-dir traversal
    name = raw.replace("/", "").replace("\\", "").replace("..", "")
    # Strip control characters and other filesystem-unsafe chars
    name = UNSAFE_FILENAME_RE.sub("", name)
    # Strip leading/trailing whitespace and dots (hidden files on Unix)
    name = name.strip().strip(".")
    # Enforce 255-char limit
    if len(name) > 255:
        stem, ext = os.path.splitext(name)
        name = stem[: 255 - len(ext)] + ext
    return name


def resolve_collision(directory: Path, filename: str) -> Path:
    """Find a non-colliding path by appending _1, _2, etc."""
    target = directory / filename
    if not target.exists():
        return target

    stem, ext = os.path.splitext(filename)
    for i in range(1, MAX_SUFFIX_ATTEMPTS + 1):
        candidate = directory / f"{stem}_{i}{ext}"
        if not candidate.exists():
            return candidate

    raise FileExistsError(
        f"Could not find a unique name after {MAX_SUFFIX_ATTEMPTS} attempts for '{filename}'"
    )


class CreateFileTool(Tool):
    """Creates a text file in the user's Downloads folder."""

    name = "create_file"
    description = (
        "Create a text file in the user's ~/Downloads/ folder. "
        "Use this when the user asks you to write, generate, or save a file. "
        "Provide the filename (no path separators) and the full file content. "
        "Binary executables (.exe, .dll, .so, etc.) are not allowed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": (
                    "The filename including extension (e.g. 'report.md', 'script.py'). "
                    "Must not contain path separators."
                ),
            },
            "content": {
                "type": "string",
                "description": "The full text content of the file.",
            },
        },
        "required": ["filename", "content"],
    }

    async def execute(self, *, filename: str, content: str) -> ToolResult:
        """Write the file to ~/Downloads/ with all safety checks."""
        try:
            # Sanitize
            safe_name = sanitize_filename(filename)
            if not safe_name:
                return ToolResult(
                    content=f"Error: '{filename}' is not a valid filename after sanitization.",
                    error=True,
                )

            # Check extension
            _, ext = os.path.splitext(safe_name)
            if ext.lower() in BLOCKED_EXTENSIONS:
                return ToolResult(
                    content=f"Error: Cannot create files with extension '{ext}' (blocked for security).",
                    error=True,
                )

            # Check content size
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > MAX_CONTENT_BYTES:
                size_mb = len(content_bytes) / (1024 * 1024)
                return ToolResult(
                    content=f"Error: Content is {size_mb:.1f} MB, exceeds 10 MB limit.",
                    error=True,
                )

            # Ensure Downloads directory exists
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

            # Resolve collisions
            target = resolve_collision(DOWNLOADS_DIR, safe_name)

            # Final safety: verify resolved path is still inside sandbox
            resolved = target.resolve()
            sandbox = DOWNLOADS_DIR.resolve()
            if not str(resolved).startswith(str(sandbox)):
                return ToolResult(
                    content="Error: Path traversal detected — file must be in ~/Downloads/.",
                    error=True,
                )

            # Write
            target.write_bytes(content_bytes)
            size_kb = len(content_bytes) / 1024

            actual_name = target.name
            logger.info("Created file: %s (%d bytes)", target, len(content_bytes))

            return ToolResult(
                content=(
                    f"✅ File created: {actual_name}\n"
                    f"📁 Location: {target}\n"
                    f"📏 Size: {size_kb:.1f} KB"
                ),
            )

        except FileExistsError as e:
            return ToolResult(content=f"Error: {e}", error=True)
        except Exception as e:
            logger.exception("Failed to create file: %s", e)
            return ToolResult(content=f"Error creating file: {e}", error=True)
