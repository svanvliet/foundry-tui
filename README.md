# Foundry TUI

A terminal UI for testing Azure AI Foundry models.

## Installation

```bash
uv sync
```

## Usage

```bash
uv run foundry-tui
```

Or activate the virtual environment and run directly:

```bash
source .venv/bin/activate
foundry-tui
```

## Configuration

Copy `.env.example` to `.env` and configure your Azure credentials:

```bash
cp .env.example .env
```

## Commands

- `/models` - Select a model
- `/clear` - Clear chat history
- `/help` - Show help
- `/quit` - Exit

## License

MIT
