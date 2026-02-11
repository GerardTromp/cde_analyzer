# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.12] - 2026-02-11

### Added
- `pattern_util --validate-subsumption` — empirical post-coalescing validation
  - Checks source text per-tinyId per-field to determine which patterns are actually needed
  - Drops shorter patterns whose occurrences are always covered by longer group members
  - Parallelized with `ProcessPoolExecutor`, greedy bin packing by tinyId count
  - `--workers N` flag (0 = sequential); sequential and parallel produce identical output
- Example CDE columns in `--field-analysis` enriched output
  - `example_name` (designation[0]), `example_question` (designation[1]), `example_definition` (definition[0])
  - Inserted after `pattern` column; text truncated to 120 chars
  - Idempotent: re-runs strip old example columns before adding new ones
- NUMERIC_WORD support in instrument extractor
  - Standalone numbers now recognized in instrument names (e.g., "Trial of ORG 10172 in Acute Stroke Treatment")
  - `_is_valid_instrument_name()` counts digit words as correct

### Fixed
- Coalescer trailing-punctuation trie bug: "Well-Being" and "Well-Being." no longer split into separate trie branches
  - Phase 2 prefix trie now normalizes trailing punctuation (`.,;:!?`) before token insertion
  - Group key computation uses punctuation-aware word comparison
  - ~15 patterns now preserve full names that were previously truncated (e.g., "Neuro-QOL Positive Affect and Well-Being", "Los Angeles Motor Scale", "NIH Toolbox Cognitive Battery")

### Changed
- `validate_subsumption` step added to `instrument_pipeline.yaml` between `coalesce_patterns` and `enrich_fields`
- `enrich_fields` now reads `validated.tsv` instead of `coalesced.tsv`
- `build_field_text_index()` extracted from `compute_field_distribution()` in `strip_discover/run.py` for reuse

## [0.5.6] - 2026-02-10

### Added
- `pattern_util --edit FILE` — interactive browser-based TSV editor for pattern curation
  - Hybrid architecture: standalone HTML (drag-drop) + Python server (direct save-back)
  - Self-contained HTML file with no external dependencies (vanilla JS/CSS)
  - Python server uses stdlib `http.server` with REST endpoints (`/info`, `/data`, `POST /save`)
  - Features: sortable columns, column filtering (with `>N`, `<N`, `!negation` syntax), inline cell editing, row selection (Shift/Ctrl-click), bulk categorize, merge rows (union tinyIds), split by field_profile, drag-and-drop row reorder, undo/redo (Ctrl+Z, 50 levels), tinyId collapsed/expanded display, field_profile color coding, unsaved changes detection
  - `--port PORT` — specify server port (default: auto-assign)
  - `--no-browser` — start server without opening browser

## [0.5.5] - 2026-02-10

### Added
- New action: `strip_report` — generate markdown quality reports for stripped JSON outputs
  - Per-branch remnant detection matrix (15 detritus types × N branches)
  - Remaining temporal phrase inventory with tinyId counts
  - Embed data CSV manifest (file sizes, row counts)
  - Version history tracking across iterations
  - Auto-detects `*_stripped.json` files in output directory
- Quality report step added to `branching_strip.yaml` workflow (runs automatically after stripping)

## [0.5.4] - 2026-02-09

### Added
- Temporal preposition variant expansion in `--expand-verbatim`
  - Patterns starting with `[in|over|during|for|within] the [past|last]` generate all preposition × tense-word combinations
  - `--no-temporal-variants` flag to disable
  - `TEMPORAL_PREPOSITIONS`, `TEMPORAL_TENSE_WORDS` constants and `generate_temporal_preposition_variants()` in `utils/pattern_variant_generator.py`
  - Pipeline order: Temporal → Plural → Number → Case (temporal first so downstream stages multiply across all preposition variants)

### Changed
- `--expand-verbatim` pipeline now runs temporal preposition expansion as first stage (before plural/number/case)

## [0.5.3] - 2026-02-09

### Added
- `pattern_util --expand-verbatim` — expand curated patterns with narrow verbatim variants
  - Case variants: original + all-lowercase
  - Number variants: digit ↔ word (`7` ↔ `seven`) via existing `generate_number_variants()`
  - Plural variants: temporal singular ↔ plural (`day` ↔ `days`, `week` ↔ `weeks`)
  - `--rescan` — re-scan source JSON to discover tinyIds per variant (instead of inheriting)
  - `--no-case-variants`, `--no-number-variants`, `--no-plural-variants` — disable specific variant types
- `strip_phrases --word-boundary` — use `\b` regex anchors for pattern matching
  - Prevents partial-word matches: "in the past" will NOT match inside "within the past"
  - Composable with `--ignore-case` (both flags can be active simultaneously)
- `strip_phrases --ignore-case` — case-insensitive pattern matching via `re.IGNORECASE`
- `generate_case_variants()` and `generate_plural_variants()` in `utils/pattern_variant_generator.py`
- `TEMPORAL_PLURALS` dictionary for singular/plural temporal word mapping

### Changed
- `strip_phrases` matching engine now supports three modes: exact substring (default), word-boundary regex, and case-insensitive regex — modes compose via flag combination
- `_worker_init()` and `strip_phrases()` accept `case_insensitive` and `word_boundary` parameters for parallel worker propagation

## [0.5.1] - 2026-01-29

### Added
- New action: `discovery_report` — generates markdown pipeline summary reports
  - Per-step metrics (row counts, tinyId coverage, subsumption stats)
  - Sanity check survivor census (instrument pipeline)
  - Version history tracking across iterations
- `pattern_util --field-analysis` — enrich patterns TSV with per-field counts and field_profile
- `pattern_util --min-field-count`, `--min-tokens`, `--exclude-patterns` — field analysis filters
- `pattern_util --emit-def-variants` — emit definition-form variants (without trailing separator)
- `pattern_util --split-tiers` — split coalesced output into tier-1/tier-2 by token count
- `pattern_util --rollup-subset-tinyids` — tinyId-subset rollup during coalesce
- `pattern_util --group-hierarchy` — assign group/sub_group labels by shared prefix
- `strip_discover --min-bare-words` — filter short bare instrument names
- `strip_discover --discover-abbreviations` — abbreviation-based designation pattern discovery
- Two-pass stripping in instrument pipeline (tier-1 long patterns, then tier-2 short fragments)
- Recall analysis steps integrated into both pipeline workflows
- Documentation: `docs/extensions_v0.5.x.md`, `docs/lessons_learned_20260129.md`

### Changed
- `coalesce_variants_tsv()` now trims anchor phrases by default (disable with `--no-trim-anchors`)
- `extract_bare_instrument_names()` accepts `min_words` parameter
- Rollup-subset now requires substring match (prevents unrelated pattern subsumption)
- Roll-down logic requires minimum 2-word base (prevents single-word false positives)
- `instrument_detection.yaml` — added emit-def-variants, split-tiers, two-pass stripping, discovery_report
- `phrase_pipeline.yaml` — added field analysis filters, parent phrase tracking, discovery_report

## [Unreleased]

### Added
- PyPI packaging support with `pyproject.toml`
- `requirements.txt` for production dependencies
- `requirements-dev.txt` for development dependencies
- CLI argument standardization audit and documentation
- Package `__init__.py` files for proper module structure
- MIT License
- This CHANGELOG file
- Version management via `__version__.py`
- Shared CLI argument groups in `utils/cli_args.py` for consistent argument handling

### Changed
- **BREAKING**: `count` action: `--verbose` changed to `--verbosity, -v` with count action
- **BREAKING**: `strip_html` action: `--format` changed to `--output-format`
- Standardized short flag order across all actions (now `--long, -short` consistently)
- `strip_phrases` action: Reordered arguments to use `--long, -short` pattern
- Prepared for `pip install cde-analyzer` distribution
- Documentation updates for installation

## [0.2.0] - 2026-01-13

### Added
- PyPI packaging configuration
- Comprehensive dependency specification
- Package metadata and entry points
- CLI argument standardization plan
- Packaging and deployment documentation

### Changed
- Repository structure prepared for PyPI distribution
- Added proper Python package initialization files

### Fixed
- Launcher fixes post lazy-load refactoring (commits 4e601c7, 57b9437)
- Repository cleanup (commit 83f1df2)

## [0.1.0] - 2024-12-XX

### Added
- Lazy loading architecture for fast CLI startup (commit 4400bf7)
- Action-based plugin system
- Nine CLI actions:
  - `fix_underscores` - Fix Pydantic-incompatible field names
  - `strip_html` - Remove HTML markup from CDE fields
  - `phrase` - Find repeated phrases across CDE records
  - `count` - Count structural elements and field occurrences
  - `extract_embed` - Extract fields for transformer model embedding
  - `strip_phrases` - Remove literal phrases at specified paths
  - `lemma_fasta` - Create FASTA format from lemma sequences
  - `phrase_builder` - Incremental phrase construction
  - `subset` - Extract subsets using filters

### Changed
- Major refactoring to lazy loading architecture
- Dramatic startup performance improvement
- CLI structure inspired by git/pip command model

### Technical Details
- Pydantic 2.x models for NLM CDE API schema
- Recursive descent visitor pattern for nested data traversal
- Multiple output formats (JSON, CSV, TSV)
- Optional HTML table parsing
- Lemmatization support for phrase extraction
- FASTA format export for bioinformatics tools

## [0.0.1] - 2024-XX-XX (Initial Development)

### Added
- Initial implementation of CDE data models
- Basic CLI structure
- Recursive descent engine (core/recursor.py)
- HTML stripping functionality
- Field counting capabilities
- Phrase extraction (experimental kmer approaches)

---

## Version History Notes

### Version Numbering
- **0.x.x** - Pre-1.0 development releases
- **0.1.0** - Initial implementation (pre-lazy loading)
- **0.2.0** - Lazy loading + PyPI packaging (current)
- **1.0.0** - Planned stable release (future)

### Deprecations
None yet (pre-1.0 development)

### Security
No known security issues

### Known Issues
- Test coverage minimal (needs expansion before 1.0)
- CLI argument naming inconsistent (standardization planned for 0.3.0)
- Legacy kmer_*.py files retained but not actively maintained
- Documentation incomplete (comprehensive docs planned)

---

## Migration Guides

### Migrating from 0.1.x to 0.2.x
No breaking changes. All existing usage patterns continue to work.

**New features available**:
- Can now install via `pip install cde-analyzer` (once published)
- New command-line entry point: `cde-analyzer` (in addition to `python cde_analyzer.py`)

### Future Breaking Changes (0.3.0)
Planned CLI argument standardization may deprecate some argument names.
Deprecation warnings will be added before removal.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information on how to contribute to this project.

---

## Links

- **GitHub**: https://github.com/gtromp/cde-analyzer
- **PyPI**: https://pypi.org/project/cde-analyzer/ (pending publication)
- **Documentation**: https://cde-analyzer.readthedocs.io (planned)
- **Issue Tracker**: https://github.com/gtromp/cde-analyzer/issues

[Unreleased]: https://github.com/gtromp/cde-analyzer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gtromp/cde-analyzer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gtromp/cde-analyzer/releases/tag/v0.1.0
