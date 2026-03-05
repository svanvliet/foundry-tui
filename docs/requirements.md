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
| Theme | Textual themes (Nord default, 20 built-in themes) |
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
  - Token counts (input/output/cached breakdown)
  - RPM counter (requests / limit) with color coding
  - Context usage indicator (warning when approaching limits)
  - Connection status
  - Rate limit auto-retry with countdown on 429 errors

### 2. Model Selection (`/models` command)

- Fuzzy search model picker (fzf-style)
- Models grouped by category:
  - **Chat Models**: GPT-4o, GPT-4.1, GPT-5, DeepSeek V3.2, Grok 3, Mistral, Kimi
  - **Reasoning Models**: o1, o3-mini, o4-mini, DeepSeek R1, Grok 4.1 Fast Reasoning
- Display model metadata:
  - Provider icon/badge
  - Capabilities (tools, vision, streaming)
  - Context window size
  - RPM/TPM rate limit columns
- Persist last-used model selection across sessions
- "Provision New Model" option showing available models (returns "Not Yet Implemented")

### 3. Tool/Function Calling ✅

- Support for models with `capabilities.tools: true`
- Extensible tool registry (`tools/registry.py`, `tools/base.py`)
- Built-in Tavily web search tool (auto-enabled when `TAVILY_API_KEY` is set)
- User-defined tools via `~/.foundry-tui/tools.json`
- Tool loop in `_send_message` with max 10 iterations
- Collapsible tool call UI widgets (show tool name + args, expand for results)
- `/tools` command to list and inspect registered tools
- Graceful fallback for models without tool support

### 3b. Memory (Persistent User Context)

Models can remember facts about the user across conversations using tool calling.
Memories are stored locally and injected into the system prompt for every conversation.

**Tools (3 tools, auto-registered for all tool-capable models):**

| Tool | Description |
|------|-------------|
| `save_memory` | Store a fact or preference about the user. Args: `content` (string) |
| `recall_memories` | Search stored memories by keyword. Args: `query` (string) |
| `forget_memory` | Delete a memory by its ID. Args: `memory_id` (string) |

**Behavior:**
- **Global scope**: All models share the same memory store
- **Proactive saving**: System prompt instructs models to save useful facts about the user automatically (e.g., preferences, name, role, coding style)
- **Auto-injection**: All stored memories are injected into the system prompt for every conversation (no smart filtering — user manages manually)
- **No memory limit**: User manages memory size via `/memory` command or direct file editing
- **Graceful degradation**: Models without tool support (o1, o3-mini, DeepSeek R1) still receive injected memories but cannot save new ones

**Storage:**
- File: `~/.foundry-tui/memories.md`
- Format: Human-readable Markdown, one `##` section per memory with metadata
- Example:
  ```markdown
  # Foundry TUI Memories

  ## mem_1709654321
  - **Saved**: 2026-03-05 12:05:21
  - **Source**: gpt-4o

  User prefers Python and uses uv as their package manager.

  ## mem_1709654400
  - **Saved**: 2026-03-05 12:06:40
  - **Source**: deepseek-v3.2

  User's name is Sebastiaan. They work in developer tools.
  ```

**`/memory` command:**
- `/memory` — list all memories with IDs and previews
- `/memory search <query>` — search memories by keyword
- `/memory delete <id>` — delete a specific memory
- `/memory clear` — delete all memories (with confirmation)

**Model compatibility (15 of 18 models):**
- ✅ Tool-capable: GPT-4o/4.1/5/5.1 family, o4-mini, DeepSeek V3.2, Grok 3/4.1, Kimi K2.5, Mistral Small
- ❌ No tools: o1, o3-mini, DeepSeek R1 (receive memories, can't save)

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
| `/tools` | List registered tools, `/tools info <name>` for details |
| `/memory` | List memories, `/memory search`, `/memory delete <id>`, `/memory clear` |
| `/theme [name]` | Switch color theme (20 built-in themes) |
| `/quit` or `/exit` | Exit application |

**Input Enhancements:**
- Slash command autocomplete menu (filters as you type, Tab to complete, Enter to submit)
- Arg-level completions: `/models` → model names, `/system` → `clear`, `/theme` → theme names
- Input history with Up/Down arrow navigation (persisted to `~/.foundry-tui/input_history.txt`, last 200 entries)

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
| `Up/Down` | Input history (cycle through previous prompts) |
| `Tab` | Accept slash command autocomplete |
| `Esc` | Cancel streaming/retry / Close modal |

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
- **Real counts** from API via `stream_options: {"include_usage": true}` in all three clients
- **Prompt/completion/cached breakdown**: `Tokens: N (↑prompt ↓completion)` with `cached_tokens` from `prompt_tokens_details`
- **Per-call logging**: per-message breakdown (role, chars, tool_calls), actual token counts
- **HTTP-level tracing**: request body, rate limit headers, error bodies (Azure OpenAI)
- **Future**: Per-model cumulative tracking across sessions (stored in config)

### Visual Design

- Minimal chrome, maximum content area
- Textual themes: Nord default, 20 built-in themes, switchable via `/theme` command
- Syntax highlighting for code blocks
- Animated spinner during model response
- Collapsible widgets for tool calls and reasoning `<think>` tokens (💭)
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

---

## Azure Setup Scripts

### Overview

Interactive setup scripts that guide users through deploying the Azure resources needed to run Foundry TUI. Scripts are provided for both Bash (macOS/Linux/WSL) and PowerShell (Windows).

### Prerequisites

- Azure CLI (`az`) installed and authenticated
- Active Azure subscription with permissions to create resources
- For serverless models: Access granted to Azure AI Foundry marketplace

### Script Architecture

```
scripts/
├── setup.sh                    # Main interactive setup (Bash)
├── setup.ps1                   # Main interactive setup (PowerShell)
├── teardown.sh                 # Resource cleanup (Bash)
├── teardown.ps1                # Resource cleanup (PowerShell)
├── lib/
│   ├── common.sh               # Shared functions (Bash)
│   ├── common.ps1              # Shared functions (PowerShell)
│   ├── azure-openai.sh         # Azure OpenAI deployment
│   ├── azure-openai.ps1
│   ├── azure-ai.sh             # Azure AI Services deployment
│   ├── azure-ai.ps1
│   ├── serverless.sh           # Serverless endpoint deployment
│   └── serverless.ps1
└── models/
    └── catalog.json            # Model definitions with cost info
```

### Interactive Flow

1. **Welcome & Prerequisites Check**
   - Verify Azure CLI is installed and authenticated
   - Check subscription access
   - Display current subscription and confirm

2. **Resource Group Setup**
   - Prompt for resource group name (default: `foundry-tui-rg`)
   - Prompt for location (default: `eastus`)
   - Create resource group if it doesn't exist

3. **Model Selection**
   - Display available models grouped by category
   - Show estimated monthly cost for each model type
   - Allow multi-select with recommended defaults highlighted
   - Confirm selection before proceeding

4. **Azure OpenAI Setup** (if GPT/o-series models selected)
   - Create Azure OpenAI resource
   - Deploy selected models
   - Display endpoint and keys
   - Automatically populate .env

5. **Azure AI Services Setup** (if DeepSeek/Grok/Kimi selected)
   - Create Azure AI Services resource
   - Deploy selected models
   - Display endpoint and keys
   - Automatically populate .env

6. **Serverless Setup** (if Mistral/marketplace models selected)
   - Guide through Azure AI Foundry portal for marketplace models
   - Prompt for endpoint URL and key after manual deployment
   - Automatically populate .env

7. **Verification**
   - Test API connectivity for each deployed model
   - Report success/failure for each endpoint
   - Suggest troubleshooting steps if any fail

8. **Completion**
   - Display summary of deployed resources
   - Show next steps (run `uv run foundry-tui`)
   - Remind about teardown script to avoid charges

### Cost Estimates Display

```
╔══════════════════════════════════════════════════════════════════╗
║  Model Selection                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ── Azure OpenAI Models ──────────────────────────────────────   ║
║  [x] GPT-4o           ~$5/1M input, $15/1M output tokens         ║
║  [ ] GPT-4o Mini      ~$0.15/1M input, $0.60/1M output tokens    ║
║  [ ] GPT-4.1          ~$2/1M input, $8/1M output tokens          ║
║  [ ] o4-mini          ~$1.10/1M input, $4.40/1M output tokens    ║
║                                                                   ║
║  ── Azure AI Models (pay-per-token) ──────────────────────────   ║
║  [ ] DeepSeek R1      ~$0.55/1M input, $2.19/1M output tokens    ║
║  [ ] DeepSeek V3.2    ~$0.27/1M input, $1.10/1M output tokens    ║
║  [ ] Grok 3           Pricing varies                              ║
║                                                                   ║
║  ── Serverless (marketplace) ─────────────────────────────────   ║
║  [ ] Mistral Small    ~$0.10/1M input, $0.30/1M output tokens    ║
║                                                                   ║
║  Base cost: $0/month (pay per token only)                        ║
║                                                                   ║
║  ↑↓ Navigate  Space Toggle  Enter Confirm  q Quit                ║
╚══════════════════════════════════════════════════════════════════╝
```

### Teardown Script

Interactive cleanup that:
1. Lists all resources created by setup
2. Confirms deletion with user
3. Deletes in reverse order (deployments → services → resource group)
4. Cleans up .env entries (optional)

### Environment Variable Management

Scripts automatically update `.env` file:
- Backs up existing `.env` to `.env.backup`
- Adds/updates only the variables for deployed services
- Preserves user customizations in app settings section

### Error Handling

- Check Azure CLI authentication before starting
- Validate subscription quotas for requested models
- Retry transient failures with exponential backoff
- Provide clear error messages with documentation links
- Save partial progress to allow resuming

---

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Azure OpenAI API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [Azure AI Model Inference API](https://learn.microsoft.com/en-us/azure/ai-studio/reference/reference-model-inference-api)
- [OpenAI Python SDK](https://github.com/openai/openai-python) (works with Azure)
- [Azure CLI Documentation](https://learn.microsoft.com/en-us/cli/azure/)
