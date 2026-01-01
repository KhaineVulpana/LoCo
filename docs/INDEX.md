# LoCo Agent Local - Complete Documentation

## Core Documentation (Read First)

### 1. **README.md**
High-level overview of the project, key design choices, quick start guide, and directory structure.

### 2. **ARCHITECTURE.md**
System architecture: extension (rich client) vs server (authoritative brain), data flow, context gathering strategy, and why we chose custom sidebar over Chat Participant API.

### 3. **UI_UX.md**
Complete UI/UX specification matching Codex/Claude Code: sidebar layout, chat interface, @ mentions, slash commands, diff previews, file changes tree, streaming indicators, settings UI.

## Protocol & Communication

### 4. **PROTOCOL.md**
HTTP + WebSocket protocol specification: message schemas, context structure, patch format, command execution, file watching for incremental indexing. Contract-first design.

### 5. **VERSIONING.md**
Protocol versioning strategy, backward compatibility rules, feature flags, deprecation policy, migration paths, and compatibility testing.

## Intelligence & Retrieval

### 6. **RAG_AND_INDEXING.md**
Indexing pipeline (incremental, file-watcher based), multi-source retrieval (symbol/text/vector), agentic RAG loop, context pack structure, caching strategies, and quality metrics.

### 7. **ACE.md**
Agentic Context Engineering: artifact types (constitution, runbook, gotchas, decisions, glossary), when artifacts are created, quality gates, and retrieval priority.

## Data & State

### 8. **DATA_MODEL.md**
Complete SQL schema with types, constraints, foreign keys, and indexes: workspaces, sessions, messages, audit logs (tool_events, patch_events, command_events), files, chunks, symbols, dependencies, ACE artifacts, embedding cache.

## Security & Safety

### 9. **SECURITY.md**
Threat model, defense layers (auth, workspace trust, policies, prompt injection defense, command sandbox, audit logging), security checklist, best practices, and incident response plan.

## Resilience & Quality

### 10. **ERROR_HANDLING.md**
Failure modes and mitigation: indexing failures, context size limits, model context window detection, diff conflicts, resource limits, scaling strategies, observability (logging, metrics, debugging), graceful degradation, and testing strategy (TDD from day one).

## Planning & Milestones

### 11. **ROADMAP.md**
8-phase roadmap from foundation to advanced features:
- Phase 1: Core Infrastructure (server, extension, protocol)
- Phase 2: Repo Intelligence (indexing, retrieval)
- Phase 3: Codex-like UI (sidebar, @ mentions, slash commands)
- Phase 4: Diff & Patch (multi-file editing)
- Phase 5: Agentic Loop (iterative fix → run → verify)
- Phase 6: ACE (learning from patterns)
- Phase 7: Hardening & Polish
- Phase 8: Advanced Features (future)

## Reference

### 12. **RESEARCH_NOTES.md**
Research decisions and citations: why Webview, why Qdrant, why this architecture.

---

## Reading Order (Recommended)

### For Product Understanding:
1. README.md
2. UI_UX.md
3. ARCHITECTURE.md
4. ROADMAP.md

### For Implementation:
1. ARCHITECTURE.md
2. PROTOCOL.md
3. DATA_MODEL.md
4. RAG_AND_INDEXING.md
5. ERROR_HANDLING.md
6. SECURITY.md

### For Advanced Topics:
1. ACE.md
2. VERSIONING.md
3. RESEARCH_NOTES.md

---

## Document Cross-References

**ARCHITECTURE.md** references:
- PROTOCOL.md (for message schemas)
- UI_UX.md (for extension UI design)
- SECURITY.md (for policy enforcement)

**PROTOCOL.md** references:
- DATA_MODEL.md (for session/message storage)
- VERSIONING.md (for version negotiation)

**RAG_AND_INDEXING.md** references:
- DATA_MODEL.md (for files/chunks/symbols tables)
- ACE.md (for artifact retrieval)
- ERROR_HANDLING.md (for failure handling)

**ROADMAP.md** references:
- All other docs for phase details

---

## File Structure in Your Repo

```
docs/
├── README.md                  # Project overview
├── ARCHITECTURE.md            # System design
├── UI_UX.md                   # UI/UX specification
├── PROTOCOL.md                # API & WebSocket protocol
├── VERSIONING.md              # Version compatibility
├── RAG_AND_INDEXING.md        # Indexing & retrieval
├── ACE.md                     # Context engineering
├── DATA_MODEL.md              # SQL schemas
├── SECURITY.md                # Security & sandboxing
├── ERROR_HANDLING.md          # Resilience & testing
├── ROADMAP.md                 # Implementation milestones
└── RESEARCH_NOTES.md          # Design decisions
```

---

## Total: 12 Documents

All docs are production-ready and comprehensive.
