# CDE Analyzer

Project aims to parse and analyze Common Data Elements (CDEs) hosted by the National Library of Medicine at the National Institutes of Health (https://cde.nlm.nih.gov/home).

**API**: Well-documented RESTful API at https://cde.nlm.nih.gov/api describing data structure.

**Data Model**: The CDE repository data structure has been implemented as a set of Pydantic models.

## Primary Principles

### Code Organization
- **All functions broken down to effect lazy loading**
  - Action directories contain:
    - `cli.py` - Argument parser (launcher)
    - `run.py` - Called by launcher, orchestrates action
  - `logic/` - Algorithm implementations (business logic)
  - `utils/` - Lightweight functions and utility tools

- **Data Models**: Pydantic classes in `CDE_Schema/` directory
  - `CDE_Item.py` - Individual data elements (CDEItem model)
  - `CDE_Form.py` - Form structures (CDEForm model)
  - `classes.py` - Shared classes (50+ supporting models)

- **Core Engine**: `core/recursor.py` - Recursive descent visitor pattern for nested structures

### Architecture
- **Layered monolithic** with plugin-style action system
- **Lazy loading** - Actions loaded only when invoked (fast startup)
- **Visitor pattern** - Single recursive engine handles all nested traversal
- **Three-layer actions**: CLI → Orchestration → Logic separation

## Current Status

**Version**: 1.6.1 (2026-06-24) — dependency-metadata correctness: requires-python raised to >=3.10 (forced by cde-lib), constraint floors/caps rationalized + documented. (1.6.0: CDE Pydantic schema relocated to cde_lib.schema, ADR-E004; CDE_Schema/ a re-export shim, cde-lib a required dep.)

**Recent Work**:
- **v1.0.0**: Config-driven pipeline scaffold, action refactoring, reference ledger, Production/Stable
- **v0.9.8**: Field-aware splits, 7-way branching strip, group-scoped re-matching
- **v0.9.5**: Containment tree in TSV editor
- **v0.9.4**: Deferred parent filter, anchor trim control, followup decision
- **v0.9.2**: N-way single-pass branching strip engine
- **v0.8.0**: Incremental curation with ledger and gate
- **v0.7.0**: Standalone editor zipapp, centralized curation server
- **v0.6.0**: Multi-curator workflow, workflow scaffold, vignettes

## Actions (CLI Commands)

### Pipeline Actions
| Action | Purpose |
|--------|---------|
| `phrase_miner` | K-mer phrase mining with iterative descent |
| `strip_discover` | Pattern discovery in CDE text fields |
| `strip_phrases` | Pattern stripping (longest-first replacement) |
| `strip_branching` | N-way branching strip (single-pass, all 7 variants) |
| `strip_report` | Quality report for stripped outputs |
| `diagnose_strip` | Diagnose remaining patterns after stripping |
| `strip_analyze` | Pattern conflict and false-negative analysis |

### Pattern & Curation Actions
| Action | Purpose |
|--------|---------|
| `pattern_util` | Pattern TSV utilities (coalesce, merge, field analysis, validate, temporal, split-priority) |
| `curation` | Curation lifecycle (edit, gate, finalize, init/merge multi-curator, serve centralized) |
| `instrument_util` | Instrument utilities (group-hierarchy, generate-strip-patterns, analyze-splits) |
| `supplementary` | Supplementary pattern management (harvest-residuals, update-ledger, promote) |
| `pattern_diag` | Pattern diagnostics (curation-status) |

### Orchestration & Utility Actions
| Action | Purpose |
|--------|---------|
| `workflow` | YAML-based pipeline orchestrator with checkpoints, scaffold, configure |
| `llm_classify` | Multi-LLM phrase classification with confidence aggregation |
| `extract_embed` | Extract fields for transformer model embedding |
| `subset` | Extract CDE subsets (literal/regex/tinyID filters) |
| `count` | Count structural elements and field occurrences |
| `fix_underscores` | Fix Pydantic-incompatible field names |
| `strip_html` | Remove HTML markup from CDE fields |

**Usage**: `cde-analyzer <action> [arguments]`
**Help**: `cde-analyzer <action> --help` for action-specific options

## Pipeline

### Phase 1: Instrument Pipeline (`instrument_pipeline.yaml`)
mine_instruments → discover_abbreviations → discover_verbatim → coalesce →
validate_subsumption → enrich_fields → curation_gate → [CURATOR] →
finalize_curation → apply_substitutions → strip_instruments → sanity_check

### Phase 2: Phrase Pipeline (`phrase_pipeline.yaml`)
mine_phrases → discover_verbatim → coalesce → field_analysis → curation_gate →
[CURATOR] → finalize_curation → apply_substitutions → strip_phrases → discovery_report

### Phase 3: Branching Strip (`branching_strip_nway.yaml`)
expand_temporal → strip_branching (7 variants) → quality_report

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

## Data & Reference Assets

- `data/reference_ledger/` — Official curation ledger (allcde03: 458 instrument + 4,023 phrase decisions)
  - Copy to `.curation_ledger/` to bootstrap incremental curation for new projects
  - `MANIFEST.yaml` — provenance, checksums (MD5+SHA1), decision counts
- `examples/pipeline_config.yaml` — Example YAML config for `workflow scaffold --from-config`
- `config/temporal_seed_patterns.yaml` — 25 temporal seed patterns (~2,100 expanded variants)
- `config/verbatim_strip_patterns.yaml` — Verbatim patterns auto-merged into inst_full stage

## Python Environment (WSL)

```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```

## Key Technical Notes

### Data Model Characteristics
- **Self-referential nesting** - Models can contain nested instances of themselves
- **All fields Optional** - Handles sparse API responses
- **Field aliases** - Maps MongoDB/API names to Python-safe names (e.g., `_id` → `id`)

### Recursive Processing
All nested data traversal uses `core/recursor.py`:
```python
recursive_descent(item, path, visitor, context, depth)
```

## Quick Reference

**Entry Point**: `cde_analyzer.py` (or `cde-analyzer` executable)
**Core Engine**: `core/recursor.py` — recursive descent visitor
**Data Models**: `CDE_Schema/` — Pydantic models mirroring NLM CDE API
**Actions**: `actions/` — each action has `cli.py` + `run.py`
**Logic**: `logic/` — core processing algorithms
**Utilities**: `utils/` — helper functions
**Workflows**: `workflows/` — YAML pipeline definitions
**Tests**: `tests/` — unit tests
**Docs**: `docs/help/` (28 command refs), `docs/vignettes/` (8 guides)
