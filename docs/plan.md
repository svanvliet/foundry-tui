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

- [ ] **3.5 Tool Calling** (deferred to Phase 7)
  - Moved to future phase to focus on core UX

- [x] **3.6 Commands**
  - [x] `/copy` - copy last response to clipboard
  - [x] `/export` - export conversation to JSON

- [x] **3.7 Terminal Background Colors**
  - [x] Use ANSI default colors (`ansi_default`) for terminal background inheritance
  - [x] Set `ANSI_COLOR = True` on App to preserve ANSI color codes
  - [x] Disabled automatic retries in OpenAI SDK (`max_retries=0`) for immediate error feedback

---

## Phase 4: System Prompts ✅

- [x] `/system` command to set/view prompt
- [x] Persist system prompts to config (~/.foundry-tui/config.json)
- [ ] Per-model default system prompts (deferred - add to catalog if needed)

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

## Phase 7: Tool Calling & Web Search

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

- [ ] **7.1.1 — Extend Message dataclass**
  - Add optional fields: `tool_calls: list[ToolCall] | None`, `tool_call_id: str | None`, `name: str | None`
  - Create `ToolCall` dataclass: `id`, `type` ("function"), `function` (name + arguments JSON string)
  - Create `ToolCallFunction` dataclass: `name`, `arguments` (JSON string)
  - Messages with `role="assistant"` can now carry `tool_calls` instead of (or alongside) `content`
  - Messages with `role="tool"` carry `tool_call_id` + `content` (the result) + `name` (tool name)

- [ ] **7.1.2 — Extend StreamChunk for tool call deltas**
  - Add `tool_calls: list[ToolCallDelta] | None` to `StreamChunk`
  - `ToolCallDelta`: `index`, `id` (only on first chunk), `function` with `name` and `arguments` (partial JSON)
  - The streaming loop will accumulate these deltas to build complete `ToolCall` objects
  - Add `finish_reason="tool_calls"` handling (distinct from `"stop"`)

- [ ] **7.1.3 — Update conversation serialization**
  - Change `messages: list[dict[str, str]]` → `list[dict[str, Any]]` in `Conversation`
  - Serialize `tool_calls` as nested dicts when saving to JSON
  - Deserialize back when loading conversations (backward-compatible: old convos without tool fields still load fine)
  - Update `generate_title()` / `generate_preview()` to skip tool-role messages gracefully

---

### 7.2 — Tool Registry & Execution Framework

Create the extensible tool system. Tools are Python callables registered with a JSON Schema definition.

**Files:** `tools/__init__.py`, `tools/registry.py`, `tools/base.py`, `tools/config.py`

- [ ] **7.2.1 — Tool base class and types**
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

- [ ] **7.2.2 — Tool registry**
  - Create `tools/registry.py` with `ToolRegistry` class:
    - `register(tool: Tool)` — add a tool
    - `get(name: str) -> Tool | None` — look up by function name
    - `get_definitions() -> list[dict]` — return all tool schemas in OpenAI API format
    - `execute(name: str, arguments: str) -> ToolResult` — parse JSON args, call tool, return result
    - `is_empty() -> bool` — check if any tools registered
  - Registry is instantiated once in `FoundryApp.__init__` and passed to the API layer
  - Built-in tools auto-register; user-defined tools loaded from config

- [ ] **7.2.3 — User-defined tools config loader**
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

- [ ] **7.5.1 — Azure OpenAI client: send tools + handle tool_calls in stream**
  - In `stream_chat()`: accept optional `tools: list[dict]` parameter
  - If tools provided, add `"tools": tools` to kwargs
  - Handle streaming deltas where `delta.tool_calls` exists (instead of `delta.content`):
    - Accumulate `ToolCallDelta` chunks by index
    - When `finish_reason == "tool_calls"`, yield a final chunk with assembled `tool_calls`
  - In `chat()` (non-streaming): extract `message.tool_calls` from response

- [ ] **7.5.2 — Azure AI client: send tools + handle tool_calls in stream**
  - Same pattern as Azure OpenAI but via httpx JSON parsing
  - Add `"tools": tools` to the request payload
  - Parse `delta.tool_calls` from SSE JSON chunks
  - Same accumulation logic as 7.5.1

- [ ] **7.5.3 — Serverless client: send tools + handle tool_calls in stream**
  - Same pattern — Mistral uses standard OpenAI tool format
  - Add `"tools": tools` to the request payload
  - Parse tool call deltas from streaming response

- [ ] **7.5.4 — Unified client: pass tools through**
  - Update `ChatClient.stream_chat()` and `ChatClient.chat()` to accept `tools: list[dict] | None`
  - Pass through to whichever backend is active
  - Only pass tools if model has `capabilities.tools == True` (graceful skip otherwise)

- [ ] **7.5.5 — Message serialization for API calls**
  - Update the `api_messages` construction in all clients to handle the full message format:
    - Assistant messages with `tool_calls` → include `tool_calls` field (not just `content`)
    - Tool result messages → `role: "tool"`, `tool_call_id`, `content`, `name`
  - Currently messages are dicts with only `role`+`content`; needs to carry all fields

---

### 7.6 — Chat Flow: The Tool Loop

Modify `_send_message` to implement the multi-turn tool calling loop.

**Files:** `app.py`

- [ ] **7.6.1 — Implement the tool loop in _send_message**
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

- [ ] **7.6.2 — Error handling in tool loop**
  - If a tool is not found in registry → return error result to model: `"Error: Unknown tool 'xyz'"`
  - If tool execution fails → return error result: `"Error: {exception message}"`
  - If max iterations exceeded → break loop, show warning in chat
  - Network errors during tool execution → don't crash the whole message flow
  - Model returns tool_calls but model has `capabilities.tools: false` → shouldn't happen, but handle gracefully

---

### 7.7 — UI: Tool Call Display

Add collapsible tool call blocks to the chat UI.

**Files:** `ui/chat.py`, `ui/styles.tcss`

- [ ] **7.7.1 — ToolCallMessage widget**
  - New `ToolCallMessage` widget (extends `Static` or `Collapsible`):
    - Collapsed: `⚡ bing_search("current weather in Seattle")` — one-line summary
    - Expanded: shows full arguments JSON + formatted result
    - Click or keybind to toggle
  - Styled distinctly from regular messages (muted color, left border accent)
  - Multiple tool calls in one turn → multiple collapsible blocks

- [ ] **7.7.2 — Streaming integration**
  - While tool calls are being accumulated during streaming, show a "thinking" indicator
  - Once tool calls are identified (stream ends with `tool_calls`), immediately show the collapsible blocks
  - While each tool executes, show a spinner next to the tool block
  - After execution completes, update the block with the result

- [ ] **7.7.3 — CSS styling**
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

- [ ] **7.9.1 — /tools command**
  - `/tools` — list all registered tools with status (enabled/available/not configured)
  - `/tools enable <name>` / `/tools disable <name>` — toggle individual tools per session
  - `/tools info <name>` — show tool schema and description
  - Show which tools are active for the current model in the tool list

- [ ] **7.9.2 — Status bar tool indicator**
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

## Phase 8: Advanced Features (Future)

- [ ] Per-model token tracking (cumulative across sessions)
- [ ] Model provisioning from catalog (in-app)
- [ ] Side-by-side model comparison
- [ ] Image/vision support

---

## Current Status

**Phase**: Phase 7 — Tool Calling & Web Search
**Current Task**: Ready for implementation
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
