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

## Phase 7: Advanced Features (Future)

- [ ] Tool/function calling support
- [ ] Per-model token tracking (cumulative across sessions)
- [ ] Model provisioning from catalog (in-app)
- [ ] Side-by-side model comparison
- [ ] Image/vision support

---

## Current Status

**Phase**: Phases 1-6 Complete
**Current Task**: Ready for Phase 7 (Advanced Features)
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
