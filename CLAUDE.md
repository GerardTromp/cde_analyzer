# CDE Analyzer — Context (v0.9.4)

> **Full context**: Read `CLAUDE_full.md` for complete project documentation.
> **Restore**: Copy `CLAUDE_full.md` back to `CLAUDE.md` when switching tasks.

## Version String Locations — UPDATE ALL ON VERSION BUMP

When changing the version, **all three files must be updated together**:

| # | File | Variable | Example |
|---|------|----------|---------|
| 1 | `cde_analyzer/__version__.py` | `__version__` | `__version__ = "X.Y.Z"` |
| 2 | `pyproject.toml` | `version` | `version = "X.Y.Z"` |
| 3 | `tools/editor_standalone/__main__.py` | `_FALLBACK_VERSION` | `_FALLBACK_VERSION = "X.Y.Z"` |

Also update the version in documentary headings: `CLAUDE.md`, `CLAUDE_full.md`, and `.claude/context/` files.

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
mine_instruments → discover_abbreviations → discover_verbatim → coalesce → validate_subsumption → enrich_fields → curation_gate → [CURATOR] → finalize_curation → apply_substitutions → strip_instruments → sanity_check

### Phase 2: Phrase Pipeline (`phrase_pipeline.yaml`)
mine_phrases → discover_verbatim → coalesce → field_analysis → curation_gate → [CURATOR] → finalize_curation → apply_substitutions → strip_phrases → discovery_report

### Phase 3: Branching Strip
- **Legacy** (`branching_strip.yaml`): strip_inst_full/sub → expand_temporal → strip_temporal (case-insensitive) → strip_phrases (case-sensitive) → quality_report (13 steps)
- **N-way** (`branching_strip_nway.yaml`): expand_temporal → strip_branching (single-pass, all variants) → quality_report (3 steps)

## Current State (v0.9.4)

### v0.9.4: Deferred Parent Filter + Anchor Trim Control + Followup Decision

#### Phrase Pipeline Correctness
- **Deferred parent filter** (`--defer-parent-filter`): Weak-parent patterns participate in prefix extraction before filtering. Rescued by prefix groups survive. Phrase pipeline default: true
- **No-trim-anchors** (`--no-trim-anchors`): Disables Phase 0 anchor trimming. Critical for phrases. Phrase pipeline default: true
- **Phase 1b protection**: Skip reverse subsumption for weak-parent patterns in deferred mode
- **Divergence warning**: Fires when parent filter removes patterns with high actual/parent ratio (>5x)

#### Phrase Miner Enhancements
- **Prefix consolidation**: Post-loop token-ID prefix trie recovers fragmented prefixes masked across multiple k-levels
- **Ledger pre-masking** (`--ledger-dir`): Prior "remove" decisions pre-masked during mining

#### Verbatim Strip Patterns
- Executive Order disclaimer extended with trailing "repository."
- New patterns: `[AHRQ]` (62), `[AQ]` (50), `[HL7v3.0]` (1), AQ Adol/Adolescent (98), Ord AQ (50), REGEX: trailing AQ (50)

#### TSV Editor: Followup Decision
- **5th decision type**: `followup` — flags patterns for later evaluation (purple badge, `F` shortcut)
- **Counts as undecided**: Does not contribute to tinyId coverage tracker
- **Ctrl+U**: Deselect all rows
- **Status bar**: Shows `tinyIds: decided/total` coverage

#### Documentation Audit
- 11 help files updated, 2 new (`strip_html.md`, `tsv_concat.md`)
- Cheatsheet renamed QUICKSTART → CHEATSHEET with curator workflow guide

### v0.9.2: N-way Single-Pass Branching Strip

#### N-way Branching Strip Engine (`strip_branching`)
- **Single-pass**: Loads CDE JSON once, produces all 6 variants simultaneously
- **Shared intermediates**: `inst_full` result reused across MTSFPF, MTSFPT, MTSTPT
- **4 strip stages**: `inst_full`, `inst_sub`, `temporal`, `phrase` — each with appropriate settings
- **TinyId-indexed lookup**: Patterns indexed by tinyId for O(applicable) vs O(all) per CDE
- **Parallel processing**: Chunks CDEs across workers, each producing all variants
- **Key files**: `logic/branching_stripper.py` (engine), `actions/strip_branching/` (action)
- **Workflow**: `branching_strip_nway.yaml` — 3 steps vs 13 in legacy pipeline
- **Configure**: `workflow configure CODE --nway` for nway-aware configuration

### v0.9.1: Production Strip Configurator + 6th Variant

#### 6th Branching Strip Variant (MTSTPT)
- **MTSTPT**: Full + sub instrument removal + phrase removal (maximum stripping)
- Pipeline extended from 5 to 6 variants (10 → 13 steps)
- Output naming standardized to `stripped_{CODE}.json` format

#### Production Strip Configurator (`workflow configure`)
- **`workflow configure CODE [CODE...] [-o FILE]`**: Maps strip codes to required pipeline steps
- **Without `-o`**: Prints step list + ready-to-use `workflow run --only-steps ...` command
- **With `-o FILE`**: Generates production YAML with only needed steps and variables
- **`--no-report`**: Exclude quality_report step
- **Smart `--set` hints**: Conditionally shows `inst_patterns_base` / `phrase_patterns` based on code positions
- **Step dependency map**: `STRIP_CODE_STEPS` constant in `actions/workflow/run.py`

#### Generic Step Filtering (`--only-steps`)
- **`workflow run --only-steps S1,S2,...`**: Filter step list before execution
- Works with any workflow YAML, not just branching strip
- Preserves YAML-defined step order; warns on unknown names; errors on empty result
- Composable with `--from-step`

### v0.9.0: Zipf Priority Split + Editor Improvements

#### Zipf-Based Curation Triage (`--split-priority`)
- **`--split-priority FILE`**: Splits `needs_review.tsv` into high-priority and low-priority files using wordfreq Zipf frequency scores
- **Classification**: If ALL word tokens in a pattern have Zipf >= threshold (default 4.0), pattern is low-priority (common English); otherwise high-priority (domain-specific)
- **`--split-auto-remove`**: Pre-fills `decision=remove` in low-priority patterns for fast single-reviewer triage
- **Outputs**: `{stem}_high.tsv` (multi-reviewer) + `{stem}_low.tsv` (fast triage)
- **allcde03 empirical results**: 1,480 patterns → 582 high-priority + 898 low-priority
- **Zipf reference**: 3=uncommon, 4=common (~top 6K words), 5=very common
- **Key files**: `actions/pattern_util/cli.py` (CLI args), `actions/pattern_util/run.py:_run_split_priority()`

#### TSV Editor UX Improvements
- **Propagate scoping**: Selection-aware group propagation with tiered warnings (selected groups only, or all if none selected)
- **Clear filters**: `Clear Filters` button + `Ctrl+Shift+F` shortcut to reset all column filters
- **Numeric equals filter**: Full operator support (`=`, `==`, `!=`, `>=`, `<=`, bare numbers)
- **Checkbox click targets**: Enlarged via pointer-events on `<td>` wrapper

#### Version Sync Mechanism
- **`tools/editor_standalone/__main__.py`**: `_resolve_version()` tries dynamic import from `cde_analyzer.__version__`, falls back to `_FALLBACK_VERSION`
- **`scripts/build_editor_zipapp.py`**: Smart `_stamp_version()` — preserves 4-segment editor versions (e.g., 0.8.1.4) when base matches, overwrites when base differs

#### Parameter Tuning Documentation
- **`docs/vignettes/parameter-tuning.md`**: New §3 "Most Influential Parameters" with empirical data from 3 production runs (allcde01/02/03)
- Impact ranking: `min_parent_tinyids` > `min_field_count` > `k_max` > `min_tokens` > `k_min`
- False-positive/false-negative tradeoff table with Zipf split workflow
- Updated `k_max` recommendation to 90 for all dataset sizes

### v0.8.1: Substitute Decision Type

#### 4th Curation Decision
- **`substitute`**: Replaces matched text with `modification` column content (vs `keep`=delete, `modify`=change pattern then delete)
- Semantics: pattern matched → replaced with modification text in output (not deleted)
- Runs as separate pass **before** stripping via `apply_substitutions` pipeline step

#### Pipeline Integration
- `_build_curated_from_auto()` returns `(curated_rows, substitute_rows)` tuple
- `_write_substitute_tsv()` writes `substitute_patterns.tsv` with `replace_with` column
- `instrument_pipeline.yaml` + `phrase_pipeline.yaml`: new `apply_substitutions` step between finalize and strip
- `branching_strip.yaml`: substitute pre-pass documented (user applies before branching)
- Empty `substitute_patterns.tsv` (header-only) makes strip step a no-op

#### Ledger Support
- `classify_patterns()`: `auto_substitute` (same tinyIds) / `needs_review` (new tinyIds)
- `record_run()`: logs `n_auto_substituted`

#### TSV Editor
- Cyan badge, `S` keyboard shortcut, toolbar button, filter dropdown, `⇄N` status counter
- `propagateGroups()` supports substitute source rows (copies actual decision, not hardcoded `modify`)

### v0.8.0: Incremental Curation (Curation Ledger & Gate)

#### Curation Ledger (`logic/curation_ledger.py`)
- **`CurationLedger`**: Persistent record of keep/remove/modify/substitute decisions across pipeline runs
- **Storage**: `{ledger_dir}/ledger_meta.yaml` (run history) + `instrument_decisions.tsv` / `phrase_decisions.tsv`
- **`classify_patterns()`**: Compares current patterns against prior decisions
  - keep + any tinyIds → auto_keep (validity is inherent)
  - remove + same tinyIds → auto_remove; remove + new tinyIds → needs_review
  - modify + same tinyIds → auto_modify; modify + new tinyIds → needs_review
  - substitute + same tinyIds → auto_substitute; substitute + new tinyIds → needs_review
  - new pattern (not in ledger) → needs_review

#### Curation Gate (`--curation-gate`)
- **Runs before checkpoint**: Classifies patterns as auto-resolved or needs-review
- **Outputs**: `gate_result.json`, `auto_resolved.tsv`, `needs_review.tsv`, and optionally `curated.tsv`
- **If all auto-resolved**: Writes `curated.tsv` directly → checkpoint is skipped
- **If needs review**: Only new/changed patterns presented to curators

#### Finalize Curation (`--finalize-curation`)
- **Runs after checkpoint**: Merges auto-resolved + human-curated → `curated.tsv`, updates ledger
- **Records all decisions** in the curation ledger for future runs

#### Conditional Checkpoint (`skip_if_file`)
- **Workflow engine extension**: `skip_if_file: "${curated_tsv}"` on checkpoint steps
- **If file exists**: Checkpoint is skipped, workflow continues to next step

#### Workflow Integration
- Both `instrument_pipeline.yaml` and `phrase_pipeline.yaml` updated with gate/finalize steps
- **New variable**: `curation_ledger_dir: "${CURATION_LEDGER:-../.curation_ledger}"`

### v0.7.0: Standalone Editor Zipapp + Synthetic QC Data + Rare Words

#### Standalone Editor (Zipapp Distribution)
- **`tools/editor_standalone/__main__.py`**: Self-contained TSV editor server (zero cde_analyzer imports, stdlib only)
- **`scripts/build_editor_zipapp.py`**: Build script → `dist/cde_editor.pyz` (~59 KB)
- **CLI**: `python cde_editor.pyz [FILE] [--port N] [--no-browser] [--version]`
- **Resource loading**: `_load_html()` reads `tsv_editor.html` from filesystem (dev) or zipapp archive (distribution)
- **HTTP endpoints**: GET `/` (HTML), GET `/info` (metadata), GET `/data` (TSV content), POST `/save` (write file)
- **Distributed curation workflow**: build zipapp → init-curation → distribute → curate → merge → resolve → finalize

#### Centralized Curation Server
- **`actions/pattern_util/centralized_server.py`**: Multi-curator HTTP server with token-scoped routes
- **`actions/pattern_util/editor_config.py`**: YAML config parsing (curators, server, TLS, security)
- **`actions/pattern_util/editor_security.py`**: HMAC token gen/verify, rate limiting, TLS setup
- **CLI**: `--serve-curation CONFIG --curation-source FILE`, `--curation-status DIR`
- **Token auth**: `{slug}_{expiry_hex}_{hmac[:16]}` — per-curator HMAC-SHA256 tokens with expiry
- **Routes**: `/c/{token}/` (editor), `/c/{token}/data|info|save` (API), `/admin/` (dashboard)
- **TLS modes**: `auto` (self-signed), `custom` (user certs), `proxy` (reverse proxy)
- **Security**: Rate limiting with exponential backoff, directory isolation, expiry watchdog
- **Vignette**: `docs/vignettes/distributed-curation.md` — file-based and centralized workflows

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
- **`docs/vignettes/distributed-curation.md`**: Multi-curator workflow with standalone editor zipapp
- **`mkdocs.yml`**: "Guides" → "Guides & Vignettes" with 7 entries

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
- **LLM pipeline integration** — `llm_classify` action exists but not yet integrated into workflow pipelines
- **Position-specific field-aware stripping** — architecture ready in branching_stripper
- **Full regression test** — legacy vs nway branching strip on allcde03 after curation

## Key Files

### Source Code (cde_analyzer/)
- `actions/pattern_util/cli.py` — CLI definitions for pattern_util (incl. init-curation, merge-curation, serve-curation, curation-gate, finalize-curation)
- `actions/pattern_util/run.py` — pattern_util orchestration (coalesce, merge, field analysis, validate subsumption, expand temporal seeds, init-curation, merge-curation, serve-curation, curation-gate, finalize-curation)
- `actions/pattern_util/centralized_server.py` — centralized multi-curator curation server (CurationState, CuratorSession, serve_curation)
- `actions/pattern_util/editor_config.py` — curation server config parsing (CurationServerConfig, load_config)
- `actions/pattern_util/editor_security.py` — token gen/verify, RateLimiter, TLS setup
- `actions/workflow/cli.py` — CLI definitions for workflow (incl. scaffold, configure)
- `actions/workflow/run.py` — workflow orchestration (run, resume, scaffold, list, copy, status, skip_if_file, configure)
- `logic/curation_ledger.py` — CurationLedger, CurationDecision, classify_patterns (incremental curation)
- `logic/inter_rater.py` — inter-rater reliability statistics (Cohen's/Fleiss' kappa, Krippendorff's alpha)
- `actions/phrase_miner/run.py` — phrase miner runner + `write_dedup_curation_tsv()`
- `logic/phrase_miner.py` — core mining: `dedup_field_texts()`, `mine_phrases()`, k-mer loop, masking
- `actions/strip_branching/cli.py` — CLI for N-way branching strip
- `actions/strip_branching/run.py` — N-way branching strip orchestration
- `logic/branching_stripper.py` — N-way branching strip engine (StripStage, strip_branching, build_tinyid_index)
- `actions/strip_discover/run.py` — `compute_field_distribution()`, `build_field_text_index()`
- `actions/strip_phrases/run.py` — stripping engine
- `utils/instrument_extractor.py` — instrument name extraction
- `utils/flexible_pattern_matcher.py` — coalescer (Phase 1a prefix-kept, Phase 1b NP-continuity)
- `config/temporal_seed_patterns.yaml` — 25 temporal seed patterns (~2100 expanded variants)
- `utils/pattern_variant_generator.py` — temporal/case/number/plural variant generators
- `tools/editor_standalone/__main__.py` — standalone TSV editor server (zipapp entry point)
- `scripts/build_editor_zipapp.py` — build script for `dist/cde_editor.pyz`

### Workflows
- `workflows/instrument_pipeline.yaml` — Phase 1
- `workflows/phrase_pipeline.yaml` — Phase 2
- `workflows/branching_strip.yaml` — Phase 3 (6-way branch, 13-step legacy)
- `workflows/branching_strip_nway.yaml` — Phase 3 (N-way single-pass, 3 steps)

### Documentation
- `docs/vignettes/` — 8 vignettes (index, quickstart, instrument-detection, pipeline-orchestration, parameter-tuning, phrase-stripping, distributed-curation, synthetic-data)
- `docs/help/` — 28 per-command reference pages
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

## `pattern_util` Capabilities (partial — run `cde-analyzer pattern_util --help` for full list)

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
cde-analyzer pattern_util --serve-curation CONFIG --curation-source FILE  # centralized server
cde-analyzer pattern_util --curation-status DIR                   # check centralized session status
cde-analyzer pattern_util --curation-gate FILE --ledger-dir DIR --phase P -i JSON -o DIR  # incremental curation gate
cde-analyzer pattern_util --finalize-curation DIR --ledger-dir DIR --phase P -i JSON      # finalize + update ledger
cde-analyzer pattern_util --split-priority FILE [--split-auto-remove]                     # Zipf-based priority split
```

## `workflow` Capabilities

```bash
cde-analyzer workflow run YAML [--set K=V] [--from-step S] [--only-steps S1,S2] [--dry-run]  # execute pipeline
cde-analyzer workflow resume --state-file FILE                          # resume after checkpoint
cde-analyzer workflow status [--state-file FILE] [-v]                   # check pipeline state
cde-analyzer workflow list                                              # list built-in workflows
cde-analyzer workflow copy NAME [--as FILE]                             # copy template to project
cde-analyzer workflow scaffold PROJECT -i JSON -d DIR [--phases 1,2,3] [--with-iterate]  # generate orchestration script
cde-analyzer workflow configure CODE [CODE...] [-o FILE] [--no-report] [--nway]  # configure branching strip for specific variants
```

## `strip_branching` Capabilities

```bash
cde-analyzer strip_branching -i JSON -d OUTPUT_DIR \
    --inst-full-patterns TSV --inst-sub-patterns TSV \
    --temporal-patterns TSV --phrase-patterns TSV \
    [--variants CODES] [--workers N] [--clean-remnants]
```
