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

## Phase 3: Polish (IN PROGRESS)

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

- [ ] **3.5 Tool Calling** (deferred to Phase 6)
  - Moved to future phase to focus on core UX

- [x] **3.6 Commands**
  - [x] `/copy` - copy last response to clipboard
  - [x] `/export` - export conversation to JSON

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

## Phase 6: Azure Setup Scripts

Interactive setup scripts for deploying Azure resources.

- [ ] **6.1 Script Infrastructure**
  - [ ] `scripts/lib/common.sh` - Shared Bash functions (colors, prompts, Azure CLI wrappers)
  - [ ] `scripts/lib/common.ps1` - Shared PowerShell functions
  - [ ] `scripts/models/catalog.json` - Model definitions with cost estimates

- [ ] **6.2 Main Setup Script**
  - [ ] `scripts/setup.sh` - Interactive Bash setup
  - [ ] `scripts/setup.ps1` - Interactive PowerShell setup
  - [ ] Prerequisites check (Azure CLI, authentication, subscription)
  - [ ] Resource group creation with location selection
  - [ ] Model selection UI with cost estimates
  - [ ] Automatic .env population

- [ ] **6.3 Azure OpenAI Deployment**
  - [ ] `scripts/lib/azure-openai.sh` / `.ps1`
  - [ ] Create Azure OpenAI resource
  - [ ] Deploy GPT and o-series models
  - [ ] Retrieve and store endpoint/keys

- [ ] **6.4 Azure AI Services Deployment**
  - [ ] `scripts/lib/azure-ai.sh` / `.ps1`
  - [ ] Create Azure AI Services resource
  - [ ] Deploy DeepSeek, Grok, Kimi models
  - [ ] Retrieve and store endpoint/keys

- [ ] **6.5 Serverless Deployment**
  - [ ] `scripts/lib/serverless.sh` / `.ps1`
  - [ ] Guide for marketplace model deployment (requires portal)
  - [ ] Prompt for endpoint/key after manual deployment
  - [ ] Validate connectivity

- [ ] **6.6 Teardown Script**
  - [ ] `scripts/teardown.sh` - Bash cleanup
  - [ ] `scripts/teardown.ps1` - PowerShell cleanup
  - [ ] List and confirm resources to delete
  - [ ] Delete in correct order
  - [ ] Optional .env cleanup

- [ ] **6.7 Verification & Testing**
  - [ ] Test API connectivity for each endpoint
  - [ ] Validate model responses
  - [ ] Error reporting with troubleshooting links

---

## Phase 7: Advanced Features (Future)

- [ ] Tool/function calling support
- [ ] Per-model token tracking (cumulative across sessions)
- [ ] Model provisioning from catalog (in-app)
- [ ] Side-by-side model comparison
- [ ] Image/vision support

---

## Current Status

**Phase**: 6 - Azure Setup Scripts (Not Started)
**Current Task**: Implement setup script infrastructure
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
