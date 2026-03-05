#!/bin/bash
# Foundry TUI - Quick Start Script

set -e

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' is not installed."
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Run the app
exec uv run foundry-tui "$@"
