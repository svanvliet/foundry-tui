# Foundry TUI - Requirements Document

## Overview

Foundry TUI is a terminal-based chat application for testing and interacting with AI models available through Microsoft Azure AI Foundry. The application provides a Claude Code-inspired interface with streaming responses, slash commands, and a polished terminal experience.

## Goals

1. **Model Testing**: Easily switch between and test 18 deployed models across providers (OpenAI, Mistral, DeepSeek, xAI, Moonshot)
2. **Developer Experience**: Provide a fast, responsive TUI similar to Claude Code
3. **Comparative Analysis**: Enable quick comparison of model responses and capabilities

---

## Finalized Decisions

| Decision | Choice |
|----------|--------|
| Language | Python 3.11+ |
| TUI Framework | [Textual](https://textual.textualize.io/) |
| Input Mode | Standard keybindings |
| Theme | Auto-detect from terminal |
| Model Picker | Fuzzy finder (fzf-style) |
| Error Display | Inline in chat + logged to `logs/` |
| Conversation Storage | JSON files in standard format |
| Tool Calling | Included in MVP |

---

## Core Features

### 1. Chat Interface

- Full-screen terminal UI with input area and scrollable message history
- Streaming response display with real-time token rendering
- Markdown rendering for model responses (code blocks, lists, headers, etc.)
- Message history with clear visual distinction between user and assistant messages
- Status bar showing:
  - Current model name and provider
  - Token counts (input/output)
  - Context usage indicator (warning when approaching limits)
  - Connection status

### 2. Model Selection (`/models` command)

- Fuzzy search model picker (fzf-style)
- Models grouped by category:
  - **Chat Models**: GPT-4o, GPT-4.1, GPT-5, DeepSeek V3.2, Grok 3, Mistral, Kimi
  - **Reasoning Models**: o1, o3-mini, o4-mini, DeepSeek R1, Grok 4.1 Fast Reasoning
- Display model metadata:
  - Provider icon/badge
  - Capabilities (tools, vision, streaming)
  - Context window size
- Persist last-used model selection across sessions
- "Provision New Model" option showing available models (returns "Not Yet Implemented")

### 3. Tool/Function Calling

- Support for models with `capabilities.tools: true`
- Define tools via configuration file or in-app
- Display tool calls and results in chat
- Graceful fallback for models without tool support

### 4. Conversation Persistence

- Auto-save conversations to `~/.foundry-tui/conversations/`
- Format: JSON following OpenAI message format (widely compatible)
- File naming: `{timestamp}_{model_id}_{first_words}.json`
- `/export` command for manual export to custom location

### 5. Slash Commands

| Command | Description |
|---------|-------------|
| `/models` | Open model selector (fuzzy finder) |
| `/clear` | Clear conversation history |
| `/new` | Start new conversation |
| `/help` | Show available commands |
| `/copy` | Copy last response to clipboard |
| `/export` | Export conversation to file |
| `/system` | Set/view system prompt (Phase 4) |
| `/quit` or `/exit` | Exit application |

### 6. Logging

- Session logs written to `logs/` directory
- Log levels: DEBUG, INFO, WARNING, ERROR
- Configurable via `FOUNDRY_TUI_LOG_LEVEL` env var
- Includes: API requests/responses, errors, timing info

---

## Technical Architecture

### Tech Stack

- **Language**: Python 3.11+
- **TUI Framework**: [Textual](https://textual.textualize.io/)
- **API Client**: `openai` SDK (works with Azure OpenAI) + `httpx` for Azure AI
- **Markdown**: `rich` (included with Textual)
- **Config**: `python-dotenv` for `.env`, `pydantic` for validation

### Deployment Types

The app handles three distinct Azure API patterns:

1. **Azure OpenAI** (`azure_openai`)
   - Endpoint: `AZURE_OPENAI_ENDPOINT`
   - Auth: `AZURE_OPENAI_API_KEY`
   - API Version: `AZURE_OPENAI_API_VERSION`
   - Models: GPT-4o, GPT-4.1, GPT-5, o1, o3-mini, o4-mini

2. **Azure AI Services** (`azure_ai`)
   - Endpoint: `AZURE_AI_ENDPOINT`
   - Auth: `AZURE_AI_API_KEY`
   - Models: DeepSeek R1, DeepSeek V3.2, Grok 3, Grok 4.1, Kimi K2.5

3. **Serverless** (`serverless`)
   - Per-model endpoints and keys (defined in `models-catalog.json`)
   - Models: Mistral Small

### Context Management Strategy

**Approach**: Token-limited with automatic Azure prompt caching

- Send up to 80% of model's context window (configurable via `FOUNDRY_TUI_CONTEXT_RATIO`)
- Reserve 20% for model response
- Azure OpenAI automatically caches repeated prompt prefixes for GPT-4o models (~50% cost reduction)
- Display context usage in status bar
- Warn when exceeding `FOUNDRY_TUI_COST_WARNING_THRESHOLD` tokens

**Cost considerations**:
- Large context models (GPT-4.1 with 1M tokens, GPT-5 with 256k) can be expensive
- Status bar shows running token count
- Optional warning threshold for long conversations

### Conversation Storage Format

```json
{
  "id": "conv_20240315_143022_gpt4o",
  "created_at": "2024-03-15T14:30:22Z",
  "model_id": "gpt-4o",
  "system_prompt": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "2+2 equals 4."}
  ],
  "metadata": {
    "total_input_tokens": 150,
    "total_output_tokens": 45
  }
}
```

---

## User Experience

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `Ctrl+C` | Cancel current generation / Exit |
| `Ctrl+L` | Clear screen |
| `Up/Down` | Scroll history |
| `Esc` | Cancel current action / Close modal |

### Status Bar

The status bar provides real-time feedback about the application state.

**Layout:**
```
┌────────────────────────────────────────────────────────────────────┐
│ ● GPT-5.1  │  ⣾ Thinking...  │  Session: 1,234 tokens  │  openai  │
└────────────────────────────────────────────────────────────────────┘
```

**Components (left to right):**

1. **Model Indicator**
   - Current model name
   - Category icon: `●` (chat) or `◆` (reasoning)

2. **Activity Status** (with spinner animation)
   | State | Display | When |
   |-------|---------|------|
   | Idle | `Ready` | Waiting for user input |
   | Sending | `⣾ Sending...` | Request being sent to API |
   | Thinking | `⣾ Thinking...` | Waiting for first token |
   | Streaming | `⣾ Receiving...` | Tokens arriving |
   | Error | `✗ Error` | API error (briefly, then Ready) |

   **Spinner Animation** (Braille dots, cycles every 100ms):
   `⣾ ⣽ ⣻ ⢿ ⡿ ⣟ ⣯ ⣷`

3. **Token Counter**
   - `Session: X,XXX tokens` - Total tokens used this session
   - Color changes as usage increases:
     - Green: < 50% of warning threshold
     - Yellow: 50-80% of warning threshold
     - Red: > 80% of warning threshold

4. **Provider Badge**
   - Shows current model's provider (openai, deepseek, xai, etc.)

**Token Tracking:**

- **Session tokens**: Total input + output tokens for current session
- **Stored in memory** during session (resets on app restart)
- **Estimated** from streaming (actual counts when API provides them)
- **Future**: Per-model cumulative tracking across sessions (stored in config)

### Visual Design

- Minimal chrome, maximum content area
- Auto-detect light/dark theme from terminal
- Syntax highlighting for code blocks
- Animated spinner during model response
- Color-coded model categories:
  - Chat models: Cyan `●`
  - Reasoning models: Magenta `◆`
- Provider badges in model picker

### Model Picker UI

```
┌─ Select Model ─────────────────────────────────────┐
│ > gpt                                              │
│                                                    │
│ ── Chat Models ──────────────────────────────────  │
│   GPT-4o              openai   128k  tools vision  │
│   GPT-4o Mini         openai   128k  tools vision  │
│ > GPT-4.1             openai   1M    tools vision  │
│   GPT-4.1 Mini        openai   1M    tools vision  │
│   GPT-5               openai   256k  tools vision  │
│                                                    │
│ ── Reasoning Models ─────────────────────────────  │
│   o4 Mini             openai   200k  tools vision  │
│                                                    │
│ ── Provision New ────────────────────────────────  │
│   [Deploy additional models...]                    │
│                                                    │
│ ↑↓ Navigate  Enter Select  Esc Cancel              │
└────────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Foundry TUI                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   .env      │───▶│ Config       │◀───│ models-       │  │
│  │             │    │ Manager      │    │ catalog.json  │  │
│  └─────────────┘    └──────┬───────┘    └───────────────┘  │
│                            │                                │
│                            ▼                                │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  TUI        │───▶│ Chat         │───▶│ API Client    │  │
│  │  (Textual)  │◀───│ Controller   │◀───│ (streaming)   │  │
│  └─────────────┘    └──────┬───────┘    └───────────────┘  │
│                            │                                │
│                            ▼                                │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Logger     │    │ Conversation │    │ Tool          │  │
│  │  (logs/)    │    │ Store        │    │ Registry      │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────────┐
              │     Azure AI Foundry              │
              │  ┌─────────┐ ┌─────────────────┐  │
              │  │ OpenAI  │ │ AI Services     │  │
              │  └─────────┘ └─────────────────┘  │
              │  ┌─────────────────────────────┐  │
              │  │ Serverless Endpoints        │  │
              │  └─────────────────────────────┘  │
              └───────────────────────────────────┘
```

---

## Project Structure

```
foundry-tui/
├── src/
│   └── foundry_tui/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── app.py               # Main Textual app
│       ├── config.py            # Configuration loading
│       ├── models.py            # Model catalog & types
│       ├── api/
│       │   ├── __init__.py
│       │   ├── client.py        # Unified API client
│       │   ├── azure_openai.py  # Azure OpenAI adapter
│       │   ├── azure_ai.py      # Azure AI adapter
│       │   └── serverless.py    # Serverless adapter
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── chat.py          # Chat view
│       │   ├── model_picker.py  # Model selector
│       │   ├── status_bar.py    # Status bar widget
│       │   └── styles.tcss      # Textual CSS
│       ├── tools/
│       │   ├── __init__.py
│       │   └── registry.py      # Tool definitions
│       └── storage/
│           ├── __init__.py
│           ├── conversations.py # Conversation persistence
│           └── logger.py        # Session logging
├── tests/
├── logs/                        # Session logs (gitignored)
├── docs/
│   └── requirements.md
├── models-catalog.json
├── .env
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Milestones

### Phase 1 - MVP
- [ ] Basic Textual app with input/output areas
- [ ] Single model chat with streaming
- [ ] Azure OpenAI integration
- [ ] `/quit` command
- [ ] Basic error handling (inline display)

### Phase 2 - Multi-Model
- [ ] `/models` command with fuzzy finder
- [ ] Support all three deployment types (azure_openai, azure_ai, serverless)
- [ ] Model persistence across sessions
- [ ] `/clear`, `/new`, `/help` commands
- [ ] Models grouped by category (chat/reasoning)
- [ ] "Provision" placeholder (Not Yet Implemented)

### Phase 3 - Polish
- [ ] Markdown rendering with syntax highlighting
- [ ] `/copy` and `/export` commands
- [ ] Token usage display in status bar
- [ ] Context management with cost warnings
- [ ] Session logging to `logs/`
- [ ] Tool/function calling support

### Phase 4 - System Prompts
- [ ] `/system` command to set/view prompts
- [ ] Per-model default system prompts
- [ ] System prompt persistence

### Phase 5 - Conversations
- [ ] Auto-save conversations to disk
- [ ] Load/resume previous conversations
- [ ] Conversation browser/picker

### Future (Deferred)
- [ ] Model provisioning from available catalog
- [ ] Side-by-side model comparison mode
- [ ] Multiple conversation tabs
- [ ] Image/vision support for capable models

---

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Azure OpenAI API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [Azure AI Model Inference API](https://learn.microsoft.com/en-us/azure/ai-studio/reference/reference-model-inference-api)
- [OpenAI Python SDK](https://github.com/openai/openai-python) (works with Azure)
