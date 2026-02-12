# CDE Analyzer — Focused Context: Phase 2 Phrase Pipeline (v0.5.13)

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

## Pipeline Overview

### Phase 1: Instrument Pipeline (`instrument_pipeline.yaml`)
mine_instruments → discover_verbatim → coalesce → validate_subsumption → enrich_fields → [CURATOR] → generate_strip_patterns → strip_instruments

### Phase 2: Phrase Pipeline (`phrase_pipeline.yaml`)
mine_phrases → discover_verbatim → coalesce → field_analysis → [CURATOR] → strip_phrases → discovery_report

### Phase 3: Branching Strip (`branching_strip.yaml`)
strip_inst_full/sub → expand_temporal → merge_temporal_phrases → strip_phrase_only/both_full/both_sub → quality_report

## Current State (v0.5.13)

### Implemented — Phrase Curation Automation
- **`--field-analysis`**: Adds def_count, desig_count, field_profile columns + example CDE columns
- **`--min-field-count N`**, **`--min-tokens N`**, **`--exclude-patterns FILE`**: Filtering
- **`--validate-subsumption`**: Empirical post-coalescing validation (parallelized)
- **`--expand-temporal-seeds`**: Universal temporal stripping from seed patterns
- **`--merge-patterns`**: Combine temporal + curated phrase patterns
- **`--dedup`** in phrase_miner: Identifies whole-text duplicates exceeding k_max

### Dedup Design (refined)
- Stage 0a: Hash field texts, group identical strings shared by N+ CDEs
- Stage 0b: Only emit phrases with **tokens > k_max** (unreachable by k-mer mining)
- **No masking** — sub-phrases within dedup'd texts remain visible to k-mer mining
- Short duplicates found naturally by k-mer mining
- Output: separate `dedup_phrases.tsv` curation template (not in regular phrase output)
- allcde01: 1003 shared texts → 4 dedup phrases (>25 tokens), 13640 k-mer phrases

### What Remains
- **Priority 3 — LLM-assisted classification** (not started):
  - Use `llm_classify` infrastructure to classify remaining patterns
  - Categories: temporal_boilerplate, definition_template, lab_nomenclature, instrument_residual, content_bearing
- **Priority 4 — Field-aware stripping** (not started):
  - `--split-by-field` or field_profile-aware strip_phrases

## Key Files

### Source Code (cde_analyzer/)
- `actions/pattern_util/cli.py` — CLI definitions for pattern_util
- `actions/pattern_util/run.py` — pattern_util orchestration (coalesce, merge, field analysis, validate subsumption, expand temporal seeds)
- `actions/phrase_miner/run.py` — phrase miner runner + `write_dedup_curation_tsv()`
- `logic/phrase_miner.py` — core mining: `dedup_field_texts()`, `mine_phrases()`, k-mer loop, masking
- `actions/strip_discover/run.py` — `compute_field_distribution()`, `build_field_text_index()`
- `actions/strip_phrases/run.py` — stripping engine
- `utils/instrument_extractor.py` — instrument name extraction
- `utils/flexible_pattern_matcher.py` — coalescer (Phase 1a prefix-kept, Phase 1b NP-continuity)
- `config/temporal_seed_patterns.yaml` — 20 temporal seed patterns

### Workflows
- `workflows/instrument_pipeline.yaml` — Phase 1
- `workflows/phrase_pipeline.yaml` — Phase 2
- `workflows/branching_strip.yaml` — Phase 3 (5-way branch)

### Data (allcde01/)
- `phase1_output/inst_stripped.json` — instrument-stripped JSON (22,743 CDEs)
- `phase2_output/` — phrase pipeline output (in progress)

## Architecture Reminders

- **Three-layer actions**: `cli.py` (args) → `run.py` (orchestration) → `logic/` (algorithms)
- **Lazy loading**: All imports inside functions
- **Pattern TSV format**: `pattern\ttinyIds\ttype\tsource_pattern` + optional field columns
- **Field paths**: `definitions.*.definition`, `designations.*.designation`
- **K-mer mining**: Descending (k_max → k_min), masks detected phrases after each k
- **Dedup**: Identification only (no masking), separate curation template, >k_max filter

## `pattern_util` Capabilities

```bash
cde-analyzer pattern_util --coalesce-variants FILE -o OUT         # subsumption + prefix trie
cde-analyzer pattern_util --merge-patterns FILE FILE -o OUT       # deduplicate/merge TSVs
cde-analyzer pattern_util --field-analysis FILE --input JSON -o OUT  # add field counts
cde-analyzer pattern_util --validate-subsumption FILE --input JSON -o OUT  # empirical validation
cde-analyzer pattern_util --expand-temporal-seeds -o OUT          # temporal seed expansion
cde-analyzer pattern_util --harvest-to-supplementary FILE         # ingest to local supplementary
cde-analyzer pattern_util --promote-supplementary                 # promote to global config
cde-analyzer pattern_util --edit FILE                             # browser-based TSV editor
```
