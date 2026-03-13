# Claude Code Context Files

This directory contains structured context files for session recovery.

## Quick Recovery (Recommended)

For most session recovery, read these in order:
1. **`CLAUDE.md`** (project root) — authoritative current state (v1.0.0)
2. **`.claude/checkpoints/checkpoint-2026-03-12-v100-consolidated.md`** — full history
3. **`08-progress.md`** — current progress summary

## Active Context Files

### [01-architecture.md](01-architecture.md)
**Core system architecture** — layered monolithic design, action system, data flow.
Valid for understanding foundational architecture.

### [04-patterns.md](04-patterns.md)
**Design patterns and coding conventions** — plugin registry, factory, visitor,
configuration patterns. Core patterns still valid.

### [07-gotchas.md](07-gotchas.md)
**Known issues, pitfalls, workarounds** — configuration, performance, data handling.

### [08-progress.md](08-progress.md)
**Current state and version history** — the primary status file.

### Supplementary Research (09–12)

- **[09-knowledge-graph-approach.md](09-knowledge-graph-approach.md)** — Graph-based pattern relationships
- **[10-semantic-substitutor-brief.md](10-semantic-substitutor-brief.md)** — Semantic proxy alternative
- **[11-branching-strip-curation-run.md](11-branching-strip-curation-run.md)** — Knowledge graph grouping
- **[12-information-loss-analysis.md](12-information-loss-analysis.md)** — Text removal quantification

## Archived

Files in `archive/` are from early project phases (2026-01-07) and reference a
different project context (cde-clustering with Hydra, PostgreSQL, MLflow, CVIs).
Retained for historical reference:
- `02-codebase-map.md` — stale file/directory listings
- `03-data-models.md` — PostgreSQL/MLflow schemas (not this project)
- `05-decisions.md` — ADRs for Hydra/PostgreSQL (not this project)
- `06-dependencies.md` — stale dependency listings
