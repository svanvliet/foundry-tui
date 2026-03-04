# Foundry TUI - Project Context

## Overview

Foundry TUI is a terminal-based chat application for testing AI models deployed on Microsoft Azure AI Foundry. It provides a Claude Code-inspired interface with streaming responses, slash commands, and a polished terminal experience.

## Tech Stack

- **Language**: Python 3.11+
- **TUI Framework**: Textual
- **Package Manager**: uv
- **API Clients**: openai SDK (Azure OpenAI), httpx (Azure AI, Serverless)

## Project Structure

```
foundry-tui/
├── src/foundry_tui/
│   ├── __main__.py          # Entry point
│   ├── app.py               # Main Textual app
│   ├── config.py            # Configuration (pydantic)
│   ├── models.py            # Model catalog & types
│   ├── api/
│   │   ├── client.py        # Unified API client
│   │   ├── azure_openai.py  # Azure OpenAI adapter (GPT models)
│   │   ├── azure_ai.py      # Azure AI adapter (DeepSeek, Grok, Kimi)
│   │   └── serverless.py    # Serverless adapter (Mistral)
│   ├── ui/
│   │   ├── chat.py          # Chat messages, streaming
│   │   ├── input.py         # Message input widget
│   │   ├── model_picker.py  # Fuzzy model selector
│   │   ├── status_bar.py    # Status bar with spinner
│   │   └── styles.tcss      # Textual CSS
│   └── storage/
│       ├── logger.py        # Session logging
│       └── persistence.py   # Model selection persistence
├── docs/
│   ├── requirements.md      # Full requirements document
│   └── plan.md              # Implementation plan
├── models-catalog.json      # Model definitions
├── .env                     # API credentials (not in git)
└── pyproject.toml
```

## Running the App

```bash
uv run foundry-tui
```

## Commands

| Command | Description |
|---------|-------------|
| `/models`, `/m` | Open model picker (fuzzy search) |
| `/new`, `/n` | Start new conversation |
| `/clear`, `/c` | Clear chat history |
| `/copy` | Copy last response to clipboard |
| `/export [file]` | Export conversation to JSON |
| `/help`, `/h` | Show help |
| `/quit`, `/q` | Exit |

## API Configuration

Three deployment types are supported:

1. **Azure OpenAI** (`azure_openai`) - GPT-4o, GPT-4.1, GPT-5, o1, o3-mini, o4-mini
   - Uses `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`
   - Uses `max_completion_tokens` (not `max_tokens`) for newer models

2. **Azure AI Services** (`azure_ai`) - DeepSeek, Grok, Kimi
   - Uses `AZURE_AI_ENDPOINT`, `AZURE_AI_API_KEY`
   - API path: `/models/chat/completions`

3. **Serverless** (`serverless`) - Mistral
   - Per-model endpoints defined in `models-catalog.json`

## Key Implementation Details

### Status Bar (`ui/status_bar.py`)
- Uses ID selectors in CSS (`#sb-model`, `#sb-activity`, etc.)
- Animated Braille spinner: `⣾ ⣽ ⣻ ⢿ ⡿ ⣟ ⣯ ⣷`
- Activity states: Ready, Sending, Thinking, Receiving, Error
- Token counter with color thresholds (green/yellow/red)

### Streaming Messages (`ui/chat.py`)
- `StreamingMessage` uses batched updates (not reactive properties) for performance
- Call `append()` to add content, `flush()` to update display
- Call `finalize()` at the end to render markdown

### Model Picker (`ui/model_picker.py`)
- Custom `ModelsListView` class to avoid duplicate ID errors
- Models grouped by category (chat/reasoning)
- Fuzzy search filtering

## Common Issues & Solutions

1. **UI locks up during streaming**: Ensure `asyncio.sleep(0)` is called periodically and use batched `flush()` instead of reactive properties

2. **Status bar not showing elements**: CSS must use ID selectors matching the widget IDs, not class selectors

3. **GPT-5.1 max_tokens error**: Use `max_completion_tokens` parameter instead of `max_tokens`

4. **Azure AI 400 errors**: API path should be `/models/chat/completions`, not `/openai/deployments/`

## Current Progress

- **Phase 1** (MVP): Complete
- **Phase 2** (Multi-Model): Complete
- **Phase 3** (Polish): Complete
- **Phase 4** (System Prompts): Not started
- **Phase 5** (Conversations): Not started
- **Phase 6** (Azure Setup Scripts): Not started

## Next Steps

1. Implement Azure setup scripts (Phase 6) - interactive Bash/PowerShell scripts for resource deployment
2. Implement `/system` command for system prompts
3. Add conversation persistence and browser

## Serverless Configuration

Serverless models (like Mistral) use environment variables for both endpoint and key:
- `endpoint_env` in models-catalog.json points to env var for the URL
- `key_env` points to env var for the API key
- Config loads both via `get_serverless_endpoint()` and `get_serverless_key()`

See `docs/plan.md` for detailed implementation plan and `docs/requirements.md` for full requirements.
