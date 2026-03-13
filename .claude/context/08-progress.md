# Progress and Current State

## Current Branch: main

**Focus**: Production release — config-driven scaffold, action refactoring, reference ledger

**Version**: 1.0.0 (2026-03-12)

## Current State (v1.0.0)

### Production Release

**v1.0.0 changes**:
- `pattern_util` split into focused actions: `curation`, `instrument_util`, `pattern_diag`, `supplementary`
- Config-driven pipeline scaffold (`workflow scaffold --from-config`)
- Reference curation ledger shipped at `data/reference_ledger/`
- Development Status upgraded to Production/Stable
- All workflow YAMLs and pipeline scripts updated to new action names

### All Pipeline Phases — Complete

**Phase 1: Instrument Pipeline** — 1,342 raw → 591 coalesced → 458 validated patterns → field-aware splits (383 full + 252 sub)
**Phase 2: Phrase Pipeline** — 4,023 patterns curated (171 keep, 3,743 remove, 102 modify, 7 substitute)
**Phase 3: Branching Strip** — 7 variant outputs; N-way 3-step single-pass with field-aware splits (all 7 distinct)

### Curation Infrastructure — Complete

- **5 decision types**: keep, remove, modify, substitute, followup
- **Containment tree** (v0.9.5): prefix+tinyId hierarchy for curation efficiency
- **Multi-curator workflow** (v0.6.0): init/merge with inter-rater stats
- **Standalone TSV editor** (v0.7.0): zipapp distribution (`cde_editor.pyz`, ~59 KB)
- **Centralized curation server** (v0.7.0): HMAC token auth, TLS, rate limiting
- **Incremental curation ledger** (v0.8.0): auto-resolve from prior decisions, gate/finalize
- **Zipf priority split** (v0.9.0): triage needs_review by word frequency
- **Reference ledger** (v1.0.0): `data/reference_ledger/` — bootstrap new projects

### Production Tooling — Complete

- **N-way branching strip** (v0.9.2): `strip_branching` — single-pass engine, all 7 variants
- **Field-aware splits** (v0.9.8): genuinely independent inst_full/inst_sub text spans
- **Strip configurator** (v0.9.1): `workflow configure CODE [-o FILE] [--nway]`
- **Config-driven scaffold** (v1.0.0): `workflow scaffold --from-config pipeline_config.yaml`
- **Documentation**: 8 vignettes, 28 help files, 4 cheatsheets, MkDocs site

## Recent Versions

| Version | Date | Summary |
|---------|------|---------|
| 1.0.0 | 2026-03-12 | Production release: action split, config scaffold, reference ledger |
| 0.9.8 | 2026-03-11 | Field-aware splits, 7-way branching strip, group-scoped re-matching |
| 0.9.6 | 2026-03-09 | 5-way branching strip, allcde03 production run (104s), curator briefing |
| 0.9.5 | 2026-03-09 | Containment tree view in TSV editor (prefix+tinyId hierarchy) |
| 0.9.4 | 2026-03-07 | Deferred parent filter, anchor trim control, followup decision, doc audit |
| 0.9.2 | 2026-03-03 | N-way single-pass branching strip engine, tinyid_count column |
| 0.9.1 | 2026-03-03 | Production strip configurator, --only-steps |
| 0.9.0 | 2026-02-26 | Zipf priority split, editor UX, version sync |
| 0.8.0 | 2026-02-24 | Incremental curation with ledger and gate |
| 0.7.0 | 2026-02-23 | Standalone editor zipapp, centralized server, synthetic QC |
| 0.6.0 | 2026-02-21 | Multi-curator, workflow scaffold, 7 vignettes |

## What Remains

- **LLM-assisted classification** — implemented (`llm_classify` action), not yet integrated into pipeline
- **Position-specific field-aware stripping** — architecture ready in branching_stripper
- **Embedding evaluation** — run extract_embed on 7 branching-strip outputs
- **Full regression test** — legacy vs nway branching strip on allcde03 after curation
