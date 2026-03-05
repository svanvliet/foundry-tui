# Foundry TUI

A terminal-based chat application for testing AI models on Microsoft Azure AI Foundry. Inspired by Claude Code's clean interface.

## Features

- **Multi-Model Support** - Chat with 18+ models from OpenAI, DeepSeek, xAI, Mistral, and more
- **Streaming Responses** - Real-time token streaming with animated status
- **Model Picker** - Fuzzy search to quickly switch between models
- **Conversation History** - Auto-save and resume previous conversations
- **System Prompts** - Set custom system prompts, persisted across sessions
- **Markdown Rendering** - Rich formatting with syntax-highlighted code blocks
- **Token Tracking** - Monitor usage with color-coded warnings

## Quick Start

### Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **Azure subscription** with AI services access

### Installation

```bash
# Clone the repository
git clone https://github.com/svanvliet/foundry-tui.git
cd foundry-tui

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the app (uv handles dependencies automatically)
./run.sh
```

### Configure Azure (Option A: Automated Setup)

Run the interactive setup script to deploy Azure resources:

```bash
# macOS/Linux
./scripts/setup.sh

# Windows (PowerShell)
.\scripts\setup.ps1
```

The script will:
1. Check prerequisites (Azure CLI)
2. Create a resource group
3. Let you select which models to deploy
4. Deploy Azure OpenAI and/or Azure AI Services
5. Automatically configure your `.env` file

### Configure Azure (Option B: Manual Setup)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Fill in your Azure credentials in `.env`:
   ```bash
   # Azure OpenAI (for GPT and o-series models)
   AZURE_OPENAI_ENDPOINT=https://your-region.api.cognitive.microsoft.com/
   AZURE_OPENAI_API_KEY=your-key-here

   # Azure AI Services (for DeepSeek, Grok, Kimi)
   AZURE_AI_ENDPOINT=https://your-region.api.cognitive.microsoft.com/
   AZURE_AI_API_KEY=your-key-here
   ```

3. Run the app:
   ```bash
   ./run.sh
   ```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/models` or `/m` | Open model picker (fuzzy search) |
| `/system [prompt]` | View/set system prompt (`/system clear` to remove) |
| `/load` or `/convs` | Browse and load saved conversations |
| `/save [title]` | Save conversation with optional title |
| `/new` or `/n` | Start a new conversation |
| `/clear` or `/c` | Clear chat history |
| `/copy` | Copy last response to clipboard |
| `/export [file]` | Export conversation to JSON |
| `/help` or `/h` | Show help |
| `/quit` or `/q` | Exit |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `Ctrl+C` | Quit |
| `Ctrl+L` | Clear screen |
| `Escape` | Cancel / Close picker |

### Supported Models

**Azure OpenAI:**
- GPT-4o, GPT-4o Mini
- GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano
- GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-5.1
- o1, o3-mini, o4-mini (reasoning)

**Azure AI Services:**
- DeepSeek R1 (reasoning), DeepSeek V3 (chat)
- Grok 3, Grok 4.1 Fast Reasoning
- Kimi K2.5

**Serverless:**
- Mistral Small

## Project Structure

```
foundry-tui/
├── run.sh                 # Quick start script
├── .env.example           # Environment template
├── models-catalog.json    # Model definitions
├── scripts/
│   ├── setup.sh           # Azure resource setup (Bash)
│   ├── setup.ps1          # Azure resource setup (PowerShell)
│   ├── teardown.sh        # Resource cleanup (Bash)
│   └── teardown.ps1       # Resource cleanup (PowerShell)
├── src/foundry_tui/
│   ├── app.py             # Main application
│   ├── config.py          # Configuration loading
│   ├── models.py          # Model definitions
│   ├── api/               # API clients
│   ├── ui/                # TUI components
│   └── storage/           # Persistence
└── docs/
    ├── requirements.md    # Full requirements
    └── plan.md            # Implementation plan
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | For GPT/o-series |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | For GPT/o-series |
| `AZURE_OPENAI_API_VERSION` | API version (default: `2024-12-01-preview`) | No |
| `AZURE_AI_ENDPOINT` | Azure AI Services endpoint | For DeepSeek/Grok/Kimi |
| `AZURE_AI_API_KEY` | Azure AI Services API key | For DeepSeek/Grok/Kimi |
| `SERVERLESS_ENDPOINT_*` | Serverless model endpoints | For Mistral |
| `SERVERLESS_KEY_*` | Serverless model API keys | For Mistral |
| `FOUNDRY_TUI_LOG_LEVEL` | Log level (default: `INFO`) | No |
| `FOUNDRY_TUI_COST_WARNING_THRESHOLD` | Token warning threshold | No |

### Model Catalog

Models are defined in `models-catalog.json`. You can add, remove, or modify models by editing this file. Each model specifies:

- `id` - Unique identifier
- `name` - Display name
- `provider` - Provider name (openai, deepseek, xai, etc.)
- `category` - `chat` or `reasoning`
- `deployment` - API type and deployment details
- `capabilities` - Tools, streaming, vision support
- `context_window` - Maximum context size
- `max_output_tokens` - Maximum output length

## Data Storage

Foundry TUI stores data in `~/.foundry-tui/`:

- `config.json` - User preferences (last model, system prompt)
- `conversations/` - Saved conversations (JSON)

Logs are written to `logs/` in the project directory.

## Cleanup

To remove Azure resources created by the setup script:

```bash
# macOS/Linux
./scripts/teardown.sh

# Windows (PowerShell)
.\scripts\teardown.ps1
```

## Development

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Run type checker
uv run pyright
```

## Troubleshooting

### "max_tokens is too large" error
The app no longer sends max_tokens by default. If you see this error, make sure you have the latest version.

### Model not responding
1. Check your `.env` file has the correct endpoint and API key
2. Verify the model is deployed in your Azure subscription
3. Check `logs/` for detailed error messages

### UI freezing during responses
This was fixed in a recent update. Pull the latest version and try again.

## License

MIT

## Acknowledgments

- Built with [Textual](https://textual.textualize.io/) for the TUI
- Inspired by [Claude Code](https://claude.ai/claude-code)'s clean interface
- Uses [Rich](https://rich.readthedocs.io/) for markdown rendering
