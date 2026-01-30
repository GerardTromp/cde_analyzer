# Code Extensions Documentation — v0.5.x (phrase-curator branch)

This document describes all code extensions added during the v0.5.0–v0.5.1 development cycle on the `phrase-curator` branch.

---

## 1. New Action: `discovery_report`

**Files**: `actions/discovery_report/{__init__,cli,run}.py`

Generates markdown summary reports for pipeline execution. Supports both instrument detection and phrase stripping pipelines.

### CLI

```bash
cde-analyzer discovery_report \
    --output-dir phase1_output/ \
    --pipeline instrument \
    -o phase1_output/discovery_report.md \
    --version iter-01 \
    --input-json cdes.json
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--output-dir, -d` | yes | Pipeline output directory to scan |
| `--pipeline, -p` | yes | `instrument` or `phrase` |
| `-o, --output` | yes | Markdown report output path |
| `--version` | no | Version label for iteration tracking |
| `--input-json, -i` | no | Original input JSON (for record count) |

### Report Contents

- **Summary table**: per-step row counts, tinyId coverage
- **Pipeline steps table**: status, rows, tinyIds per output file
- **Subsumption summary**: action type counts from coalesce reports
- **Sanity check survivors** (instrument only): top 10 remaining patterns
- **Version history**: accumulated across iterations, shows pattern/tinyId progression

### Step Definitions

The report knows which files to scan per pipeline type:

- **Instrument**: instruments.tsv → instruments_verbatim.tsv → expanded_phrases.tsv → abbrev_patterns.tsv → discovered_instruments.tsv → coalesced_instruments.tsv → curated_instruments.tsv → final_discovered.tsv → final_coalesced.tsv → final_coalesced_short.tsv → tier1_stripped.json → no_instruments.json → sanity_check.tsv
- **Phrase**: verbatim_phrases.tsv → discovered.tsv → coalesced.tsv → coalesce_report.tsv → coalesced_fields.tsv → curated.tsv → final_stripped.json → strip_trace.tsv

---

## 2. `pattern_util` Enhancements

**Files**: `actions/pattern_util/{cli,run}.py`

### 2.1 Field Analysis (`--field-analysis`)

Enriches a patterns TSV with per-field tinyId counts by scanning source JSON.

```bash
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i source.json -m CDE \
    -o coalesced_fields.tsv \
    --min-field-count 6 --min-tokens 3 \
    --exclude-patterns exclusions.tsv
```

**New columns added**: `definition_count`, `designation_count`, `field_profile` (one of: `def-only`, `desig-only`, `both-all`, `mixed`)

**Filters applied**:
- `--min-field-count N`: drop patterns below N in ALL fields
- `--min-tokens N`: drop patterns with fewer than N whitespace-delimited tokens
- `--exclude-patterns FILE`: remove patterns matching entries in exclusion file

### 2.2 Anchor Trimming (default ON in `--coalesce-variants`)

Patterns containing anchor phrases (`as part of`, `based on`, etc.) are trimmed to the bare instrument name. The anchor prefix and any preceding CDE-specific text are removed, tinyIds merged.

- Disable with `--no-trim-anchors`
- Two-path extraction: prefix-only (`extract_bare_instrument_name()`) then mid-pattern regex

### 2.3 Rollup-Subset TinyIds (`--rollup-subset-tinyids`)

After text-based subsumption, removes short patterns whose tinyIds are a strict subset of a longer pattern's tinyIds, even when the short pattern is not a text substring. Only rolls up patterns shorter (by word count) than their covering pattern.

### 2.4 Definition-Form Variants (`--emit-def-variants`)

For each pattern ending with ` -` or ` - ` (designation separator), emits an additional pattern without the trailing separator. Definitions contain instrument names without the trailing separator (e.g., `Scale (CES-D).` vs `Scale (CES-D) - question`).

### 2.5 Tier Splitting (`--split-tiers MIN_TOKENS`)

Splits coalesced output into two files by token count:
- **Tier-1** (≥MIN_TOKENS tokens): written to `--output`
- **Tier-2** (<MIN_TOKENS tokens): written to `{output_base}_short.tsv`

Enables two-pass stripping: long instrument patterns first, then short fragments.

### 2.6 Group Hierarchy (`--group-hierarchy`)

Assigns `group`, `sub_group`, `suffix` labels to patterns based on shared prefix. Strips trailing delimiters from group names.

```bash
cde-analyzer pattern_util --group-hierarchy coalesced.tsv \
    -o grouped.tsv --min-tinyids 3
```

---

## 3. `strip_discover` Enhancements

**Files**: `actions/strip_discover/{cli,run}.py`

### 3.1 Field Distribution Functions

Two new functions exposed for reuse by `pattern_util --field-analysis`:

- `compute_field_distribution(parsed_models, verbatim_map, field_paths)` — computes per-field tinyId sets for each pattern by scanning parsed CDE models
- `_field_profile(field_dist)` — classifies distribution as `def-only`, `desig-only`, `both-all`, or `mixed`

### 3.2 Minimum Bare-Name Words (`--min-bare-words`)

Filters out short bare instrument names during `--discover-bare-names`. Default: 2 words. Prevents fragments like "Score" from producing false positives.

### 3.3 Abbreviation Pattern Discovery (`--discover-abbreviations`)

Discovers designation patterns based on known abbreviations:
- `(ABBREV) - ...` separator patterns
- `[ABBREV]` bracketed patterns
- Open `(ANYABBREV) -` scan for unknown abbreviations

---

## 4. `flexible_pattern_matcher` Enhancements

**File**: `utils/flexible_pattern_matcher.py`

### 4.1 Roll-Down Minimum 2-Word Check

The roll-down logic (which expands prefix patterns to more specific forms) now requires a minimum 2-word base. Prevents over-aggressive roll-down that creates single-word false positives.

### 4.2 Rollup-Subset Substring Match

The tinyId-subset rollup now requires the short pattern to be a substring of the covering pattern. Prevents unrelated patterns from being incorrectly subsumed just because their tinyIds overlap.

### 4.3 `coalesce_variants_tsv()` New Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rollup_subset_tinyids` | bool | False | Enable tinyId-subset rollup |
| `trim_anchors` | bool | True | Enable anchor phrase trimming |
| `emit_def_variants` | bool | False | Emit definition-form variants |

---

## 5. Two-Pass Stripping in Instrument Pipeline

**File**: `workflows/instrument_detection.yaml`

The instrument detection workflow now strips in two passes:
1. **Tier-1** (`strip_tier1`): Long instrument patterns (≥3 tokens) stripped first
2. **Tier-2** (`strip_tier2`): Short fragments (<3 tokens) stripped from tier-1 output

This prevents short fragment patterns (e.g., "Scale") from damaging instrument names that would have been matched by longer tier-1 patterns.

Related workflow variables: `final_coalesced_short`, `tier1_stripped_json`, `tier1_trace_tsv`.

---

## 6. `instrument_family_assigner` Enhancements

**File**: `logic/instrument_family_assigner.py`

Extended family detection with improved matching logic for instrument pattern grouping.

---

## 7. Workflow Changes

### `instrument_detection.yaml`

- Added `--emit-def-variants` and `--split-tiers 3` to `final_coalesce` step
- Added `--rollup-subset-tinyids` to both coalesce steps
- Added two-pass stripping (tier-1 then tier-2)
- Added `discovery_report` step after sanity check
- Added recall analysis steps (optional, conditional on `recall_patterns`)

### `phrase_pipeline.yaml`

- Added `discovery_report` step after strip
- Added recall analysis steps (before and after strip)
- Added `parent_column` and `min_parent_tinyids` variables
- Added field analysis filters: `min_field_count`, `min_tokens`, `exclude_patterns`

---

## 8. New Logic Modules (untracked)

### `logic/group_hierarchy.py`

Group/sub-group hierarchy assignment using prefix-based grouping with delimiter stripping.

### `logic/span_boundary.py`

SpaCy-based semantic boundary detection for prefix group trimming. Uses POS tagging to prevent overshooting into content-bearing tokens. Supports temporal frame detection and classification.
