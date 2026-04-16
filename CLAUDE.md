# CDE Analyzer — Context (v1.5.1)

> **Full context**: Read `CLAUDE_full.md` for complete project documentation.
> **Restore**: Copy `CLAUDE_full.md` back to `CLAUDE.md` when switching tasks.

## Version String Locations — UPDATE ALL ON VERSION BUMP

When changing the version, **all three files must be updated together**:

| # | File | Variable | Example |
|---|------|----------|---------|
| 1 | `cde_analyzer/__version__.py` | `__version__` | `__version__ = "X.Y.Z"` |
| 2 | `pyproject.toml` | `version` | `version = "X.Y.Z"` |
| 3 | `tools/editor_standalone/__main__.py` | `_FALLBACK_VERSION` | `_FALLBACK_VERSION = "X.Y.Z"` |

Also update the version in these documentary locations:

| # | File | Location |
|---|------|----------|
| 4 | `CLAUDE.md` | Heading `# CDE Analyzer — Context (vX.Y.Z)` + `## Current State` |
| 5 | `CLAUDE_full.md` | `**Active Branch**` line |
| 6 | `.claude/context/08-progress.md` | `**Version**` line + `## Current State` heading |
| 7 | `.claude/context/README.md` | Quick Recovery item 1 |
| 8 | `docs/curator-briefing.md` | `> **Version**:` line (line 3) |
| 9 | `docs/tsv-editor-cheatsheet.md` | `> **Version**:` line (line 3) |
| 10 | `docs/presentations/pipeline_overview/cde_pipeline_overview.md` | `**Version**:` line (line 8) |

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
- **Legacy** (`branching_strip.yaml`): strip_inst_full/sub → expand_temporal → strip_temporal (case-insensitive) → strip_phrases (case-sensitive) → quality_report (10 steps)
- **N-way** (`branching_strip_nway.yaml`): expand_temporal → strip_branching (single-pass, all 7 variants) → quality_report (3 steps)

## Current State (v1.5.1)

### v1.0.0: Production Release

#### Config-Driven Pipeline Scaffold
- **`workflow scaffold --from-config`**: Generate full-featured `run_pipeline.sh` from YAML config
- Status dashboard, completion guards, curation resume, iterative harvesting
- Windows→WSL path auto-conversion
- Example config: `examples/pipeline_config.yaml`

#### Action Refactoring
- `pattern_util` split into focused actions: `curation`, `instrument_util`, `pattern_diag`, `supplementary`, `llm_classify`
- All workflow YAMLs and pipeline scripts updated to new action names

#### pyproject.toml
- Development Status upgraded from "Beta" to "Production/Stable"

### v0.9.8: Field-Aware Splits + 7-Way Branching Strip

#### Field-Aware Instrument Splits
- **Three-component decomposition**: Each curated instrument pattern split into Full (group prefix), Sub (separator + suffix), and Abbreviation
- `inst_full` and `inst_sub` now operate on **different text spans**, making all 7 variants genuinely distinct
- **Group-scoped re-matching**: Sub-patterns only matched against CDEs within their instrument group's tinyId scope, preventing cross-instrument contamination
- **QC validated**: 20 double-space artifacts (v2/unscoped) → 0 (v3/scoped)
- 7 variants: MTSFPF, MFSTPF, MTSTPF, MFSFPT, MTSFPT, MFSTPT, MTSTPT
- Verbatim patterns from `config/verbatim_strip_patterns.yaml` auto-merged into `inst_full` stage via `--verbatim-patterns`

#### allcde03 Production Run (v3 strip patterns)
- 22,743 CDEs × 7 variants (N-way single-pass)
- Pattern inventory: 383 inst_full + 252 inst_sub + 273 curated phrases + 7 substitutes + 39 verbatim + 2,100 temporal
- Quality: 84.2% fields at 90-100% retention (MTSFPT), 0 stripping artifacts, 6 trailing_article remnants per variant
- Run details: `docs/runs/allcde03-branching-strip-run.md`

### v0.9.6: 5-Way Branching Strip + allcde03 Run (superseded by v0.9.8)

- Pre-field-aware-splits version with identical inst_full/inst_sub patterns
- 5 variants (MT+ST combinations degenerate)

### v0.9.5: Containment Tree in TSV Editor

#### Containment Tree View
- **Prefix-containment tree**: Automatic hierarchical grouping of patterns by text prefix + tinyId subset containment
- **Containment rule**: Pattern A contains pattern B if A is a word-level prefix of B AND A's tinyIds ⊇ B's tinyIds
- **Algorithm**: O(n*k) word-level prefix generation + Map lookup (not naive O(n²))
- **Quick-reject**: Skip subset check if child tinyId set is larger than parent
- **Tree column**: Virtual column (not saved to TSV) inserted as column #3, showing hierarchy
- **Visual elements**: ▶/▼ collapse toggles, purple descendant count badges, `⊃ parent` child references, depth dots (·, ··)
- **Tree sort** (`T` key): DFS traversal grouping children under parents, sorted by tinyid_count descending
- **Tree propagate** (⊃ Propagate button): Copy decision from parent(s) to all contained children, selection-aware
- **Tree filter**: Dropdown with (all), root, child, none options
- **Collapse/expand**: Click ▶/▼ toggles to collapse/expand subtrees
- **Status bar**: Shows `⊃N trees, M contained` count
- **Design decision**: Tree is computed client-side on data load; virtual column avoids polluting saved TSV
- **allcde03 empirical results**: 818/4006 patterns (20%) are fully contained by shorter prefixes; largest tree: "Scale related to" (38 members, depth 3, 818 tinyIds)
- **Key file**: `actions/pattern_util/tsv_editor.html` — `_buildContainmentTree()`, `_getTreeDfsOrder()`, `_renderTreeCell()`

### v0.9.4: Deferred Parent Filter + Anchor Trim Control + Followup Decision

#### Phrase Pipeline Correctness
- **Deferred parent filter** (`--defer-parent-filter`): Weak-parent patterns participate in prefix extraction before filtering. Rescued by prefix groups survive. Phrase pipeline default: true
- **No-trim-anchors** (`--no-trim-anchors`): Disables Phase 0 anchor trimming. Critical for phrases. Phrase pipeline default: true
- **Phase 1b protection**: Skip reverse subsumption for weak-parent patterns in deferred mode
- **Divergence warning**: Fires when parent filter removes patterns with high actual/parent ratio (>5x)

#### Phrase Miner Enhancements
- **Prefix consolidation**: Post-loop token-ID prefix trie recovers fragmented prefixes masked across multiple k-levels
- **Ledger pre-masking** (`--ledger-dir`): Prior "skip" decisions pre-masked during mining

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
- **Single-pass**: Loads CDE JSON once, produces all 5 variants simultaneously
- **Shared intermediates**: `inst_full` result reused across MTSFPF, MTSFPT
- **4 strip stages**: `inst_full`, `inst_sub`, `temporal`, `phrase` — each with appropriate settings
- **TinyId-indexed lookup**: Patterns indexed by tinyId for O(applicable) vs O(all) per CDE
- **Parallel processing**: Chunks CDEs across workers, each producing all variants
- **Key files**: `logic/branching_stripper.py` (engine), `actions/strip_branching/` (action)
- **Workflow**: `branching_strip_nway.yaml` — 3 steps vs 10 in legacy pipeline
- **Configure**: `workflow configure CODE --nway` for nway-aware configuration

### v0.9.1: Production Strip Configurator

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
- **`--split-auto-skip`**: Pre-fills `decision=skip` in low-priority patterns for fast single-reviewer triage
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
- **`substitute`**: Replaces matched text with `modification` column content (vs `strip`=delete, `modify`=change pattern then delete)
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
- Cyan badge, `U` keyboard shortcut, toolbar button, filter dropdown, `⇄N` status counter
- `propagateGroups()` supports substitute source rows (copies actual decision, not hardcoded `modify`)

### v0.8.0: Incremental Curation (Curation Ledger & Gate)

#### Curation Ledger (`logic/curation_ledger.py`)
- **`CurationLedger`**: Persistent record of strip/skip/modify/substitute decisions across pipeline runs
- **Storage**: `{ledger_dir}/ledger_meta.yaml` (run history) + `instrument_decisions.tsv` / `phrase_decisions.tsv`
- **`classify_patterns()`**: Compares current patterns against prior decisions
  - strip + any tinyIds → auto_strip (validity is inherent)
  - skip + same tinyIds → auto_skip; skip + new tinyIds → needs_review
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
- `actions/pattern_util/` — Pattern TSV utilities (coalesce, merge, field analysis, validate, expand temporal, edit, split-priority)
- `actions/curation/` — Curation lifecycle (edit, gate, finalize, init/merge multi-curator, serve centralized)
- `actions/instrument_util/` — Instrument-specific utilities (group-hierarchy, generate-strip-patterns, analyze-instrument-splits)
- `actions/supplementary/` — Supplementary pattern management (harvest-residuals, update-ledger, harvest-to-supplementary, promote)
- `actions/pattern_diag/` — Pattern diagnostics (curation-status)
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
- `workflows/production_strip.yaml` — **Production default**: pre-curated strip + embed extraction (ML baseline, 7 steps)
- `workflows/instrument_pipeline.yaml` — Phase 1
- `workflows/phrase_pipeline.yaml` — Phase 2
- `workflows/branching_strip.yaml` — Phase 3 (5-way branch, 10-step legacy)
- `workflows/branching_strip_nway.yaml` — Phase 3 (N-way single-pass, 3 steps)

### Documentation
- `docs/vignettes/` — 8 vignettes (index, quickstart, instrument-detection, pipeline-orchestration, parameter-tuning, phrase-stripping, distributed-curation, synthetic-data)
- `docs/help/` — 29 per-command reference pages
- `docs/workflow-architecture.md` — pipeline diagrams + design rationale

### Data
- `data/reference_ledger/` — Official curation ledger (allcde03: 458 instrument + 4,058 phrase decisions, Curator B baseline)
  - `production_patterns/` — Ready-to-use pattern files for `production_strip.yaml`
  - Copy to `.curation_ledger/` to bootstrap incremental curation for new projects
  - `MANIFEST.yaml` — provenance, checksums, decision counts
- `config/embed_path_schemas/` — Pydantic path schemas for `extract_embed`
  - `NQD.csv` (production default: Name, Question, Definition)
  - `NQDP.csv`, `full_designations.csv` (extended variants)
- `examples/pipeline_config.yaml` — Example YAML config for `workflow scaffold --from-config`

## Architecture Reminders

- **Three-layer actions**: `cli.py` (args) → `run.py` (orchestration) → `logic/` (algorithms)
- **Lazy loading**: All imports inside functions
- **Pattern TSV format**: `pattern\ttinyIds\ttype\tsource_pattern` + optional field columns
- **Field paths**: `definitions.*.definition`, `designations.*.designation`
- **K-mer mining**: Descending (k_max → k_min), masks detected phrases after each k
- **Dedup**: Identification only (no masking), separate curation template, >k_max filter

## Action Capabilities

### `pattern_util` — Pattern TSV utilities
```bash
cde-analyzer pattern_util --coalesce-variants FILE -o OUT         # subsumption + prefix trie
cde-analyzer pattern_util --merge-patterns FILE FILE -o OUT       # deduplicate/merge TSVs
cde-analyzer pattern_util --field-analysis FILE --input JSON -o OUT  # add field counts
cde-analyzer pattern_util --validate-subsumption FILE --input JSON -o OUT  # empirical validation
cde-analyzer pattern_util --expand-temporal-seeds -o OUT          # temporal seed expansion
cde-analyzer pattern_util --split-priority FILE [--split-auto-skip]  # Zipf-based priority split
```

### `curation` — Curation lifecycle
```bash
cde-analyzer curation --edit FILE                                       # browser-based TSV editor
cde-analyzer curation --curation-gate FILE --ledger-dir DIR --phase P -i JSON -o DIR  # incremental gate
cde-analyzer curation --finalize-curation DIR --ledger-dir DIR --phase P -i JSON      # finalize + update ledger
cde-analyzer curation --init-curation FILE -o DIR                       # initialize multi-curator curation
cde-analyzer curation --merge-curation FILE -o OUT                      # merge curator annotations + stats
cde-analyzer curation --serve-curation CONFIG --curation-source FILE    # centralized server
```

### `instrument_util` — Instrument-specific utilities
```bash
cde-analyzer instrument_util --group-hierarchy FILE -o OUT              # assign group hierarchy
cde-analyzer instrument_util --generate-strip-patterns FILE -o BASE     # generate inst_full/sub TSVs
cde-analyzer instrument_util --analyze-instrument-splits FILE -i JSON -o OUT  # field-aware split analysis
```

### `supplementary` — Supplementary pattern management
```bash
cde-analyzer supplementary --harvest-residuals FILE --curated FILE -i JSON -o OUT  # harvest residuals
cde-analyzer supplementary --update-ledger FILE --ledger FILE -o OUT    # update pattern ledger
cde-analyzer supplementary --harvest-to-supplementary FILE              # ingest to local supplementary
cde-analyzer supplementary --promote-supplementary                      # promote to global config
```

### `workflow` — Pipeline orchestration
```bash
cde-analyzer workflow run YAML [--set K=V] [--from-step S] [--only-steps S1,S2] [--dry-run]
cde-analyzer workflow resume --state-file FILE
cde-analyzer workflow status [--state-file FILE] [-v]
cde-analyzer workflow list                                              # list built-in templates
cde-analyzer workflow copy NAME [--as FILE]                             # copy template to project
cde-analyzer workflow scaffold --from-config CONFIG.yaml [-o FILE]      # config-driven script generation
cde-analyzer workflow scaffold PROJECT -i JSON -d DIR [--with-iterate]  # legacy CLI mode
cde-analyzer workflow configure CODE [CODE...] [-o FILE] [--nway]       # configure branching strip
```

## `strip_branching` Capabilities

```bash
cde-analyzer strip_branching -i JSON -d OUTPUT_DIR \
    --inst-full-patterns TSV --inst-sub-patterns TSV \
    --temporal-patterns TSV --phrase-patterns TSV \
    [--variants CODES] [--workers N] [--clean-remnants]
```

## Shell Execution (inherited from parent CLAUDE.md)

All Claude sessions MUST follow the shell execution mandates defined in
`../../CLAUDE.md` § "Shell Execution Mandates":

1. **Strip PATH**: `export PATH="/c/Windows/system32:/c/Windows"`
2. **Always use WSL**: `MSYS_NO_PATHCONV=1 wsl --distribution Ubuntu-22.04 -- <cmd>`
3. **Write scripts to files** for anything beyond simple one-liners
