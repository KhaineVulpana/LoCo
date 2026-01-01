# Agentic Context Engineering (ACE)

ACE makes the agent improve over time without ballooning prompts.

## Artifact types
- Constitution: durable project rules (style, constraints, do/don’t)
- Runbook: verified commands and procedures (tests, build, dev server)
- Gotchas: failure → fix patterns (env vars, ordering, tooling quirks)
- Decisions: architectural decisions with brief rationale
- Glossary: domain terms → code locations/symbols

## When artifacts are created/updated
After a task reaches a stable checkpoint:
- tests pass
- build succeeds
- user approves a patch

## Quality gates (what gets persisted)
- 1–5 bullet points
- scoped (workspace/module)
- verifiable (includes command or file evidence)
- tagged for retrieval

## Retrieval priority at task start
1) Constitution
2) Relevant gotchas (module-specific)
3) Runbook (commands)
4) Decisions
5) Glossary

## Context budget discipline
ACE artifacts are “small but high leverage”.
They should be preferred over large raw logs.
