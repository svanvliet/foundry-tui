# Foundry TUI - Implementation Plan

## Phase 1: MVP ✅

- [x] Project Setup, Configuration, API Client, TUI, Chat Flow

---

## Phase 2: Multi-Model ✅

- [x] API Adapters (Azure OpenAI, Azure AI, Serverless)
- [x] Model Picker with fuzzy search
- [x] Commands: /models, /clear, /new, /help
- [x] Model persistence

---

## Phase 3: Polish ✅

- [x] **3.1 Markdown Rendering**
  - [x] Rich markdown in assistant messages
  - [x] Syntax highlighting for code blocks

- [x] **3.2 Status Bar Redesign**
  - [x] Animated spinner (Braille dots: ⣾ ⣽ ⣻ ⢿ ⡿ ⣟ ⣯ ⣷)
  - [x] Activity states: Ready → Sending → Thinking → Receiving → Ready
  - [x] Session token counter with color thresholds
  - [x] Provider badge
  - [x] Model category indicator (● chat, ◆ reasoning)

- [x] **3.3 Token Tracking**
  - [x] Track session total tokens
  - [x] Estimate from streaming
  - [x] Color-coded usage warnings (green/yellow/red)

- [x] **3.4 Logging**
  - [x] Session logs to `logs/`
  - [x] API request/response logging

- [x] **3.5 Tool Calling** (deferred to Phase 7)
  - Moved to future phase to focus on core UX

- [x] **3.6 Commands**
  - [x] `/copy` - copy last response to clipboard
  - [x] `/export` - export conversation to JSON

- [x] **3.7 Terminal Colors & Themes**
  - [x] Textual themes (Nord default, `/theme` command with 20 built-in themes)
  - [x] Disabled automatic retries in OpenAI SDK (`max_retries=0`) for immediate error feedback

---

## Phase 4: System Prompts ✅

- [x] `/system` command to set/view prompt
- [x] Persist system prompts to config (~/.foundry-tui/config.json)
- [x] Per-model default system prompts (deferred - add to catalog if needed)

---

## Phase 5: Conversations ✅

- [x] Auto-save conversations to disk (~/.foundry-tui/conversations/)
- [x] Conversation browser/picker (/load, /convs)
- [x] Load/resume previous conversations
- [x] Manual save with custom title (/save)

---

## Phase 6: Azure Setup Scripts ✅

Interactive setup scripts for deploying Azure resources.

- [x] **6.1 Script Infrastructure**
  - [x] `scripts/lib/common.sh` - Shared Bash functions (colors, prompts, Azure CLI wrappers)
  - [x] `scripts/lib/common.ps1` - Shared PowerShell functions

- [x] **6.2 Main Setup Script**
  - [x] `scripts/setup.sh` - Interactive Bash setup
  - [x] `scripts/setup.ps1` - Interactive PowerShell setup
  - [x] Prerequisites check (Azure CLI, authentication, subscription)
  - [x] Resource group creation with location selection
  - [x] Model selection UI with cost estimates
  - [x] Automatic .env population

- [x] **6.3 Azure OpenAI Deployment**
  - [x] Create Azure OpenAI resource
  - [x] Deploy GPT and o-series models
  - [x] Retrieve and store endpoint/keys

- [x] **6.4 Azure AI Services Deployment**
  - [x] Create Azure AI Services resource
  - [x] Note about portal deployment for marketplace models
  - [x] Retrieve and store endpoint/keys

- [x] **6.5 Teardown Script**
  - [x] `scripts/teardown.sh` - Bash cleanup
  - [x] `scripts/teardown.ps1` - PowerShell cleanup
  - [x] List and confirm resources to delete
  - [x] Delete resource group
  - [x] Optional .env cleanup

- [x] **6.6 Documentation**
  - [x] `run.sh` - Quick start script
  - [x] Updated README.md with comprehensive guide

---

## Phase 7: Tool Calling & Web Search ✅

Add function/tool calling support so models can invoke external tools during a conversation.
Ships with **Tavily Web Search** as a built-in tool (works with all tool-capable models).
Also adds an extensible registry so users can define custom tools via a JSON config file.

> **Note:** Originally planned to use Bing Search API v7, but that service was retired in August 2025.
> Pivoted to Tavily, which is purpose-built for AI tool calling and has a generous free tier (1,000 searches/month).

Tools are **auto-enabled** when the active model has `capabilities.tools: true` and at least one tool is configured.

### Design Decisions

| Decision | Choice |
|----------|--------|
| Web search API | Tavily Search API (free tier, no Azure resource needed) |
| Tool definitions | Built-in tools + user-defined tools via JSON config (`~/.foundry-tui/tools.json`) |
| Tool activation | Auto-enabled when model supports tools and tools are configured |
| UI display | Collapsible blocks in chat showing tool name + args, expandable to see results |
| Setup scripts | Extended to prompt for Tavily API key and populate .env |

---

### 7.1 — Core Data Model Changes

Update `Message` and `StreamChunk` to support the tool calling protocol.

**Files:** `api/azure_openai.py`, `storage/conversations.py`, `models.py`

- [x] **7.1.1 — Extend Message dataclass**
  - Add optional fields: `tool_calls: list[ToolCall] | None`, `tool_call_id: str | None`, `name: str | None`
  - Create `ToolCall` dataclass: `id`, `type` ("function"), `function` (name + arguments JSON string)
  - Create `ToolCallFunction` dataclass: `name`, `arguments` (JSON string)
  - Messages with `role="assistant"` can now carry `tool_calls` instead of (or alongside) `content`
  - Messages with `role="tool"` carry `tool_call_id` + `content` (the result) + `name` (tool name)

- [x] **7.1.2 — Extend StreamChunk for tool call deltas**
  - Add `tool_calls: list[ToolCallDelta] | None` to `StreamChunk`
  - `ToolCallDelta`: `index`, `id` (only on first chunk), `function` with `name` and `arguments` (partial JSON)
  - The streaming loop will accumulate these deltas to build complete `ToolCall` objects
  - Add `finish_reason="tool_calls"` handling (distinct from `"stop"`)

- [x] **7.1.3 — Update conversation serialization**
  - Change `messages: list[dict[str, str]]` → `list[dict[str, Any]]` in `Conversation`
  - Serialize `tool_calls` as nested dicts when saving to JSON
  - Deserialize back when loading conversations (backward-compatible: old convos without tool fields still load fine)
  - Update `generate_title()` / `generate_preview()` to skip tool-role messages gracefully

---

### 7.2 — Tool Registry & Execution Framework

Create the extensible tool system. Tools are Python callables registered with a JSON Schema definition.

**Files:** `tools/__init__.py`, `tools/registry.py`, `tools/base.py`, `tools/config.py`

- [x] **7.2.1 — Tool base class and types**
  - Create `tools/base.py` with abstract `Tool` class:
    ```python
    class Tool(ABC):
        name: str           # Function name sent to model
        description: str    # Shown to model in system context
        parameters: dict    # JSON Schema for arguments
        
        @abstractmethod
        async def execute(self, **kwargs) -> ToolResult: ...
    ```
  - `ToolResult` dataclass: `content: str`, `error: bool = False`
  - `ToolDefinition` — serializable format matching OpenAI tool spec:
    ```json
    {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    ```

- [x] **7.2.2 — Tool registry**
  - Create `tools/registry.py` with `ToolRegistry` class:
    - `register(tool: Tool)` — add a tool
    - `get(name: str) -> Tool | None` — look up by function name
    - `get_definitions() -> list[dict]` — return all tool schemas in OpenAI API format
    - `execute(name: str, arguments: str) -> ToolResult` — parse JSON args, call tool, return result
    - `is_empty() -> bool` — check if any tools registered
  - Registry is instantiated once in `FoundryApp.__init__` and passed to the API layer
  - Built-in tools auto-register; user-defined tools loaded from config

- [x] **7.2.3 — User-defined tools config loader**
  - Create `tools/config.py` to load tools from `~/.foundry-tui/tools.json`
  - Config format:
    ```json
    {
      "tools": [
        {
          "name": "get_weather",
          "description": "Get current weather for a city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
          },
          "endpoint": "https://api.weather.example/v1/weather",
          "method": "GET",
          "headers": {"Authorization": "Bearer ${WEATHER_API_KEY}"},
          "result_path": "$.current.summary"
        }
      ]
    }
    ```
  - `HttpTool` class: generic tool that makes HTTP requests based on config
  - Supports `${ENV_VAR}` interpolation in headers/URLs
  - Validate schemas on load; log warnings for invalid tools

---

### 7.3 — Tavily Web Search Tool (Built-in)

Implement the Tavily Search API tool as the primary built-in tool.

**Files:** `tools/tavily_search.py`

- [x] **7.3.1 — Tavily Search API client**
  - Create `tools/tavily_search.py` implementing `Tool` base class
  - Tool schema:
    ```json
    {
      "name": "web_search",
      "description": "Search the web for current information...",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "Search query"},
          "max_results": {"type": "integer", "description": "Number of results (1-10)", "default": 5}
        },
        "required": ["query"]
      }
    }
    ```
  - `execute()`:
    - POST to `https://api.tavily.com/search` with Bearer auth
    - Request `include_answer: true` for direct AI-generated answer
    - Format results: summary + numbered list of `[N] Title — URL\n    Snippet`
    - Handle errors (401 invalid key, 429 rate limit) → return `ToolResult(error=True)`
  - Uses `httpx.AsyncClient` (consistent with existing API clients)
  - Reads `TAVILY_API_KEY` from env

- [x] **7.3.2 — Auto-registration**
  - In registry init: if `TAVILY_API_KEY` env var is set, auto-register the Tavily Search tool
  - If key not set, skip silently (tool just not available)
  - Log tool registration at startup: `"Tavily Search tool configured"`

---

### ~~7.4 — Grounding with Bing~~ (Removed)

> Removed: Grounding with Bing requires Azure AI Agent SDK, which is incompatible with the
> chat completions API used by this app. May revisit if Azure adds grounding support to the
> regular completions endpoint.

---

### 7.5 — API Layer: Tool Calling Protocol

Wire the tool calling protocol into all three API clients.

**Files:** `api/azure_openai.py`, `api/azure_ai.py`, `api/serverless.py`, `api/client.py`

- [x] **7.5.1 — Azure OpenAI client: send tools + handle tool_calls in stream**
  - In `stream_chat()`: accept optional `tools: list[dict]` parameter
  - If tools provided, add `"tools": tools` to kwargs
  - Handle streaming deltas where `delta.tool_calls` exists (instead of `delta.content`):
    - Accumulate `ToolCallDelta` chunks by index
    - When `finish_reason == "tool_calls"`, yield a final chunk with assembled `tool_calls`
  - In `chat()` (non-streaming): extract `message.tool_calls` from response

- [x] **7.5.2 — Azure AI client: send tools + handle tool_calls in stream**
  - Same pattern as Azure OpenAI but via httpx JSON parsing
  - Add `"tools": tools` to the request payload
  - Parse `delta.tool_calls` from SSE JSON chunks
  - Same accumulation logic as 7.5.1

- [x] **7.5.3 — Serverless client: send tools + handle tool_calls in stream**
  - Same pattern — Mistral uses standard OpenAI tool format
  - Add `"tools": tools` to the request payload
  - Parse tool call deltas from streaming response

- [x] **7.5.4 — Unified client: pass tools through**
  - Update `ChatClient.stream_chat()` and `ChatClient.chat()` to accept `tools: list[dict] | None`
  - Pass through to whichever backend is active
  - Only pass tools if model has `capabilities.tools == True` (graceful skip otherwise)

- [x] **7.5.5 — Message serialization for API calls**
  - Update the `api_messages` construction in all clients to handle the full message format:
    - Assistant messages with `tool_calls` → include `tool_calls` field (not just `content`)
    - Tool result messages → `role: "tool"`, `tool_call_id`, `content`, `name`
  - Currently messages are dicts with only `role`+`content`; needs to carry all fields

---

### 7.6 — Chat Flow: The Tool Loop

Modify `_send_message` to implement the multi-turn tool calling loop.

**Files:** `app.py`

- [x] **7.6.1 — Implement the tool loop in _send_message**
  - After streaming a response, check if `finish_reason == "tool_calls"`
  - If yes, enter a loop:
    1. Parse the tool calls from the final stream chunk
    2. Append the assistant message (with `tool_calls`) to history
    3. For each tool call:
       a. Look up the tool in the registry
       b. Display a collapsible "calling tool" block in the UI
       c. Execute the tool asynchronously
       d. Display the result in the collapsible block
       e. Append a `role="tool"` message with the result to history
    4. Call the API again with the updated message history (including tool results)
    5. Stream the new response
    6. If the model returns more tool calls, repeat; if `finish_reason == "stop"`, break
  - Safety: cap the loop at a configurable max iterations (default: 10) to prevent runaway loops
  - Update status bar during tool execution: "Calling bing_search..." or similar

- [x] **7.6.2 — Error handling in tool loop**
  - If a tool is not found in registry → return error result to model: `"Error: Unknown tool 'xyz'"`
  - If tool execution fails → return error result: `"Error: {exception message}"`
  - If max iterations exceeded → break loop, show warning in chat
  - Network errors during tool execution → don't crash the whole message flow
  - Model returns tool_calls but model has `capabilities.tools: false` → shouldn't happen, but handle gracefully

---

### 7.7 — UI: Tool Call Display

Add collapsible tool call blocks to the chat UI.

**Files:** `ui/chat.py`, `ui/styles.tcss`

- [x] **7.7.1 — ToolCallMessage widget**
  - New `ToolCallMessage` widget (extends `Static` or `Collapsible`):
    - Collapsed: `⚡ bing_search("current weather in Seattle")` — one-line summary
    - Expanded: shows full arguments JSON + formatted result
    - Click or keybind to toggle
  - Styled distinctly from regular messages (muted color, left border accent)
  - Multiple tool calls in one turn → multiple collapsible blocks

- [x] **7.7.2 — Streaming integration**
  - While tool calls are being accumulated during streaming, show a "thinking" indicator
  - Once tool calls are identified (stream ends with `tool_calls`), immediately show the collapsible blocks
  - While each tool executes, show a spinner next to the tool block
  - After execution completes, update the block with the result

- [x] **7.7.3 — CSS styling**
  - Add styles for `.tool-call-message` — distinct visual treatment:
    - Subtle background, left border accent (e.g., blue/cyan)
    - Monospace font for arguments
    - Collapsed/expanded state styling
  - Tool error results: red accent border

---

### 7.8 — Setup Scripts: Web Search Configuration

Extend the existing setup scripts to optionally configure Tavily web search.

**Files:** `scripts/setup.sh`, `scripts/setup.ps1`

- [x] **7.8.1 — Bash setup script (setup.sh)**
  - After Azure AI Services deployment, add a new section: "Step 4: Web Search (Optional)"
  - Prompt: `"Would you like to enable web search for tool calling? (y/N)"`
  - If yes: prompt for Tavily API key and save to `.env`
  - Show note: "Get a free API key at: https://tavily.com (1,000 searches/month free)"
  - Supports `--only-search` flag to skip model deployment and go straight to search setup

- [x] **7.8.2 — PowerShell setup script (setup.ps1)**
  - Mirror the Bash changes for PowerShell
  - Supports `-OnlySearch` parameter

- [x] **7.8.3 — Teardown script updates**
  - Clean up `TAVILY_API_KEY` from .env on teardown (comment out)

- [x] **7.8.4 — Update .env.example**
  - Add `TAVILY_API_KEY=` to `.env.example`

---

### 7.9 — /tools Command & Discoverability

Add a slash command for users to manage tools.

**Files:** `app.py`

- [x] **7.9.1 — /tools command**
  - `/tools` — list all registered tools with status (enabled/available/not configured)
  - `/tools enable <name>` / `/tools disable <name>` — toggle individual tools per session
  - `/tools info <name>` — show tool schema and description
  - Show which tools are active for the current model in the tool list

- [x] **7.9.2 — Status bar tool indicator**
  - When tools are active, show a `🔧 N` indicator in the status bar (N = number of active tools)
  - When model doesn't support tools, dim or hide the indicator

---

### Implementation Order & Dependencies

```
7.1 (Data Models) ──────────┐
                             ├──→ 7.5 (API Layer) ──→ 7.6 (Chat Flow) ──→ 7.9 (Commands)
7.2 (Registry Framework) ───┤
                             ├──→ 7.3 (Tavily Search Tool)
7.8 (Setup Scripts) ────────┘
7.7 (UI) ─── depends on 7.6 for integration, but widget can be built in parallel
```

**Suggested build order:**
1. 7.1 — Data models (foundation for everything)
2. 7.2 — Registry framework (tool infrastructure)
3. 7.3 — Tavily Search tool (first concrete tool)
4. 7.5 — API layer changes (wire tools into requests/responses)
5. 7.7 — UI widgets (build tool call display)
6. 7.6 — Chat flow tool loop (bring it all together)
7. 7.8 — Setup scripts (configuration)
8. 7.9 — /tools command & status bar

---

## Phase 8: UX Polish & Observability ✅

- [x] Slash command autocomplete menu with arg-level completions (`/models` → model names, `/system` → `clear`, `/tools` → `info`, `/theme` → theme names)
- [x] Input history with Up/Down navigation (persisted to `~/.foundry-tui/input_history.txt`, last 200 entries)
- [x] Real token tracking via `stream_options: {"include_usage": true}` with prompt/completion/cached breakdown
- [x] HTTP-level request/response tracing for Azure OpenAI (request body, rate limit headers, error bodies)
- [x] Rate limit tracking (RPM/TPM ratios in catalog, actual limits persisted in config, status bar `RPM: count/limit`, model picker RPM/TPM columns)
- [x] 429 auto-retry with countdown and cancellation (max 3 retries, Escape cancels, Ctrl+C quits)
- [x] Reasoning model `<think>` tag rendering (collapsible 💭 widget, status bar "💭 Reasoning...")
- [x] Textual themes with `/theme` command (Nord default, 20 built-in themes, persisted in config.json)
- [x] Background worker for streaming (`_send_message` as Textual worker, non-blocking event loop, Escape cancels)

---

## Phase 9: Memory (Persistent User Context) ✅

Add persistent memory so models can remember facts about the user across conversations.
Three tools (`save_memory`, `recall_memories`, `forget_memory`) auto-registered for all
tool-capable models. Memories stored as human-readable Markdown at `~/.foundry-tui/memories.md`.
Models use `recall_memories` tool to look up relevant context on demand.

### Design Decisions

| Decision | Choice |
|----------|--------|
| Scope | Global — all models share the same memories |
| Storage format | Markdown (`~/.foundry-tui/memories.md`) with `##` sections |
| Recall | Tool-based — models call `recall_memories` to look up context on demand |
| Search | Semantic (embeddings) with keyword fallback when embeddings not configured |
| Proactive saving | System prompt instructs models to auto-save useful facts |
| Memory limit | None — user manages via `/memory` or direct file editing |

---

### 9.1 — Memory Storage Layer

Read/write memories to `~/.foundry-tui/memories.md`.

**File:** `storage/memory.py`

- [x] **9.1.1 — Memory dataclass and storage functions**
  - `Memory` dataclass: `id` (str, e.g. `mem_1709654321`), `content` (str), `source_model` (str), `created_at` (datetime)
  - `load_memories() -> list[Memory]` — parse `memories.md`, return list
  - `save_memory(content: str, source_model: str) -> Memory` — append new section to file, return it
  - `delete_memory(memory_id: str) -> bool` — remove section, rewrite file
  - `clear_memories() -> int` — delete all, return count
  - `search_memories(query: str) -> list[Memory]` — case-insensitive substring match
  - Create file with `# Foundry TUI Memories` header on first write

---

### 9.2 — Memory Tools (3 tools)

Implement the tools that models invoke via function calling.

**File:** `tools/memory.py`

- [x] **9.2.1 — SaveMemoryTool**
  - `name = "save_memory"`, single param: `content` (string, required)
  - `execute()`: calls `save_memory()` from storage layer, returns confirmation with memory ID
  - Description tells model: "Save a fact or preference about the user for future conversations"

- [x] **9.2.2 — RecallMemoriesTool**
  - `name = "recall_memories"`, single param: `query` (string, required)
  - `execute()`: calls `search_memories()`, formats results as numbered list
  - If no results, returns "No memories found matching: {query}"

- [x] **9.2.3 — ForgetMemoryTool**
  - `name = "forget_memory"`, single param: `memory_id` (string, required)
  - `execute()`: calls `delete_memory()`, returns success/failure message

- [x] **9.2.4 — Auto-registration in `__init__.py`**
  - Always register all 3 memory tools (no env var needed — file-based)
  - Register before Tavily so memory tools appear first in `/tools` list

---

### 9.3 — System Prompt Memory Injection

Inject all stored memories into the system prompt automatically.

**File:** `app.py`

- [x] **9.3.1 — Inject memories into API messages**
  - In `_send_message()` where `api_messages` is built, load all memories
  - Append a memory context block to the system prompt:
    ```
    ## Your memories about the user
    You have saved the following memories about the user. Use them to personalize responses.
    When you learn something new and important about the user, use save_memory to remember it.

    - User prefers Python and uses uv as their package manager.
    - User's name is Sebastiaan. They work in developer tools.
    ```
  - If no memories exist, add instruction: "You have no saved memories yet. Use save_memory when you learn useful facts about the user."
  - If no system prompt set, create one with just the memory block

---

### 9.4 — `/memory` Command

User-facing command to manage memories from the TUI.

**Files:** `app.py`, `ui/input.py`

- [x] **9.4.1 — Implement /memory command handler**
  - `/memory` — list all memories with IDs and content previews
  - `/memory search <query>` — search by keyword
  - `/memory delete <id>` — delete specific memory
  - `/memory clear` — delete all (with count confirmation)

- [x] **9.4.2 — Slash command autocomplete**
  - Add `/memory` to `SLASH_COMMANDS` list
  - Add arg completions: `search`, `delete`, `clear`
  - Add to `/help` output

---

### 9.5 — Status Bar Memory Indicator

Show memory count in status bar.

**File:** `ui/status_bar.py`, `app.py`

- [x] **9.5.1 — Memory count indicator**
  - Add `🧠 N` indicator to status bar (N = number of stored memories)
  - Update on model switch and after tool execution
  - Dim/hide if 0 memories

---

### 9.6 — Semantic Memory Search (Embeddings) ✅

Add optional Azure OpenAI embedding-based search for memories. Falls back to keyword
search when not configured. Also enables smart system prompt injection (top-5 relevant
memories instead of all) when memory count exceeds 10.

**Design Decisions:**

| Decision | Choice |
|----------|--------|
| Embedding model | `text-embedding-3-small` (1536 dims, cheapest) |
| Deployment | Auto-deployed by setup scripts alongside chat models |
| Storage | `~/.foundry-tui/memory_embeddings.json` sidecar |
| Activation | Auto-detected when `AZURE_OPENAI_ENDPOINT` + API key + model deployed |
| Fallback | Keyword substring search (current default, always works) |
| Smart injection | When embeddings available AND >10 memories, inject top-5 by relevance |

---

#### 9.6.1 — Embedding Client

**File:** `api/embeddings.py`

- [x] **Create EmbeddingClient class**
  - Uses existing `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` (no new env vars)
  - Deployment name: `text-embedding-3-small` (added to `models-catalog.json` as utility model)
  - `async embed(text: str) -> list[float]` — embed a single text, return 1536-dim vector
  - `async embed_batch(texts: list[str]) -> list[list[float]]` — batch embedding
  - `is_available() -> bool` — check if embedding model is deployed (fast HEAD check, cached)
  - Uses `openai.AsyncAzureOpenAI` client (same pattern as `azure_openai.py`)

---

#### 9.6.2 — Embedding Storage

**File:** `storage/memory.py` (extend existing)

- [x] **Add embedding sidecar management**
  - Sidecar file: `~/.foundry-tui/memory_embeddings.json`
  - Format: `{ "mem_123": [0.012, -0.034, ...], "mem_456": [...] }`
  - `save_embedding(memory_id: str, embedding: list[float])` — add/update
  - `load_embeddings() -> dict[str, list[float]]` — load all
  - `delete_embedding(memory_id: str)` — remove on memory delete
  - `clear_embeddings()` — remove all on memory clear
  - Auto-cleanup: if a memory ID exists in embeddings but not in memories.md, prune it

---

#### 9.6.3 — Semantic Search Function

**File:** `storage/memory.py` (extend existing)

- [x] **Add cosine similarity search**
  - `async semantic_search(query: str, top_k: int = 5) -> list[Memory]`
  - Embed the query using `EmbeddingClient`
  - Compute cosine similarity against all stored embeddings
  - Return top-k memories sorted by similarity
  - No external deps: cosine similarity is `dot(a,b) / (norm(a) * norm(b))` — pure Python/math

---

#### 9.6.4 — Wire Embeddings into Memory Tools

**Files:** `tools/memory.py`, `app.py`

- [x] **Update SaveMemoryTool**
  - After saving to markdown, embed the content and save to sidecar
  - If embedding fails (model not available), save memory anyway (keyword still works)

- [x] **Update RecallMemoriesTool**
  - If embeddings available: use semantic search (finds "name" → "Scott lives in...")
  - If not available: fall back to current keyword substring search

- [x] **Update ForgetMemoryTool / clear**
  - Delete embedding from sidecar when memory is deleted/cleared

---

#### 9.6.5 — Smart System Prompt Injection

**File:** `app.py`

- [x] **Conditional injection in `_build_system_prompt()`**
  - If ≤10 memories OR no embeddings: inject all memories (current behavior)
  - If >10 memories AND embeddings available: embed user's message, inject top-5 most relevant
  - Always include the "use save_memory" instruction regardless of injection mode
  - Log which memories were injected: `"Injected 5/23 memories (semantic)"`

---

#### 9.6.6 — Setup Script Updates

**Files:** `scripts/setup.sh`, `scripts/setup.ps1`

- [x] **Auto-deploy text-embedding-3-small**
  - When deploying Azure OpenAI models, automatically include `text-embedding-3-small`
  - No user prompt needed (free to deploy, pay-per-use at $0.02/1M tokens)
  - Add `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small` to `.env`
  - Teardown: include in model cleanup

- [x] **Update .env.example**
  - Add `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=` entry

---

#### 9.6.7 — Model Catalog Update

**File:** `models-catalog.json`

- [x] **Add embedding model entry**
  - New category: `"utility"` (not shown in model picker, used internally)
  - Entry: `text-embedding-3-small` with deployment type `azure_openai`
  - Not selectable as a chat model

---

### Updated Implementation Order

```
9.1–9.5 (Core Memory) ✅ ──→ 9.6.1 (Embed Client) ──→ 9.6.2 (Storage)
                              9.6.6 (Setup Scripts)     ──→ 9.6.3 (Search)
                              9.6.7 (Catalog)           ──→ 9.6.4 (Wire Tools)
                                                        ──→ 9.6.5 (Smart Inject)
```

9.6.1 + 9.6.6 + 9.6.7 can be built in parallel (no dependencies on each other).
9.6.2–9.6.5 are sequential.

---

## Phase 10: Responses API Migration ✅

Migrate Azure OpenAI models from Chat Completions API to Responses API.
Keep CAPI for Azure AI (DeepSeek, Grok, Kimi) and Serverless (Mistral) which don't support RAPI.
RAPI becomes the default for OpenAI models; CAPI adapter retained as fallback.

### Design Decisions

| Decision | Choice |
|----------|--------|
| Scope | Azure OpenAI models only (12 models) |
| Default API | RAPI for OpenAI models, CAPI for all others |
| CAPI fallback | Kept but not default — available if RAPI has issues |
| Web search | `web_search_preview` built-in for OpenAI, Tavily for others |
| Server-side state | Optional, off by default, user-configurable via `/state` |
| Streaming | Map RAPI events to existing `StreamChunk`/`ToolCallDelta` types |
| SDK | Same `openai` package — uses `client.responses.create()` |

---

### 10.1 — Responses API Client

**File:** `api/azure_openai_responses.py` (new)

Create a new adapter alongside the existing `azure_openai.py` (CAPI).

- [x] **Create `AzureOpenAIResponsesClient` class**
  - Same constructor pattern as `AzureOpenAIClient` (endpoint, api_key, api_version)
  - Reuses `AsyncAzureOpenAI` client instance with `base_url` pointing to `/openai/v1/`
  - HTTP logging hooks (same pattern as CAPI client)

- [x] **Implement `stream_response()` method**
  - Signature: `async def stream_response(deployment_name, input, tools, store, previous_response_id) -> AsyncGenerator[StreamChunk, None]`
  - Call `client.responses.create(model=..., input=..., stream=True, ...)`
  - Map streaming events to `StreamChunk`:
    - `response.output_text.delta` → `StreamChunk(content=event.delta)`
    - `response.function_call_arguments.delta` → `StreamChunk(tool_calls=[ToolCallDelta(...)])`
    - `response.completed` → `StreamChunk(usage=TokenUsage(...))`
    - `response.failed` → raise appropriate error
  - Return `response.id` for `previous_response_id` chaining (attach to final chunk or separate)

- [x] **Implement `respond()` method** (non-streaming)
  - Same as `chat()` but using `client.responses.create()` without `stream=True`
  - Returns `(content, usage, tool_calls, response_id)`

- [x] **Input format conversion**
  - Convert existing `Message` list to RAPI `input` format:
    - `{role: "user", content: "..."}` → same
    - `{role: "assistant", content: "..."}` → same
    - `{role: "system", content: "..."}` → `instructions` parameter
    - Tool results → `{type: "function_call_output", call_id: "...", output: "..."}`
  - When `previous_response_id` is set, only send the new user message (not full history)

---

### 10.2 — Built-in Web Search (web_search_preview)

**Files:** `tools/__init__.py`, `api/azure_openai_responses.py`

Replace Tavily for Azure OpenAI models with the Responses API built-in `web_search_preview`.

- [x] **Add `web_search_preview` to RAPI tool definitions**
  - When building tools for RAPI calls, inject `{"type": "web_search_preview"}` alongside function tools
  - No API key needed — native to the Responses API
  - The model decides when to invoke web search (same as Tavily behavior)

- [x] **Handle web search results in streaming**
  - RAPI returns web search results as part of the response output items
  - Parse and display search citations/sources in the UI
  - Map to existing `ToolCallMessage` widget for consistent UX

- [x] **Keep Tavily for non-OpenAI models**
  - `create_default_registry()` still registers Tavily for CAPI-based models
  - When routing through RAPI, don't send Tavily's function definition — use built-in instead
  - Tool registry needs awareness of which tools are RAPI-native vs function-based

- [x] **Update `/tools` command**
  - Show `web_search (built-in)` for OpenAI models, `web_search (Tavily)` for others
  - Indicate which tools are native vs custom

---

### 10.3 — Server-Side State Management

**Files:** `app.py`, `storage/persistence.py`, `ui/status_bar.py`, `ui/input.py`

Optional server-managed conversation state using `store=true` + `previous_response_id`.

- [x] **Add `server_state` config**
  - Persisted in `~/.foundry-tui/config.json` as `"server_state": false`
  - Default: off (local state, same as today)
  - When on: pass `store=true` and chain `previous_response_id`

- [x] **Track `previous_response_id`**
  - Store in app state: `self._last_response_id: str | None`
  - Set after each successful RAPI response
  - Clear on `/new`, `/clear`, model switch, or conversation load
  - When set + server_state enabled: only send new user message as `input`
  - When not set or server_state disabled: send full message history

- [x] **Implement `/state` command**
  - `/state` — show current state mode (local/server)
  - `/state on` — enable server-side state
  - `/state off` — disable server-side state, clear `previous_response_id`
  - Add to slash command completions in `ui/input.py`

- [x] **Status bar indicator**
  - Show `☁️` icon when server_state is active and `previous_response_id` is set
  - Show nothing when using local state

- [x] **Handle state invalidation gracefully**
  - If RAPI returns error for stale `previous_response_id`, fall back to sending full history
  - Log the fallback event
  - On model switch, clear `previous_response_id` (different model can't continue same response chain)

---

### 10.4 — Unified Client Router

**File:** `api/client.py`

Update `ChatClient` to route Azure OpenAI models to the RAPI adapter.

- [x] **Add RAPI client property**
  - `azure_openai_responses` → lazy-initialized `AzureOpenAIResponsesClient`
  - Uses same endpoint/key/version as the CAPI client

- [x] **Update `stream_chat()` routing**
  - For `azure_openai` models: call RAPI `stream_response()` by default
  - Pass `store` and `previous_response_id` parameters through
  - For `azure_ai` and `serverless`: unchanged (CAPI path)

- [x] **Handle tool definition splitting**
  - For RAPI: separate built-in tools (`web_search_preview`) from function tools
  - For CAPI: pass all tools as function definitions (current behavior)
  - The router decides which tool format based on deployment type

- [x] **Return response_id from streaming**
  - `stream_chat()` needs to communicate the RAPI `response.id` back to the caller
  - Option: attach to final `StreamChunk` or use a callback/return wrapper
  - Only set when using RAPI; None for CAPI calls

---

### 10.5 — App Integration

**File:** `app.py`

Wire RAPI into the main message sending flow.

- [x] **Update `_send_message()`**
  - Pass `store` and `previous_response_id` to `stream_chat()` when using RAPI
  - Capture `response_id` from final chunk and store as `self._last_response_id`
  - Handle RAPI tool calling loop:
    - RAPI returns tool calls differently (as output items, not `finish_reason="tool_calls"`)
    - Execute tools same as before, then send results back as `function_call_output` items
    - Use `previous_response_id` to chain tool result turns

- [x] **Update conversation state management**
  - `/new` → clear `_last_response_id`
  - `/clear` → clear `_last_response_id`
  - Model switch → clear `_last_response_id`
  - `/load` conversation → clear `_last_response_id` (can't resume server state from saved conv)
  - System prompt change → clear `_last_response_id` (instructions changed)

- [x] **Message format for RAPI**
  - System prompt → `instructions` parameter (not a message)
  - When `previous_response_id` set: input = just the new user message
  - When not set: input = full message history (same as CAPI, different format)

- [x] **Fallback handling**
  - If RAPI call fails, optionally retry via CAPI adapter
  - Log which API was used for each request

---

### 10.6 — Model Catalog Updates

**File:** `models-catalog.json`

- [x] **Add `api` field to model capabilities**
  - New field: `"api": "responses"` for OpenAI models that support RAPI
  - Default/absent = `"completions"` (CAPI)
  - Used by router to decide which adapter to use

- [x] **Mark web search support**
  - New capability: `"web_search": true` for models that support `web_search_preview`
  - All GPT-4o+ and o4-mini models get this
  - o1 and o3-mini may not support it (verify)

---

### 10.7 — Documentation & Testing

- [x] **Update README.md**
  - Mention Responses API for Azure OpenAI models
  - Note that web search works without Tavily for OpenAI models
  - Document `/state` command
  - Update env vars (Tavily now optional if only using OpenAI models)

- [x] **Update .env.example**
  - Mark `TAVILY_API_KEY` as optional (only needed for non-OpenAI web search)

- [x] **Manual testing checklist**
  - [x] GPT-4o streaming via RAPI (text only)
  - [x] GPT-4o with web_search_preview
  - [x] GPT-4o with memory tools (function calling via RAPI)
  - [x] GPT-4o with server-side state enabled
  - [x] DeepSeek/Grok via CAPI (unchanged behavior)
  - [x] Mistral via Serverless (unchanged behavior)
  - [x] Model switch clears response chain
  - [x] `/state on` / `/state off` toggle
  - [x] Conversation save/load with RAPI

---

### Implementation Order

```
10.1 (RAPI Client) ──→ 10.4 (Router) ──→ 10.5 (App Integration)
10.2 (Web Search)  ──→ 10.4 (Router)       ↓
10.6 (Catalog)     ──→ 10.4 (Router)     10.7 (Docs & Testing)
10.3 (State Mgmt)  ──→ 10.5 (App)
```

10.1 + 10.2 + 10.3 + 10.6 can be built in parallel (independent).
10.4 depends on 10.1, 10.2, 10.6.
10.5 depends on 10.3, 10.4.
10.7 is last (after integration).

---

## Phase 11: File Creation Tool & Clickable Links ✅

Add a `create_file` tool so models can save files to the user's local filesystem,
and make URLs/file paths in the TUI clickable.

### Design Decisions

| Decision | Choice |
|----------|--------|
| Output directory | `~/Downloads/` (sandboxed, no other paths allowed) |
| Path traversal | Strip all path separators from filename; bare names only |
| Duplicate filenames | Auto-suffix `_1`, `_2`, etc. |
| Blocked extensions | Binary executables only (.exe, .bat, .com, .msi, .dll, .so, .dylib) |
| Allowed extensions | All text/code/script files (.md, .txt, .py, .sh, .json, etc.) |
| Max file size | 10 MB |
| Link handling | OSC 8 terminal hyperlinks + Textual action handler |

---

### 11.1 — File Creation Tool

**File:** `tools/file_create.py` (new)

- [x] **Create `CreateFileTool` class**
  - Parameters: `filename` (str), `content` (str)
  - Sanitize filename: strip path separators (`/`, `\`), `..`, control chars, limit to 255 chars
  - Block dangerous extensions: `.exe`, `.bat`, `.com`, `.msi`, `.dll`, `.so`, `.dylib`
  - Enforce 10 MB max content size
  - Write to `~/Downloads/<filename>`
  - If file exists: try `name_1.ext`, `name_2.ext`, etc. (up to 100 attempts)
  - Return: full absolute path of created file + size in bytes
  - Tool description instructs model: "Creates a text file in the user's Downloads folder"

- [x] **Register in `tools/__init__.py`**
  - Always registered (no API key needed)
  - Available to all tool-capable models

---

### 11.2 — Clickable Links in TUI

**Files:** `ui/chat.py`, `app.py`

Make URLs and file paths in messages clickable.

- [x] **Add `action_open_link` to FoundryApp**
  - `action_open_link(url: str)` → calls `webbrowser.open(url)` for http(s) URLs
  - For `file://` or local paths → calls `subprocess.run(["open", path])` (macOS) or `xdg-open` (Linux)

- [x] **Enable link rendering in message widgets**
  - Use Textual's built-in `Markdown` widget (supports clickable links natively) instead of Rich's Markdown
  - Or: post-process rendered content to wrap URLs with `[@click=app.open_link('url')]url[/]` Rich markup
  - File paths from `create_file` results should render as clickable links

- [x] **Handle file:// links in tool results**
  - When `CreateFileTool` returns a path, format it as a clickable link in the `ToolCallMessage` widget
  - Clicking opens the file in the default application or reveals in Finder/Explorer

---

### 11.3 — Documentation

- [x] Update README with `create_file` tool description
- [x] Update `/tools` command output to show create_file
- [x] Note security model in README (sandboxed to ~/Downloads/)

---

### Implementation Order

```
11.1 (File Tool) ──→ 11.2 (Clickable Links) ──→ 11.3 (Docs)
```

11.1 and 11.2 are mostly independent but link rendering benefits from having the file tool to test with.

---

## Phase 12: Image Generation Tool ✅

~~Previously targeted GPT-image-1 (Azure OpenAI) — deprecated DALL-E 3, GPT-image-1 not available via CLI.~~
**Updated:** Use FLUX.2-pro (Black Forest Labs) on Azure AI Services instead.

### Design Decisions

| Decision | Choice |
|----------|--------|
| Image model | **FLUX.2-pro** (Black Forest Labs, Azure AI Services) |
| API | Standard Azure OpenAI Images API (`/openai/deployments/{name}/images/generations`) |
| Endpoint/Key | `AZURE_AI_ENDPOINT` + `AZURE_AI_API_KEY` (AI Services, not Azure OpenAI) |
| Tool availability | Auto-registered when `AZURE_AI_IMAGE_DEPLOYMENT` is set |
| Size | Model picks: 1024×1024, 1024×1536, 1536×1024 |
| Quality | User-configurable default (high), persisted, `/image quality <level>` |
| Output | Save to ~/Downloads/ as PNG with file:// URL |
| Filename | Auto-generated timestamp (`image_20260306_001234.png`) |
| Rate limit | 30 RPM on GlobalStandard SKU (configurable in portal) |

---

### 12.1 — Image Generation Tool (Refactor)

**File:** `tools/image_generate.py` (update existing)

- [x] **Refactor `GenerateImageTool` for FLUX.2-pro**
  - Change: use `AZURE_AI_ENDPOINT` + `AZURE_AI_API_KEY` instead of OpenAI credentials
  - Change: deployment name from env var `AZURE_AI_IMAGE_DEPLOYMENT`
  - Remove: `quality` parameter from tool (FLUX.2-pro doesn't support it the same way)
  - Keep: `prompt`, `size` parameters; same base64 decode + save logic
  - Keep: `resolve_collision()`, file:// URL, timestamp filenames

- [x] **Update `create_image_tool()` factory**
  - Read `AZURE_AI_IMAGE_DEPLOYMENT` (was `AZURE_OPENAI_IMAGE_DEPLOYMENT`)
  - Read `AZURE_AI_ENDPOINT` + `AZURE_AI_API_KEY` (was AZURE_OPENAI_*)
  - Return None if not configured

- [x] **Update `tools/__init__.py`** — update env var name

---

### 12.2 — Configuration Updates

- [x] **Update `.env.example`** — replace `AZURE_OPENAI_IMAGE_DEPLOYMENT` with `AZURE_AI_IMAGE_DEPLOYMENT`
- [x] **Update `.env`** — add `AZURE_AI_IMAGE_DEPLOYMENT=flux-2-pro`
- [x] **Update `/image` command** — remove quality references for FLUX (keep persisted quality for future use)

---

### 12.3 — Setup Scripts

- [x] **Update `setup.sh`** — deploy `flux-2-pro` on AI Services (not OpenAI)
  - Uses `--model-format "Black Forest Labs"`, `--sku-name "GlobalStandard"`
  - Writes `AZURE_AI_IMAGE_DEPLOYMENT=flux-2-pro` to `.env`
  - Remove old gpt-image-1 deployment attempt from OpenAI section

- [x] **Update `setup.ps1`** — same changes in PowerShell

---

### 12.4 — Documentation

- [x] Update README: env var table, built-in tools table
- [x] Update plan.md: mark complete

---

### Implementation Order

```
12.1 (Refactor Tool) ──→ 12.2 (Config) ──→ 12.3 (Scripts) ──→ 12.4 (Docs)
```

---

### Implementation Order

```
12.1 (Tool) ──→ 12.2 (Commands) ──→ 12.3 (Inline Display) ──→ 12.4 (Scripts) ──→ 12.5 (Docs)
```

12.1 is the core. 12.2 and 12.3 enhance UX. 12.4 and 12.5 are setup/docs.

---

## Phase 13: Advanced Features (Future)

- [x] Per-model token tracking (cumulative across sessions)
- [x] Model provisioning from catalog (in-app)
- [x] Side-by-side model comparison
- [x] Vision/image input support
- [x] Code interpreter built-in tool (RAPI)
- [x] Computer-use tool (RAPI)

---

## Current Status

**Phase**: Phase 12 — Image Generation Tool ✅ (FLUX.2-pro)
**Current Task**: None — all phases through 12 complete
**Blockers**: None

---

## Progress Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-03-04 | Phase 1 | Complete | MVP with GPT-4o streaming |
| 2026-03-04 | Phase 2 | Complete | Multi-model with fuzzy picker |
| 2026-03-04 | Phase 3 | Complete | Markdown, logging, status bar, commands |
| 2026-03-04 | Status bar fix | Complete | Fixed CSS selectors, optimized streaming performance |
| 2026-03-04 | Env refactor | Complete | Moved serverless endpoints to .env, created .env.example |
| 2026-03-04 | Setup scripts design | Complete | Added requirements for interactive Bash/PowerShell setup |
| 2026-03-04 | Phase 4 | Complete | /system command with persistence |
| 2026-03-04 | Phase 5 | Complete | Auto-save conversations, load/save commands, picker |
| 2026-03-04 | Phase 6 | Complete | Setup/teardown scripts, run.sh, comprehensive README |
| 2026-03-04 | Rate limit fix | Complete | Disabled OpenAI SDK auto-retries (max_retries=0) |
| 2026-03-04 | Terminal colors | Complete | ANSI_COLOR=True + ansi_default for terminal background |
| 2026-03-05 | Phase 7 plan | Complete | Tool calling + Bing Search + Grounding + custom tools |
| 2026-03-05 | Phase 7 | Complete | Tool calling with Tavily web search |
| 2026-03-05 | Bing → Tavily pivot | Complete | Bing Search v7 retired; switched to Tavily |
| 2026-03-05 | Phase 8 | Complete | UX polish, token tracking, themes, rate limits |
| 2026-03-05 | Phase 9 plan | Complete | Memory tools design with global markdown storage |
| 2026-03-05 | Phase 9.1–9.5 | Complete | Memory tools, storage, injection, /memory command, status bar |
| 2026-03-05 | Phase 9.6 plan | Complete | Semantic memory search via Azure OpenAI embeddings |
| 2026-03-05 | Phase 9.6 | Complete | Semantic memory search with Azure OpenAI text-embedding-3-small embeddings |
| 2026-03-05 | Memory recall | Complete | Switched from system prompt injection to tool-based recall for better accuracy |
| 2026-03-05 | Phase 10 plan | Complete | Responses API migration for Azure OpenAI models |
| 2026-03-05 | Phase 10 | Complete | Responses API for Azure OpenAI models with built-in web search and server-side state |
| 2026-03-05 | Phase 11 plan | Complete | File creation tool with security sandboxing + clickable TUI links |
| 2026-03-05 | Phase 11 | Complete | create_file tool (~/Downloads/ sandbox), clickable links via Textual Markdown |
| 2026-03-06 | Phase 12 plan | Complete | Image generation tool via GPT-image-1 deployment |
| 2026-03-06 | Phase 12 | Complete | generate_image tool, /image command, setup scripts. Inline display deferred. |
