# Architecture Decision Records

> **Updated**: v1.0.0 (2026-03-12)

## ADR-1: Flat Layout (Not Nested Package)

**Decision**: Source code lives at project root (`actions/`, `logic/`, `utils/`, `core/`) rather than nested under a `cde_analyzer/` package directory.

**Rationale**: The project started as a script collection; restructuring to nested layout would break all imports. `pyproject.toml` uses `setuptools.packages.find` with `where=["."]` to make it installable despite flat layout.

**Consequence**: `cde_analyzer/` subdirectory exists but is only used for `__version__.py`. All real code is at root level.

## ADR-2: Lazy-Loaded Action System

**Decision**: Actions are lazy-loaded via `ACTION_REGISTRY` in `cde_analyzer.py`. Only the invoked action's module is imported.

**Rationale**: Fast CLI startup (<0.5s) despite 30+ actions with heavy dependencies (spacy, pandas, nltk). Inspired by git/pip architecture.

**Trade-off**: Import errors only surface at invocation time, not at startup.

## ADR-3: Three-Layer Action Pattern

**Decision**: Every action follows `cli.py` (argument parsing) → `run.py` (orchestration, I/O) → `logic/` (algorithms).

**Rationale**: Separates concerns cleanly. Business logic is testable without CLI. Orchestration handles file I/O and formatting.

## ADR-4: Pattern TSV as Interchange Format

**Decision**: Tab-separated values (TSV) is the primary format for pattern data flowing between pipeline steps and human curation.

**Rationale**: TSV is spreadsheet-compatible (Excel, Google Sheets), diff-friendly, and human-readable. Patterns may contain commas, making CSV problematic. The `tinyIds` column uses comma-separated values within a single TSV field.

## ADR-5: Descending K-mer Mining (k_max → k_min)

**Decision**: Mine phrases from longest (k_max=90) down to shortest (k_min=3), masking detected phrases after each k-level.

**Rationale**: Prevents shorter subphrases of already-detected longer phrases from being re-detected. Masking ensures each token is claimed by at most one phrase.

**Alternative rejected**: Ascending mining would require complex post-hoc subsumption filtering.

## ADR-6: Branching Strip (7 Variants)

**Decision**: Produce 7 stripped variants simultaneously, varying the order and inclusion of instrument/phrase/temporal stripping.

**Rationale**: Different downstream tasks (embedding, clustering, search) benefit from different levels of text normalization. Rather than picking one strategy, generate all variants and let evaluation determine which is best.

**Codes**: MTSFPF, MFSTPF, MTSTPF, MFSFPT, MTSFPT, MFSTPT, MTSTPT (Main/Sub × Temporal × Full/Sub × Phrase × First/Temporal).

## ADR-7: Field-Aware Instrument Splits

**Decision**: Split curated instrument patterns into three components (Full = group prefix, Sub = separator + suffix, Abbreviation) that operate on different text spans.

**Rationale**: Pre-v0.9.8, `inst_full` and `inst_sub` patterns were identical substrings, making MT/ST variants degenerate (5 unique out of 7). Field-aware splits ensure all 7 variants are genuinely distinct.

**Implementation**: `instrument_util --generate-strip-patterns` with group-scoped re-matching to prevent cross-instrument contamination.

## ADR-8: Incremental Curation via Ledger

**Decision**: Persist all curation decisions in a ledger (`logic/curation_ledger.py`). On re-run, auto-resolve patterns matching prior decisions; present only new/changed patterns for review.

**Rationale**: Full re-curation of 4,000+ patterns per run is impractical. The ledger reduces subsequent runs to reviewing only genuinely new patterns.

**Classification rules**: `keep` + any tinyIds → auto_keep; `remove`/`modify`/`substitute` + same tinyIds → auto_resolve; different tinyIds → needs_review.

## ADR-9: Containment Tree (Client-Side, Virtual Column)

**Decision**: Compute the prefix-containment tree client-side in the TSV editor. The tree column is virtual (not saved to TSV).

**Rationale**: Avoids polluting the saved TSV with computed metadata. Tree structure depends on the current pattern set and would need recomputation anyway. Client-side computation keeps the server stateless.

## ADR-10: Workflow Engine with YAML Definitions

**Decision**: Pipeline steps are defined in YAML files and executed by a generic workflow engine (`actions/workflow/run.py`). Checkpoints pause for human intervention.

**Rationale**: Declarative pipelines are reproducible, versionable, and self-documenting. The checkpoint mechanism integrates human curation into an otherwise automated pipeline.

**Features**: Variable substitution (`${VAR}`), `--from-step` resume, `--only-steps` filtering, `skip_if_file` conditional checkpoints.

## ADR-11: Standalone Editor as Zipapp

**Decision**: The TSV curation editor is distributed as a self-contained Python zipapp (`cde_editor.pyz`, ~59 KB) with zero dependencies beyond stdlib.

**Rationale**: Curators may not have the full cde_analyzer environment. A single-file distribution with no install step maximizes adoption. The editor serves its HTML UI via a built-in HTTP server.

## ADR-12: Group-Scoped Sub-Pattern Re-Matching

**Decision**: When generating strip patterns, sub-patterns are re-matched only within their instrument group's tinyId scope, not against all CDEs.

**Rationale**: Unscoped re-matching caused common words (e.g., "Assessment") to match hundreds of unrelated CDEs, producing double-space stripping artifacts. Group scoping eliminated all 20 artifacts in allcde03.

**Discovery**: QC mining on stripped output (v2) revealed the issue; fixed in v3 patterns.

## ADR-13: Action Refactoring (v1.0.0)

**Decision**: Split the monolithic `pattern_util` action into focused actions: `curation`, `instrument_util`, `pattern_diag`, `supplementary`, `llm_classify`.

**Rationale**: `pattern_util` had grown to handle 15+ distinct operations. Splitting improves discoverability, reduces per-action import cost, and aligns with the principle that each action should have a clear, bounded responsibility.

**Migration**: All workflow YAMLs and pipeline scripts updated to reference new action names.
