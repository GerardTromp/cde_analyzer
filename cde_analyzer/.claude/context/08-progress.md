# Progress and Current State

## Current Branch: phrase-curator

**Focus**: Automated instrument/phrase stripping pipeline for CDE text normalization

**Tracking**: origin/phrase-curator

**Version**: 0.5.14

## Current State (v0.5.14, 2026-02-12)

### Phase 3 Branching Strip — Complete
- 5-way branching strip pipeline producing distinct normalized outputs
- Split temporal/curated stripping: temporal patterns case-insensitive, curated case-sensitive
- 25 temporal seed patterns → ~2100 expanded variants (0 remnants in def/desig fields)
- 10-step pipeline: 2 instrument + 1 expand + 3 temporal + 3 curated + 1 quality report
- allcde01 results: inst_full: -515K, inst_sub: -415K, phrase: -105K, both_full: -553K, both_sub: -449K
- 6 non-temporal remnants in fully-stripped outputs (trailing articles)
- Runtime: ~4.5 minutes (down from >15 hours before v0.5.13 fixes)

### Phase 2 Phrase Pipeline — Complete
- 86 curated phrases, 6 removed
- Whole-text dedup: 4 phrases >k_max (separate curation template)
- 13,640 k-mer phrases mined

### Phase 1 Instrument Pipeline — Complete
- 458 validated instrument patterns (from 1342 raw → 591 coalesced → 458 validated)

## Recent Versions

| Version | Date | Summary |
|---------|------|---------|
| 0.5.14 | 2026-02-12 | Split temporal/curated strip, bare/article-only variants, 5 new seeds |
| 0.5.13 | 2026-02-11 | Universal temporal stripping, dedup pre-pass, 3 critical bug fixes |
| 0.5.12 | 2026-02-11 | Empirical subsumption validation, coalescer punctuation fix |
| 0.5.11 | 2026-02-10 | Coalescer NP-continuity fix, iterative stripping pipeline |
| 0.5.6 | 2026-02-10 | Interactive TSV editor for pattern curation |
| 0.5.5 | 2026-02-10 | strip_report action for quality reports |

## Branches

### Active: phrase-curator (CURRENT)
- **Purpose**: Full instrument + phrase stripping pipeline
- **Contains**: All v0.5.x features (instrument pipeline, phrase pipeline, branching strip, temporal stripping, dedup, LLM classify)
- **Status**: Phase 3 complete, ready for embedding/clustering evaluation

### Main: main (stable baseline)
- **Last sync**: Commit 328b48e
- **Tracking**: origin/main

## What Remains

- **Priority 3 — LLM-assisted classification** (not started)
- **Priority 4 — Field-aware stripping** (not started)
- **Embedding evaluation** — run extract_embed on 5 branching-strip outputs
- **Merge to main** — after full pipeline validation
