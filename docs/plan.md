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

## Phase 4: System Prompts

- [ ] `/system` command to set/view prompt
- [ ] Per-model default system prompts
- [ ] Persist system prompts to config

---

## Phase 5: Conversations

- [ ] Auto-save conversations to disk
- [ ] Conversation browser/picker
- [ ] Load/resume previous conversations

---

## Phase 6: Advanced Features (Future)

- [ ] Tool/function calling support
- [ ] Per-model token tracking (cumulative across sessions)
- [ ] Model provisioning from catalog
- [ ] Side-by-side model comparison
- [ ] Image/vision support

---

## Current Status

**Phase**: 3 - Polish (Complete)
**Current Task**: Ready for Phase 4
**Blockers**: None

---

## Progress Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-03-04 | Phase 1 | Complete | MVP with GPT-4o streaming |
| 2026-03-04 | Phase 2 | Complete | Multi-model with fuzzy picker |
| 2026-03-04 | Phase 3 | Complete | Markdown, logging, status bar, commands |
| 2026-03-04 | Status bar fix | Complete | Fixed CSS selectors, optimized streaming performance |
