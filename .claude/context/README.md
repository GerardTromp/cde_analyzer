# Claude Code Context Files

This directory contains structured context files for session recovery.

## Quick Recovery (Recommended)

For most session recovery, read these in order:
1. **`CLAUDE.md`** (project root) — authoritative current state (v1.6.0)
2. **`.claude/checkpoints/checkpoint-2026-04-04-v151-consolidated.md`** — full project state, consolidates all prior checkpoints
3. **`08-progress.md`** — current progress summary and version history

## Active Context Files

### [01-architecture.md](01-architecture.md)
**Core system architecture** — layered monolithic design, action system, data flow.

### [02-codebase-map.md](02-codebase-map.md)
**Directory structure** — actions, logic, utils, core, CDE_Schema, config, workflows.

### [03-data-models.md](03-data-models.md)
**Data models** — Pydantic CDE schemas, pattern TSV format, ledger format, workflow YAML.

### [04-patterns.md](04-patterns.md)
**Design patterns and coding conventions** — plugin registry, factory, visitor,
configuration patterns.

### [05-decisions.md](05-decisions.md)
**Architecture Decision Records** — 13 ADRs covering layout, lazy loading, branching
strip, field-aware splits, incremental curation, action refactoring.

### [06-dependencies.md](06-dependencies.md)
**Dependencies** — runtime, dev, optional packages; spaCy model; Python version; tool config.

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
Retained for historical reference only.
