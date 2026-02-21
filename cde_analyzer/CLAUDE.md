# CDE Analyzer — Context (v0.6.0)

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
strip_inst_full/sub → expand_temporal → strip_temporal_{phrase,both_full,both_sub} (case-insensitive) → strip_{phrase_only,both_full,both_sub} (case-sensitive) → quality_report

## Current State (v0.6.0)

### v0.6.0: Multi-Curator Curation + Workflow Scaffold + Vignettes

#### Multi-Curator Curation Workflow
- **`--init-curation FILE`**: Initialize multi-curator curation from enriched TSV (copies to `FILE.curator_N.tsv`)
- **`--merge-curation FILE`**: Merge multiple curator TSVs with inter-rater statistics
- **Inter-rater statistics**: `logic/inter_rater.py` — Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, pairwise agreement
- **Curation diff HTML**: `actions/pattern_util/curation_diff.html` — browser-based visual diff viewer
- **Workflow**: init-curation → distribute → curators annotate → merge-curation → review diff → finalize

#### Workflow Scaffold Command
- **`workflow scaffold PROJECT -i JSON -d DIR`**: Generates project-specific pipeline orchestration bash scripts
- **Auto Windows→WSL path conversion**: `D:\foo\bar` → `/mnt/d/foo/bar`
- **Phase subset support**: `--phases 2,3` generates only selected phases with TODO placeholders
- **Iterative harvesting**: `--with-iterate` includes residual harvesting loop
- **Generated script structure**: PARAMETERS → DERIVED PATHS → HELPERS → phase functions → DISPATCH

#### Documentation: Vignettes
- **`docs/vignettes/index.md`**: Landing page with decision table
- **`docs/vignettes/quickstart.md`**: Full pipeline end-to-end walkthrough (scaffold → Phase 1-3)
- **`docs/vignettes/instrument-detection.md`**: Phase 1 deep dive — curation decisions, iterative harvesting, supplementary patterns
- **`docs/vignettes/pipeline-orchestration.md`**: Workflow engine power user guide — variable chain, config files, scaffold, checkpoints, recipes
- **`docs/vignettes/parameter-tuning.md`**: Small vs large dataset comparison (scheuermann08 vs allcde01), `min_parent_tinyids` deep dive
- **`mkdocs.yml`**: "Guides" → "Guides & Vignettes" with 6 entries

### v0.5.15–v0.5.17: Documentation Restructuring
- **Nav restructure**: `mkdocs.yml` reorganized — Workflows elevated, Command Reference section, LLM section, Appendix
- **SVG diagrams**: `detailed-workflow-architecture.svg`, `llm-workflow.svg` replacing ASCII art
- **CLI short options**: Standardized across 10 cli.py files

### Implemented — Phrase Curation Automation
- **`--field-analysis`**: Adds def_count, desig_count, field_profile columns + example CDE columns
- **`--min-field-count N`**, **`--min-tokens N`**, **`--exclude-patterns FILE`**: Filtering
- **`--validate-subsumption`**: Empirical post-coalescing validation (parallelized)
- **`--expand-temporal-seeds`**: Universal temporal stripping from 25 seed patterns (~2100 variants)
- **`--merge-patterns`**: Combine/deduplicate pattern TSV files
- **`--dedup`** in phrase_miner: Identifies whole-text duplicates exceeding k_max
- **Split temporal/curated stripping**: Temporal patterns stripped case-insensitively before case-sensitive curated phrase stripping

### What Remains
- **Priority 3 — LLM-assisted classification** (not started)
- **Priority 4 — Field-aware stripping** (not started)

## Key Files

### Source Code (cde_analyzer/)
- `actions/pattern_util/cli.py` — CLI definitions for pattern_util (incl. init-curation, merge-curation)
- `actions/pattern_util/run.py` — pattern_util orchestration (coalesce, merge, field analysis, validate subsumption, expand temporal seeds, init-curation, merge-curation)
- `actions/workflow/cli.py` — CLI definitions for workflow (incl. scaffold)
- `actions/workflow/run.py` — workflow orchestration (run, resume, scaffold, list, copy, status)
- `logic/inter_rater.py` — inter-rater reliability statistics (Cohen's/Fleiss' kappa, Krippendorff's alpha)
- `actions/phrase_miner/run.py` — phrase miner runner + `write_dedup_curation_tsv()`
- `logic/phrase_miner.py` — core mining: `dedup_field_texts()`, `mine_phrases()`, k-mer loop, masking
- `actions/strip_discover/run.py` — `compute_field_distribution()`, `build_field_text_index()`
- `actions/strip_phrases/run.py` — stripping engine
- `utils/instrument_extractor.py` — instrument name extraction
- `utils/flexible_pattern_matcher.py` — coalescer (Phase 1a prefix-kept, Phase 1b NP-continuity)
- `config/temporal_seed_patterns.yaml` — 25 temporal seed patterns (~2100 expanded variants)
- `utils/pattern_variant_generator.py` — temporal/case/number/plural variant generators

### Workflows
- `workflows/instrument_pipeline.yaml` — Phase 1
- `workflows/phrase_pipeline.yaml` — Phase 2
- `workflows/branching_strip.yaml` — Phase 3 (5-way branch)

### Documentation
- `docs/vignettes/` — 6 vignettes (index, quickstart, instrument-detection, pipeline-orchestration, parameter-tuning, phrase-stripping)
- `docs/help/` — 22 per-command reference pages
- `docs/workflow-architecture.md` — pipeline diagrams + design rationale

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
cde-analyzer pattern_util --init-curation FILE -o DIR             # initialize multi-curator curation
cde-analyzer pattern_util --merge-curation FILE -o OUT            # merge curator annotations + stats
```

## `workflow` Capabilities

```bash
cde-analyzer workflow run YAML [--set K=V] [--from-step S] [--dry-run]  # execute pipeline
cde-analyzer workflow resume --state-file FILE                          # resume after checkpoint
cde-analyzer workflow status [--state-file FILE] [-v]                   # check pipeline state
cde-analyzer workflow list                                              # list built-in workflows
cde-analyzer workflow copy NAME [--as FILE]                             # copy template to project
cde-analyzer workflow scaffold PROJECT -i JSON -d DIR [--phases 1,2,3] [--with-iterate]  # generate orchestration script
```
