# Progress and Current State

## Current Branch: main

**Focus**: Automated instrument/phrase stripping pipeline for CDE text normalization

**Version**: 0.9.0 (2026-02-26)

## Current State (v0.9.0)

### All Pipeline Phases — Complete

**Phase 1: Instrument Pipeline** — 1,342 raw → 591 coalesced → 458 validated patterns
**Phase 2: Phrase Pipeline** — 86 curated phrases, 6 removed; 13,640 k-mer phrases mined
**Phase 3: Branching Strip** — 6 variant outputs, 13-step pipeline, ~4.5 min runtime, 0 temporal remnants

### Curation Infrastructure — Complete

- **Multi-curator workflow** (v0.6.0): init/merge with inter-rater stats (Cohen's/Fleiss' kappa, Krippendorff's alpha)
- **Standalone TSV editor** (v0.7.0): zipapp distribution (`cde_editor.pyz`, ~59 KB)
- **Centralized curation server** (v0.7.0): HMAC token auth, TLS, rate limiting, admin dashboard
- **Incremental curation ledger** (v0.8.0): auto-resolve from prior decisions, gate/finalize workflow
- **Substitute decision** (v0.8.1): 4th decision type replacing matched text with modification content
- **Zipf priority split** (v0.9.0): triage needs_review by word frequency for fast curation

### Tooling — Complete

- **Workflow scaffold** (v0.6.0): auto-generate bash scripts with Windows→WSL conversion
- **Documentation** (v0.5.17–v0.6.0): 7 vignettes, SVG diagrams, CLI short options, MkDocs site

## Recent Versions

| Version | Date | Summary |
|---------|------|---------|
| 0.9.0 | 2026-02-26 | Zipf priority split, editor UX, version sync |
| 0.8.1 | 2026-02-25 | Substitute decision type |
| 0.8.0 | 2026-02-24 | Incremental curation with ledger and gate |
| 0.7.0 | 2026-02-23 | Standalone editor zipapp, centralized server, synthetic QC |
| 0.6.0 | 2026-02-21 | Multi-curator, workflow scaffold, 7 vignettes |
| 0.5.17 | 2026-02-18 | Documentation restructuring, SVG diagrams, CLI shorts |
| 0.5.14 | 2026-02-12 | Split temporal/curated strip pipeline |

## Branches

### Active: main
- **Contains**: Everything through v0.9.0
- **Status**: All pipeline phases complete, full curation infrastructure

### Retired: phrase-curator (merged at v0.5.14)
- Merged into main on 2026-02-12

## What Remains

- **Priority 3 — LLM-assisted classification** (not started)
- **Priority 4 — Field-aware stripping** (not started)
- **Embedding evaluation** — run extract_embed on 6 branching-strip outputs
