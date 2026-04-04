# Consolidated Checkpoint: v1.5.1

**Date**: 2026-04-04
**Package Version**: 1.5.1
**Branch**: main
**Git Commit**: 9aa2eff
**Scope**: Full project state — consolidates all prior checkpoints (v0.3.0–v1.5.0) plus v1.5.1 QC fixes
**Supersedes**: checkpoint-2026-04-02-v101-consolidated.md, checkpoint-2026-04-02-scoped-stripping.md, checkpoint-2026-04-03-v150-interim.md

---

## Executive Summary

CDE Analyzer is a Python CLI tool that parses, analyzes, and normalizes text from the NLM Common Data Elements repository. Three-phase pipeline: instrument pattern mining/stripping, phrase mining/stripping, and 7-way branching strip with quality reporting. Full curation workflow supports multi-curator review, incremental ledger-based auto-resolution, and standalone/centralized editor distribution.

**Current state**: Production at v1.5.1. Pipeline fully converged. 5-curator production output generated (GT, MD, ML, consensus3, consensus3m × 7 variants = 35 stripped JSONs + 70 embed files). CDE construction recommendations report with 19 findings delivered. Next step: embedding clustering evaluation and production curator selection.

---

## Architecture

- **Style**: Layered monolithic with plugin-style lazy-loaded action system
- **Entry point**: `cde_analyzer.py` → `ACTION_REGISTRY` → lazy dispatch
- **Three-layer pattern**: `cli.py` (args) → `run.py` (orchestration) → `logic/` (algorithms)
- **Data models**: Pydantic in `CDE_Schema/`
- **Python**: 3.13 via WSL Ubuntu-22.04
- **Tests**: 377 tests passing

## Key Capabilities

### Pipeline (3 phases)
1. **Instrument Pipeline** (`instrument_pipeline.yaml`): mine → discover → coalesce → validate → enrich → gate → [CURATOR] → finalize → apply_substitutions → strip → sanity_check
2. **Phrase Pipeline** (`phrase_pipeline.yaml`): mine → discover → coalesce → field_analysis → gate → [CURATOR] → finalize → apply_substitutions → strip → discovery_report
3. **Branching Strip** (`branching_strip_nway.yaml`): expand_temporal → strip_branching (single-pass, 7 variants) → quality_report

### Stripping Engine
- **7 variant codes**: MTSFPF, MFSTPF, MTSTPF, MFSFPT, MTSFPT, MFSTPT, MTSTPT
- **Field-aware splits** (v0.9.8): inst_full and inst_sub operate on different text spans
- **199 verbatim patterns** (176 scoped, 23 universal) from `config/verbatim_strip_patterns.yaml`
- **Auto-propagation**: bracketed `[TAG]` → bare `TAG` with same tinyId scope
- **Post-strip cleanup**: remnant_detector handles orphan articles, floating punctuation, `?` separators
- **Pattern inventory**: 451 instrument + 259 GT phrase + 2,100 temporal + 199 verbatim + 30 boilerplate substitutes

### Curation Infrastructure
- **5 decision types**: strip, skip, modify, substitute, followup
- **Incremental ledger**: auto-resolve from prior decisions, gate/finalize workflow
- **Multi-curator**: init/merge with inter-rater stats (Cohen's/Fleiss' kappa, Krippendorff's alpha)
- **Standalone editor**: zipapp (`cde_editor.pyz`, ~59 KB), centralized server with HMAC auth
- **Containment tree**: prefix+tinyId hierarchy in editor, DFS sort, propagation
- **Zipf priority split**: triage needs_review by word frequency

### LLM Integration
- **Boilerplate substitution**: 30 verbose definitions → LLM summaries (88% reduction)
- **YAML prompt registry**: `config/llm_prompts.yaml` — add new LLM tasks without Python code
- **Providers**: Claude, OpenAI, Gemini (async, rate-limited)

---

## Version History (condensed)

| Version | Date | Key Changes |
|---------|------|-------------|
| **1.5.1** | 2026-04-03 | REGEX prefix fix (PROMIS 35→2), `?` cleanup (201→0), 7 new verbatim patterns (192→199), CDE recommendations (19 items) |
| **1.5.0** | 2026-04-02 | tinyId-scoped verbatim stripping, boilerplate substitution (30 defs, 88%), YAML LLM prompts, abbreviation v1.1–v1.4 |
| **1.0.1** | 2026-03-13 | Decision terminology rename (keep→strip), leakage scan, 297 tests |
| **1.0.0** | 2026-03-12 | Production release: action refactoring, config scaffold, reference ledger |
| **0.9.8** | 2026-03-11 | Field-aware splits, 7-way branching strip, group-scoped re-matching |
| **0.9.2** | 2026-03-03 | N-way single-pass branching strip engine |
| **0.8.0** | 2026-02-24 | Incremental curation ledger and gate |
| **0.7.0** | 2026-02-23 | Standalone editor zipapp, centralized server |
| **0.6.0** | 2026-02-21 | Multi-curator workflow, 7 vignettes |

Pre-v0.6.0 history archived in `.claude/checkpoints/archive/`.

---

## Production Run State (phrase_curation3)

### Input
- **CDE JSON**: `cde_all_03_20260105_no-undrscr_nohtml.json` — 22,743 CDEs

### Pipeline Output (v1.5.1, 2026-04-04)
- **Stripped JSON**: 5 curators × 7 variants = 35 files (5.5 GB)
  - GT: `branching_output/stripped_{VARIANT}.json`
  - Others: `branching_output/{curator}/stripped_{VARIANT}.json`
- **Embed files**: 5 curators × 7 variants × 2 formats = 70 files (220 MB)
  - `embed_text/embed_{VARIANT}.{csv,tsv}` (GT)
  - `embed_text/embed_{VARIANT}_{curator}.{csv,tsv}` (others)

### Stripping Quality (MTSTPT, most aggressive variant)

| Metric | R1 | R4 | R6/R7 | R1→R7 |
|--------|---:|---:|------:|-------|
| Instrument leakage | 2,380 | 335 | 300 | **-87%** |
| Bracketed instrument tags | 6,505 | 37 | 0 | **-100%** |
| `?` separator remnants | 201 | 201 | 0 | **-100%** |
| Likert scale in defs | 45 | 45 | 0 | **-100%** |

Remaining 300 leakage: 225 item stems (expected questionnaire text) + 75 abbreviation fragments (diminishing returns).

### Curation Decisions
- **Instruments**: 458 patterns (383 full + 252 sub after field-aware split)
- **Phrases (GT)**: 259 curated (171 strip, 3,743 skip, 102 modify, 7 substitute)
- **5 curators compared**: GT (259), consensus3m (396), ML (496), consensus3 (484), MD (1,015)

### Inter-Rater Agreement
- Krippendorff's α = 0.006 (4 curators, 1,331 patterns)
- GT achieves 86% cluster stability (best); MD at 57% (over-stripping = no stripping)

---

## CDE Construction Recommendations (19 items)

Delivered in `reports/cde_construction_recommendations.md`. Key findings:

| # | Category | Impact |
|---|----------|--------|
| 1 | Instrument contamination | 500+ stripping patterns needed |
| 2 | Boilerplate definitions | 88% of verbose text is non-definitional |
| 2b | Measurement method in defs | 45 CDEs (Likert scale) |
| 3 | Empty/missing fields | 27% of CDEs have no definition |
| 4 | Loose designation data model | 58% of CDEs untyped |
| 5.1-5.5 | Modularity/duplication | 798 scope-variant near-dupes (3.5%) |
| 6 | Poor phrasing | 2,076 defs under 50 chars |
| 7-8 | HTML / duplicate defs | 70 + 440 CDEs |
| 9.1 | Unicode encoding failures | 201 CDEs with corrupted separators |
| 9.2 | Spelling/typos | 29 errors + 392 spacing issues |
| 10 | Case inconsistency | Doubles pattern count |
| 11 | Inline abbreviation clutter | 2,386 introductions |
| 12 | Undefined abbreviations | 162 abbrevs / 899 CDEs never defined |
| 13 | References in definitions | 37 CDEs with URLs/PMIDs |
| 14 | Noise phrases / bundling | 100+ CDEs are enumerated combinations |

---

## Data Files (phrase_curation3/reports/)

| File | Content |
|------|---------|
| `cde_construction_recommendations.md` | 19-item recommendations with empirical counts |
| `detailed_strip_report.md` | Round-by-round QC with R1/R4/R6 columns |
| `summary_strip_report.md` | Executive summary |
| `strip_qc_reveal.html` | Reveal.js slide deck (12 slides) |
| `scope_variant_groups.tsv` | 288 near-duplicate groups (798 CDEs) |
| `undefined_abbreviations_in_names.tsv` | 162 abbreviations (899 CDEs) |
| `verbose_definition_candidates.tsv` | 210 definitions >300 chars (LLM candidates) |
| `remnant_scan/` | Per-curator instrument fragment TSVs |

---

## What Remains

1. **Embedding clustering evaluation** — generate embeddings from R7 embed CSVs, compare 5 curators × 7 variants
2. **Choose production curator** — GT vs consensus3m vs ML vs MD based on cluster quality
3. **Production run + reference ledger update** — winning curator → update `data/reference_ledger/`
4. **LLM substitution pass 2** — 210 verbose definition candidates identified
5. **API key setup** — for automated LLM-driven boilerplate substitution on new corpora

### Lower Priority
- Position-specific field-aware stripping (architecture ready)
- tinyId parsing migration (27 call sites → `parse_tinyid_set()`)
- Complexity reduction (top 5 files, ~40-50 helper extractions)

---

## Recovery Instructions

1. Read this checkpoint for full state
2. Read `CLAUDE.md` for current version summary and action reference
3. Read `.claude/context/08-progress.md` for detailed version history
4. Production data is in `phrase_curation3/` (work directory, not in git)
5. Pipeline script: `phrase_curation3/scripts/run_pipeline.sh`
6. Curator comparison: `phrase_curation3/scripts/run_all_curators_phase3.sh`
7. Embed generation: `phrase_curation3/scripts/generate_embed_files.sh`
