# Progress and Current State

## Current Branch: main

**Focus**: Automated instrument/phrase stripping pipeline for CDE text normalization

**Note**: phrase-curator branch merged into main at v0.5.14 (2026-02-12)

**Version**: 0.6.0

## Current State (v0.6.0, 2026-02-21)

### v0.6.0: Multi-Curator Curation + Workflow Scaffold + Vignettes

#### Multi-Curator Curation Workflow
- `--init-curation` / `--merge-curation` in pattern_util for multi-curator workflows
- `logic/inter_rater.py` — Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, pairwise agreement
- `actions/pattern_util/curation_diff.html` — browser-based visual diff viewer
- Rare word detection with wordfreq Zipf scoring and whitelist

#### Workflow Scaffold
- `workflow scaffold PROJECT -i JSON -d DIR` generates project-specific pipeline bash scripts
- Auto Windows→WSL path conversion, phase subset support, iterative harvesting loop
- Generated script: PARAMETERS → DERIVED PATHS → HELPERS → phase functions → DISPATCH

#### Documentation: Vignettes (5 new pages)
- `docs/vignettes/index.md` — landing page with decision table
- `docs/vignettes/quickstart.md` — full pipeline end-to-end walkthrough
- `docs/vignettes/instrument-detection.md` — Phase 1 deep dive
- `docs/vignettes/pipeline-orchestration.md` — workflow engine power user guide
- `docs/vignettes/parameter-tuning.md` — small vs large dataset comparison
- `mkdocs.yml` nav: "Guides" → "Guides & Vignettes"

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
| 0.6.0 | 2026-02-21 | Multi-curator curation, workflow scaffold, vignettes |
| 0.5.17 | 2026-02-15 | Documentation restructuring, CLI short options |
| 0.5.14 | 2026-02-12 | Split temporal/curated strip, bare/article-only variants, 5 new seeds |
| 0.5.13 | 2026-02-11 | Universal temporal stripping, dedup pre-pass, 3 critical bug fixes |
| 0.5.12 | 2026-02-11 | Empirical subsumption validation, coalescer punctuation fix |
| 0.5.11 | 2026-02-10 | Coalescer NP-continuity fix, iterative stripping pipeline |
| 0.5.6 | 2026-02-10 | Interactive TSV editor for pattern curation |
| 0.5.5 | 2026-02-10 | strip_report action for quality reports |

## Branches

### Active: main (CURRENT)
- **Contains**: All v0.5.x features merged from phrase-curator + v0.6.0 features
- **Status**: Phase 3 complete, multi-curator + scaffold + vignettes added

### Retired: phrase-curator (merged at v0.5.14)
- Merged into main on 2026-02-12
- Remote branch preserved for history

## What Remains

- **Priority 3 — LLM-assisted classification** (not started)
- **Priority 4 — Field-aware stripping** (not started)
- **Embedding evaluation** — run extract_embed on 5 branching-strip outputs
