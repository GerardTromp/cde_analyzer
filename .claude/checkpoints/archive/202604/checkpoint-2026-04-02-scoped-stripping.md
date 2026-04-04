# Checkpoint: tinyId-Scoped Verbatim Stripping

**Date**: 2026-04-02
**Package Version**: 1.0.1 (unchanged)
**Branch**: main
**Parent Checkpoint**: checkpoint-2026-04-02-v101-consolidated.md

---

## Summary

Implemented tinyId-scoped stripping as a first-class feature throughout the pipeline.
Bare instrument abbreviation tags (UPPS-P, BFI, CAST, etc.) are now stripped only
within their instrument's CDE set, eliminating false-positive risk while recovering
536 CDEs worth of instrument tag leakage.

## What Changed

### Config Loader (`utils/config_loader.py`)
- `_parse_tinyid_field()`: New helper — parses comma/space/pipe-delimited tinyId strings
- `_extract_verbatim_patterns_from_config()`: Returns 3-tuple `(pattern, replace_with, tinyIds)` instead of 2-tuple
- `_auto_propagate_bare_patterns()`: New — generates bare `TAG` from bracketed `[TAG]` with same tinyId scope
- `load_verbatim_strip_patterns()`: Returns 3-tuple with tinyIds; runs auto-propagation after loading

### Consumers Updated
- `actions/strip_phrases/run.py`: `load_verbatim_strip_patterns()` wrapper passes through tinyIds
- `actions/strip_branching/run.py`: Unpacks 3-tuple, passes tinyIds into phrase_map

### Abbreviation Dictionary (`logic/abbreviation_dictionary.py`)
- `export_scoped_verbatim_yaml()`: New method — generates YAML with tinyIds for pipeline integration

### Abbreviation Action (`actions/abbreviation/`)
- `cli.py`: New `--export-scoped-yaml` subcommand
- `run.py`: Handler + pipeline mode auto-exports scoped YAML

### Verbatim Config (`config/verbatim_strip_patterns.yaml`)
- 106 scoped patterns now have `tinyIds` field with corpus-derived tinyId sets
- 16 universal patterns (temporal, boilerplate) unchanged
- 5 zero-hit patterns without tinyIds (no matches in corpus)

### Tests (`tests/test_config_loader_scoped.py`)
- 23 new tests: _parse_tinyid_field (9), _extract_verbatim (6), _auto_propagate (8)
- All pass; 360/361 existing tests pass (1 pre-existing failure in verbatim_coalesce)

## Validation

MTSTPT strip comparison (scoped vs baseline):
- 22,743 CDEs: 22,207 identical, 536 more-stripped
- 3,196 chars removed, 0 chars added, 0 regressions
- Top stripped tags: LTVH (65), UPPS-P (57), BFI (44), CAST (43), MIDUS II (24)
- All removals within tinyId scope — zero false positives

## Design Decisions

1. **Backwards compatible**: YAML entries without `tinyIds` remain universal (None)
2. **Auto-propagation**: `[TAG]` with tinyIds generates bare `TAG` with same scope; universal bare patterns never downgraded
3. **No engine changes**: Both phrase_stripper and branching_stripper already had tinyId support
4. **Scope is semantic, tinyIds are corpus-dependent**: U/S decisions are durable; tinyId sets need refreshing on new corpus

## Files Modified

| File | Change |
|------|--------|
| `utils/config_loader.py` | Core 3-tuple return type + auto-propagation |
| `actions/strip_phrases/run.py` | Pass through tinyIds from config |
| `actions/strip_branching/run.py` | Unpack 3-tuple with tinyIds |
| `logic/abbreviation_dictionary.py` | New `export_scoped_verbatim_yaml()` |
| `actions/abbreviation/cli.py` | New `--export-scoped-yaml` |
| `actions/abbreviation/run.py` | Handler + pipeline integration |
| `config/verbatim_strip_patterns.yaml` | 106 entries with tinyIds |
| `tests/test_config_loader_scoped.py` | 23 new tests |
