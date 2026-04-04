# Consolidated Checkpoint: v1.0.1+

**Date**: 2026-04-02
**Package Version**: 1.0.1 (since 2026-03-13)
**Branch**: main
**Scope**: Full project state — consolidates all prior checkpoints (v0.3.0–v1.0.0) plus post-v1.0.0 work through 2026-04-01

---

## Executive Summary

CDE Analyzer is a Python CLI tool that parses, analyzes, and normalizes text from
the NLM Common Data Elements repository. Three-phase pipeline: instrument pattern
mining/stripping, phrase mining/stripping, and branching strip with quality reporting.
Full curation workflow supports multi-curator review, incremental ledger-based
auto-resolution, and standalone/centralized editor distribution.

**Current state**: Production-stable at v1.0.1. Post-release work has focused on
abbreviation disambiguation (v1.1–v1.4 feature iterations), instrument leakage
reduction, and inter-rater agreement analysis. Package version not bumped beyond
1.0.1 — the v1.1–v1.4 labels in commit messages track abbreviation feature iterations.

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| **1.0.1** | 2026-03-13 | Decision rename (keep→strip, remove→skip), leakage scan, test suite (297) |
| **1.0.0** | 2026-03-12 | Production release: action refactoring, config-driven scaffold, reference ledger |
| **0.9.8** | 2026-03-11 | Field-aware splits, 7-way branching strip, group-scoped re-matching |
| **0.9.6** | 2026-03-09 | 7th variant (MTSTPF), allcde03 production run (104s), curator briefing |
| **0.9.5** | 2026-03-09 | Containment tree view in TSV editor (prefix+tinyId hierarchy) |
| **0.9.4** | 2026-03-07 | Deferred parent filter, anchor trim control, followup decision, doc audit |
| **0.9.2** | 2026-03-03 | N-way single-pass branching strip engine, tinyid_count column |
| **0.9.1** | 2026-03-03 | Production strip configurator, --only-steps |
| **0.9.0** | 2026-02-26 | Zipf priority split, editor UX, version sync |
| **0.8.1** | 2026-02-25 | Substitute decision type |
| **0.8.0** | 2026-02-24 | Incremental curation with ledger and gate |
| **0.7.0** | 2026-02-23 | Standalone editor zipapp, centralized server, synthetic QC |
| **0.6.0** | 2026-02-21 | Multi-curator, workflow scaffold, 7 vignettes |
| **0.5.17** | 2026-02-18 | Documentation restructuring, SVG diagrams, CLI shorts |
| **0.5.14** | 2026-02-12 | Split temporal/curated strip pipeline |

---

## Architecture (Stable)

### Three-Layer Action System
```
actions/{name}/cli.py  ->  actions/{name}/run.py  ->  logic/{module}.py
     (args)                  (orchestration)            (algorithms)
```

Lazy-loaded via `ACTION_REGISTRY` in `cde_analyzer.py`. Only the invoked action's
module is imported at runtime. Flat source layout (code at project root, not under
`cde_analyzer/` package directory).

### Pipeline

**Phase 1** (instrument_pipeline.yaml): mine -> discover -> coalesce -> validate ->
enrich -> gate -> [CURATE] -> finalize -> substitute -> strip -> sanity_check

**Phase 2** (phrase_pipeline.yaml): mine -> discover -> coalesce -> field_analysis ->
gate -> [CURATE] -> finalize -> substitute -> strip -> report

**Phase 3** (branching_strip_nway.yaml): expand_temporal -> strip_branching (7 variants) -> quality_report

### 7 Branching Strip Variants

| Code | Main | Sub | Phrase | Description |
|------|------|-----|--------|-------------|
| MTSFPF | T | F | F | Main instrument only |
| MFSTPF | F | T | F | Sub instrument only |
| MTSTPF | T | T | F | Main + sub instrument |
| MFSFPT | F | F | T | Phrases only |
| MTSFPT | T | F | T | Main instrument + phrases |
| MFSTPT | F | T | T | Sub instrument + phrases |
| MTSTPT | T | T | T | All three |

Field-aware splits (v0.9.8+): inst_full matches group prefix, inst_sub matches
separator + suffix. All 7 genuinely distinct.

---

## Key Infrastructure (Stable Since v1.0.0)

### Curation System
- **5 decision types**: strip, skip, modify, substitute, followup
- **Incremental ledger** (`logic/curation_ledger.py`): auto-resolve from prior decisions
- **Gate/finalize**: `--curation-gate` classifies, `--finalize-curation` merges + records
- **TSV editor** (`actions/curation/tsv_editor.html`): browser-based with containment tree
- **Multi-curator**: init -> distribute -> curate -> merge -> resolve -> finalize
- **Centralized server**: HMAC token auth, TLS, rate limiting
- **Zipf split**: triage needs_review by word frequency
- **Reference ledger**: `data/reference_ledger/` (458 instrument + 4,023 phrase decisions)

### Workflow Engine
- **YAML workflows**: variable substitution, checkpoints, skip_if_file
- **Config-driven scaffold**: `workflow scaffold --from-config`
- **Strip configurator**: `workflow configure CODE --nway`
- **Step filtering**: `--only-steps`, `--from-step`

### Production Data (allcde03)
- 22,743 CDEs x 7 variants (N-way single-pass, 104s)
- Pattern inventory: 383 inst_full + 252 inst_sub + 273 phrases + 7 substitutes + 39 verbatim + 2,100 temporal
- Quality: 84.2% fields at 90-100% retention (MTSFPT), 0 artifacts

---

## Post-v1.0.0 Work (2026-03-13 through 2026-04-01)

### v1.0.1 Changes (2026-03-13)
- Decision terminology renamed: keep->strip, remove->skip (backwards-compat reads old values)
- Keyboard shortcuts: S=strip, K=skip, U=substitute, M=modify, F=followup
- Instrument leakage scan added to `strip_report`
- New instrument family patterns
- Synthetic QC data generator

### Codebase Quality (2026-03-17)
- **Test coverage**: 128 -> 297 tests (+132%), test-to-code ratio 1:30 -> 1:15
- New test files: `test_phrase_miner.py` (41), `test_flexible_pattern_matcher.py` (68), `test_workflow_engine.py` (60)
- **Shared utilities**: `scripts/synthetic_common.py` (injection engine)
- **`parse_tinyid_set()`**: Consolidates 27 duplicate tinyId parsing patterns
- **.gitignore**: Fixed overly broad `test*` pattern

### Inter-Rater Agreement Analysis (2026-03-17 -- 2026-03-24)
- **4-curator merge**: GT, MD, MLEACH, BP2 -- 1,331 patterns, Krippendorff's alpha = 0.039
- **Collapsed agreement** (modify/substitute -> strip): 405 unanimous (30.7%), 510 majority
- **Cluster consequence study**: GT achieves 86% cluster stability (best); MD matches baseline at 57%
- **Key finding**: "subject/participant" framing carries structural signal useful for clustering

### Verbatim Strip Pattern Updates (2026-03-17 -- 2026-03-24)
- [PROMIS]/[PROMIS.PEDS] bracketed tags (41 CDEs)
- PROMIS regex for instrument prefix with form/version/item code (31 CDEs)
- Repository typos: "Information Measurement" transposition, "Patient- Reported" hyphen-space
- 55 bracketed instrument tags added, 27 bare-tag scoped patterns
- NIHSS/PedNIHSS bare abbreviations, ^PROMIS start-of-field regex
- PROMIS LOINC designation regex

### Abbreviation Disambiguation (v1.1 -- v1.4 feature iterations)

**v1.1.0** (commit c757a19): Core abbreviation dictionary
- `logic/abbreviation_dictionary.py`, `actions/abbreviation/`, 22 tests
- Three-tier resolution: internal expansion (Tier 1), external lookup (Tier 2), adjudication dictionary (Tier 3)

**v1.2.0**: Seeding from curated instruments
- 513 entries, 188 instruments, 197 generated patterns (vs 129 manual)

**v1.3.0/v1.3.1** (commits 71d9709, d9d9b12): External lookup + integration
- 226 instruments, 244 generated patterns, tentative decision UX
- Decision column in dictionary, tentative auto-fill, zero-tinyId filtering

**v1.4.0** (commit 4d52f86): Acronym alignment + skip management
- Acronym-alignment heuristic: maps abbreviation letters to token initials (not mid-word)
- Permanent skip list: `config/permanent_skip_abbreviations.yaml` (genes, anatomy, orgs, coding systems)
- K-fold re-evaluation: skip decisions re-flagged when tinyId count grows >= 3x
- All-caps field detection: skip bare-caps discovery in "shouting" fields

**Post-v1.4.0 fixes**:
- Catastrophic backtracking fix in _PAREN_RE (commit 668f7c3)
- Workflow YAML fix: remove YAML from additional_patterns TSV-only arg (commit dbfdd5a)

### Instrument Leakage Follow-up (2026-04-01)

Run on MTSTPT variant after v1.4.0 abbreviation work:

| Metric | Round 1 | Current | Delta |
|--------|---------|---------|-------|
| Gross hits | 2,380 | 335 | **-86%** |
| Net hits (excl PROMIS stems) | 2,380 | 111 | **-95%** |

Remaining leakage categories:
- **PROMIS stems** ("I felt" 180, "I had trouble" 40): Phase 2 phrase curation scope, not instrument leaks
- **Bare abbreviations** (PROMIS 35, NIHSS 35, PHQ 15-17, DSQ 1-23): need tinyId-scoped stripping
- **Sub-instrument names** (SWAL-QOL 50, PDQUALIF 33, etc.): only in MF variants, stripped in MT variants

### phrase_curation3 / allcde04 (Active)
- 5-way curator comparison (GT, MD, ML, consensus3, consensus3m) complete
- 6 embed CSVs ready for clustering evaluation
- Residual fixes applied (PhenX, ASSIST, eyeGENE), pending rerun
- Location: `d:/GT/Professional/NLM_CDE/work_202602/phrase_curation3/`

### Embedding Feature Selection (Sibling Repo)
- `clone_git/embedding_feature_selection/`: boilerplate-encoding vs signal-carrying dimensions
- Finding: minilm (384 dims) provides best clustering anecdotally

---

## What Remains

1. **Scoped stripping** (deferred to future version) -- tinyId-scoped verbatim patterns for bare abbreviations
2. **LLM pipeline integration** -- `llm_classify` action exists but not integrated into workflow
3. **Parallel abbreviation discovery** (v1.5.0 design) -- embarrassingly parallel, chunk across workers
4. **phrase_curation3 rerun** -- with updated config + ledger, then clustering evaluation
5. **Position-specific field-aware stripping** -- architecture ready in branching_stripper
6. **tinyId parsing migration** -- 27 call sites -> `parse_tinyid_set()` (gradual)
7. **Complexity reduction** -- top 5 files, ~40-50 helper extractions possible (gradual)

---

## Prior Checkpoints (Archived)

- `archive/checkpoint-2026-03-12-v100-consolidated.md` -- v0.3.0-v1.0.0
- `archive/202603/checkpoint-2026-03-10-v096-consolidated.md` -- v0.3.0-v0.9.6
- `archive/202602/` -- February 2026 incremental checkpoints
- `archive/202601/` -- January 2026 incremental checkpoints
