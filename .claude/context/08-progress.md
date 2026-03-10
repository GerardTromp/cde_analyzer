# Progress and Current State

## Current Branch: field-aware-strip

**Focus**: Phrase pipeline correctness, curation UX, documentation

**Version**: 0.9.6 (2026-03-10)

## Current State (v0.9.6)

### All Pipeline Phases — Complete

**Phase 1: Instrument Pipeline** — 1,342 raw → 591 coalesced → 458 validated patterns
**Phase 2: Phrase Pipeline** — 4,006 patterns (with deferred parent filter + no-trim-anchors); curation in progress
**Phase 3: Branching Strip** — 7 variant outputs (complete 2³-1 grid); legacy 14-step pipeline or N-way 3-step single-pass (104s for 22,743 CDEs)

### Containment Tree in TSV Editor (v0.9.5–v0.9.6)

- **Prefix-containment tree**: Automatic hierarchical grouping by text prefix + tinyId subset containment
- **818/4006 patterns** (20%) fully contained by shorter prefixes in allcde03
- **Tree sort** (`T`), **tree propagate** (⊃), **tree filter** (root/child/none)
- **Virtual column**: Not saved to TSV — computed client-side on load

### Phrase Pipeline Correctness (v0.9.4)

- **Deferred parent filter** (`--defer-parent-filter`): Weak-parent patterns participate in prefix extraction before filtering
- **No-trim-anchors** (`--no-trim-anchors`): Disables Phase 0 anchor trimming for phrases
- **Prefix consolidation** (phrase_miner): Post-loop token-ID prefix trie recovers fragmented prefixes
- **Ledger pre-masking** (`--ledger-dir`): Prior "remove" decisions pre-masked during mining

### Curation Infrastructure — Complete

- **5 decision types**: keep, remove, modify, substitute, followup (v0.9.4: followup added)
- **Containment tree** (v0.9.5): prefix+tinyId hierarchy for curation efficiency
- **Multi-curator workflow** (v0.6.0): init/merge with inter-rater stats
- **Standalone TSV editor** (v0.7.0): zipapp distribution (`cde_editor.pyz`, ~59 KB)
- **Centralized curation server** (v0.7.0): HMAC token auth, TLS, rate limiting
- **Incremental curation ledger** (v0.8.0): auto-resolve from prior decisions, gate/finalize
- **Zipf priority split** (v0.9.0): triage needs_review by word frequency

### Production Tooling — Complete

- **N-way branching strip** (v0.9.2): `strip_branching` — single-pass engine, all 7 variants
- **Strip configurator** (v0.9.1): `workflow configure CODE [-o FILE] [--nway]`
- **Step filtering** (v0.9.1): `--only-steps S1,S2,...` generic step filter
- **Workflow scaffold** (v0.6.0): auto-generate bash scripts with Windows→WSL conversion
- **Documentation**: 8 vignettes, 28 help files, 4 cheatsheets, MkDocs site

## Recent Versions

| Version | Date | Summary |
|---------|------|---------|
| 0.9.6 | 2026-03-09 | 7th variant (MTSTPF), allcde03 production run (104s), curator briefing |
| 0.9.5 | 2026-03-09 | Containment tree view in TSV editor (prefix+tinyId hierarchy) |
| 0.9.4 | 2026-03-07 | Deferred parent filter, anchor trim control, followup decision, doc audit |
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
- **Contains**: Everything through v0.9.6
- **Status**: 7-way branching strip, containment tree, deferred parent filter, allcde03 production run

### Active: main
- **Contains**: Everything through v0.9.1 + tinyid_count + context-aware examples
- **Status**: All pipeline phases complete, full curation infrastructure, production strip tooling

### Retired: phrase-curator (merged at v0.5.14)
- Merged into main on 2026-02-12

## What Remains

- **LLM-assisted classification** — implemented (`llm_classify` action), not yet integrated into pipeline
- **Position-specific field-aware stripping** — architecture ready in branching_stripper
- **Embedding evaluation** — run extract_embed on 7 branching-strip outputs
- **Full regression test** — legacy vs nway branching strip on allcde03 after curation
