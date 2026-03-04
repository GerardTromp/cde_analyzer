# Progress and Current State

## Current Branch: field-aware-strip

**Focus**: N-way single-pass branching strip engine

**Version**: 0.9.2 (2026-03-03)

## Current State (v0.9.2)

### All Pipeline Phases — Complete

**Phase 1: Instrument Pipeline** — 1,342 raw → 591 coalesced → 458 validated patterns
**Phase 2: Phrase Pipeline** — 86 curated phrases, 6 removed; 13,640 k-mer phrases mined
**Phase 3: Branching Strip** — 6 variant outputs; legacy 13-step pipeline or N-way 3-step single-pass

### Production Tooling — Complete

- **N-way branching strip** (v0.9.2): `strip_branching` — single-pass engine producing all variants simultaneously
- **Strip configurator** (v0.9.1): `workflow configure CODE [-o FILE] [--nway]` maps codes to steps
- **Step filtering** (v0.9.1): `--only-steps S1,S2,...` generic step filter for any workflow

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
| 0.9.2 | 2026-03-03 | N-way single-pass branching strip engine, tinyid_count column |
| 0.9.1 | 2026-03-03 | Production strip configurator, --only-steps, 6th variant (MTSTPT) |
| 0.9.0 | 2026-02-26 | Zipf priority split, editor UX, version sync |
| 0.8.1 | 2026-02-25 | Substitute decision type |
| 0.8.0 | 2026-02-24 | Incremental curation with ledger and gate |
| 0.7.0 | 2026-02-23 | Standalone editor zipapp, centralized server, synthetic QC |
| 0.6.0 | 2026-02-21 | Multi-curator, workflow scaffold, 7 vignettes |
| 0.5.17 | 2026-02-18 | Documentation restructuring, SVG diagrams, CLI shorts |
| 0.5.14 | 2026-02-12 | Split temporal/curated strip pipeline |

## Branches

### Active: field-aware-strip (from main)
- **Contains**: Everything through v0.9.2
- **Status**: N-way branching strip engine, tinyid_count column

### Active: main
- **Contains**: Everything through v0.9.1 + tinyid_count + context-aware examples
- **Status**: All pipeline phases complete, full curation infrastructure, production strip tooling

### Retired: phrase-curator (merged at v0.5.14)
- Merged into main on 2026-02-12

## What Remains

- **Priority 3 — LLM-assisted classification** (not started)
- **Position-specific field-aware stripping** — architecture ready in branching_stripper
- **Embedding evaluation** — run extract_embed on 6 branching-strip outputs
