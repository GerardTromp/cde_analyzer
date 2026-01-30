# CDE Analyzer — Focused Context: Phase 2 Phrase Curation Automation

> **Full context**: Read `CLAUDE_full.md` for complete project documentation.
> **Restore**: Copy `CLAUDE_full.md` back to `CLAUDE.md` when switching tasks.

## Project Summary

CDE Analyzer parses and analyzes Common Data Elements from the NLM CDE repository.
Layered monolithic architecture with plugin-style action system. Lazy loading.
Entry point: `cde_analyzer.py`. Data models: Pydantic in `CDE_Schema/`.

## Python Environment (WSL)

```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```

## Current Task: Automate Phase 2 Phrase Curation

**Goal**: Convert the manual phrase curation process (documented in
`scheuermann04/phase2_output/PROCESS_NOTES.md`) into automated `pattern_util`
subcommands and potentially LLM-assisted classification.

### What Was Done Manually (scheuermann04)

1. k-mer mining → subsumption → coalescing (already automated)
2. Field distribution analysis (function exists in `strip_discover/run.py`, needs CLI)
3. Instrument residual removal (keyword regex + manual review)
4. Minimum count filtering (>=6 in either field)
5. Short pattern removal (<=2 tokens)
6. Temporal pattern grouping (prefix-based, most labor-intensive)
7. Coverage analysis (tinyId set subtraction)
8. Field-aware sequential stripping (def pass, then desig pass)

### What Needs Implementation

**Priority 1 — `pattern_util` enhancements**:
- `--field-analysis` : Add field distribution columns (def_count, desig_count, field_profile) to a patterns TSV by scanning source JSON
- `--min-field-count N` : Filter patterns below threshold in both fields
- `--min-tokens N` : Filter patterns with fewer than N tokens
- `--exclude-patterns FILE` : Remove patterns matching entries in exclusion list

**Priority 2 — Temporal pattern automation**:
- `--group-temporal` : Detect temporal phrases via regex, group by prefix, merge tinyIds
- Temporal regex: `(in|over|during|for|within) the (past|last) \d+ (days?|weeks?|months?|years?)`

**Priority 3 — LLM-assisted classification**:
- Use `llm_classify` infrastructure to classify remaining patterns
- Categories: temporal_boilerplate, definition_template, lab_nomenclature, instrument_residual, content_bearing
- Could replace manual steps 3-6 entirely

**Priority 4 — Field-aware stripping workflow**:
- `--split-by-field` on pattern_util: split TSV into def-only and desig-only files
- Or: teach `strip_phrases` to accept a `field_profile` column and route patterns to correct fields

## Key Files for This Task

### Source Code (cde_analyzer/)
- `actions/pattern_util/cli.py` — CLI definitions for pattern_util
- `actions/pattern_util/run.py` — pattern_util orchestration
- `actions/strip_discover/run.py` — contains `compute_field_distribution()` (lines 26-94) and `_field_profile()` (lines 97-108) — **move or reuse these**
- `actions/strip_phrases/run.py` — stripping engine
- `logic/verbatim_discoverer.py` — `_extract_at_path()` helper
- `utils/pattern_tsv_utils.py` — shared TSV loading
- `actions/llm_classify/` — LLM classification infrastructure

### Data (scheuermann04/)
- `phase2_output/PROCESS_NOTES.md` — **detailed process documentation with automation recommendations**
- `phase2_output/manual_coalesce_fields.tsv` — 11 manually curated patterns (ground truth)
- `phase2_output/coalesced_min6_remaining.tsv` — 59 patterns needing classification
- `phase2_output/residual_instruments.tsv` — 13 instrument patterns to exclude
- `phase1_output/no_instruments_stripped_byhand.json` — input JSON (1148 CDEs)

### Workflow
- `workflows/phrase_pipeline.yaml` — existing phrase pipeline (may need updates)

## Architecture Reminders

- **Three-layer actions**: `cli.py` (args) → `run.py` (orchestration) → `logic/` (algorithms)
- **Lazy loading**: All imports inside functions
- **Pattern TSV format**: `pattern\ttinyIds\ttype\tsource_pattern` + optional field columns
- **Field paths**: `definitions.*.definition`, `designations.*.designation`
- **strip_phrases --fields**: Controls which fields get stripped (key for field-aware stripping)

## Existing `pattern_util` Capabilities

```bash
cde-analyzer pattern_util --coalesce-variants FILE -o OUT   # subsumption + prefix extraction
cde-analyzer pattern_util --merge-patterns FILE FILE -o OUT  # deduplicate/merge
cde-analyzer pattern_util --add-to-supplementary FILE        # import to config
```

New subcommands should follow the same pattern: `--flag FILE` with `-o OUT`.
