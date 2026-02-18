# `pattern_util` Command

TSV pattern utilities (merge, coalesce, field analysis, import).

## Overview

The `pattern_util` command provides TSV manipulation utilities for pattern files. Most operations work on TSV files only — no CDE JSON input required (except `--field-analysis`).

## Usage

```bash
# Merge duplicate patterns
cde-analyzer pattern_util --merge-patterns FILE -o OUTPUT.tsv

# Coalesce patterns (remove subsumed)
cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT.tsv \
    [--coalesce-report REPORT.tsv] [--min-prefix-tinyids N] \
    [--min-parent-tinyids N] [--rollup-subset-tinyids] \
    [--emit-def-variants] [--split-tiers MIN_TOKENS]

# Field analysis (enrich with per-field counts)
cde-analyzer pattern_util --field-analysis FILE \
    -i SOURCE.json -m CDE -o ENRICHED.tsv \
    [--min-field-count N] [--min-tokens N] [--exclude-patterns FILE]

# Group hierarchy
cde-analyzer pattern_util --group-hierarchy FILE -o GROUPED.tsv \
    [--min-tinyids N] [--min-tinyids-scale F]

# Semantic grouping
cde-analyzer pattern_util --group-semantic FILE -o GROUPED.tsv \
    [--min-group-size N] [--min-prefix-words N]

# Expand curated patterns with variants
cde-analyzer pattern_util --expand-verbatim FILE -o EXPANDED.tsv \
    [--no-temporal-variants] [--no-case-variants] \
    [--no-number-variants] [--no-plural-variants] \
    [--rescan -i SOURCE.json -m CDE]

# Import patterns to supplementary config
cde-analyzer pattern_util --add-to-supplementary CURATED.tsv
```

## Modes

### Merge Mode

Combine duplicate pattern rows, merging their tinyId sets:

```bash
cde-analyzer pattern_util --merge-patterns discovered.tsv -o merged.tsv
```

Useful after removing sub-instrument details when multiple patterns become identical.

### Coalesce Mode

Remove patterns subsumed by longer patterns (tinyId-aware):

```bash
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --coalesce-report subsumption.tsv
```

A pattern is subsumed if:
1. It's a substring of longer pattern(s)
2. Its tinyIds are covered by the union of those longer patterns' tinyIds

**Anchor trimming** (default ON): Patterns containing anchor phrases (`as part of`, `based on`, etc.) are trimmed to the bare instrument name. Disable with `--no-trim-anchors`.

**Prefix extraction**: Groups patterns by common prefix and replaces them with the shortest prefix meeting the tinyId threshold.

```bash
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --min-prefix-tinyids 3
```

Example: "as part of Neuro-QOL Lower..." and "as part of Neuro-QOL Upper..." become "as part of Neuro-QOL" if it covers enough tinyIds.

**TinyId-subset rollup**: Removes short patterns whose tinyIds are a strict subset of a longer pattern's, even without text substring relation. Requires substring match to prevent unrelated subsumption.

**Definition-form variants**: Emits additional patterns without trailing separators (` -`, ` - `) for definition field matching.

**Tier splitting**: Splits output into tier-1 (≥N tokens) and tier-2 (<N tokens) for two-pass stripping.

### Field Analysis Mode

Enrich a patterns TSV with per-field tinyId counts by scanning source JSON:

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

### Group Hierarchy Mode

Assign `group`, `sub_group`, `suffix` labels based on shared prefix:

```bash
cde-analyzer pattern_util --group-hierarchy coalesced.tsv \
    -o grouped.tsv --min-tinyids 3
```

### Semantic Grouping Mode

Group patterns by shared prefix spans with SpaCy POS-based boundary trimming:

```bash
cde-analyzer pattern_util --group-semantic coalesced.tsv \
    -o grouped.tsv --min-group-size 2 --min-prefix-words 2
```

### Generate Strip Patterns

Produce strip-ready pattern files from a group-hierarchy TSV:

```bash
cde-analyzer pattern_util --generate-strip-patterns grouped.tsv -o strip_patterns
```

Produces `{output}_full.tsv` (full removal) and `{output}_sub.tsv` (group prefix removed, suffix retained).

### Normalize Mode

Convert any pattern TSV to minimal 2-column format for merging:

```bash
cde-analyzer pattern_util --to-minimal discovered.tsv -o minimal.tsv
```

Auto-detects column names (`pattern`/`tinyIds`/`tinyids`) and normalizes tinyId separator to pipe (`|`). Useful for combining files from different pipeline stages that may have different column structures.

### Expand Verbatim Mode

Expand curated patterns with temporal preposition, case, number, and plural variants for precise verbatim matching:

```bash
cde-analyzer pattern_util --expand-verbatim curated.tsv -o expanded.tsv
```

Generates narrow variants of each curated pattern:
- **Temporal**: preposition × tense-word variants (`In the past` → also `During the past`, `Over the last`, etc.)
- **Case**: original + all-lowercase (`In the past` → also `in the past`)
- **Number**: digit ↔ word (`7 days` ↔ `seven days`)
- **Plural**: temporal singular ↔ plural (`day` ↔ `days`, `week` ↔ `weeks`)

Optionally re-scan source JSON to discover actual tinyIds per variant:

```bash
cde-analyzer pattern_util --expand-verbatim curated.tsv \
    -i source.json -m CDE --rescan -o expanded.tsv
```

Without `--rescan`, variants inherit the source pattern's tinyIds. With `--rescan`, each variant is searched in the JSON and variants with no matches are dropped.

Output includes `source_pattern` column for tracing back to the curated pattern.

### Supplementary Import Mode

Add curated patterns to `config/supplementary_patterns.yaml`:

```bash
cde-analyzer pattern_util --add-to-supplementary curated.tsv
```

The TSV must have `pattern` and `name` (or `suggested_name`) columns. Only rows with `include` column set to `yes` are imported. The input file is deleted after successful import.

## Options

### Merge Options

| Option | Description |
|--------|-------------|
| `--merge-patterns`, `-M` FILE | Deduplicate patterns within a single TSV file, merging tinyId sets for identical patterns |
| `-o, --output FILE` | Output merged TSV file (required) |
| `--merge-pattern-column` | Column name for patterns (default: `pattern`) |
| `--merge-tinyids-column` | Column name for tinyIds (default: `tinyIds`) |

**Note**: To merge multiple files, first normalize with `--to-minimal`, concatenate, then merge. See [Merge Multiple Pattern Files](#merge-multiple-pattern-files) example.

### Coalesce Options

| Option | Description |
|--------|-------------|
| `--coalesce-variants`, `-c` FILE | Input TSV file for subsumption analysis |
| `-o, --output FILE` | Output coalesced TSV file (required) |
| `--coalesce-report FILE` | Write subsumption report showing removed patterns |
| `--min-prefix-tinyids N` | Enable prefix extraction (0 = disabled) |
| `--min-parent-tinyids N` | Filter by parent phrase tinyId count (0 = disabled) |
| `--no-trim-anchors` | Disable anchor phrase trimming |
| `--rollup-subset-tinyids` | Enable tinyId-subset rollup |
| `--emit-def-variants` | Emit definition-form variants (without trailing separator) |
| `--split-tiers MIN_TOKENS` | Split output into tier-1/tier-2 by token count (0 = disabled) |

### Field Analysis Options

| Option | Description |
|--------|-------------|
| `--field-analysis`, `-A` FILE | Input patterns TSV to enrich |
| `-i, --input FILE` | Source CDE JSON for scanning (required) |
| `-m, --model NAME` | Pydantic model name (default: `CDE`) |
| `--fields PATHS` | Field paths to scan (default: `definitions.*.definition designations.*.designation`) |
| `--min-field-count N` | Drop patterns below N in both fields (0 = disabled) |
| `--min-tokens N` | Drop patterns with fewer than N tokens (0 = disabled) |
| `--exclude-patterns FILE` | Remove patterns matching entries in exclusion file |

### Group Options

| Option | Description |
|--------|-------------|
| `--group-hierarchy FILE` | Assign group/sub_group labels by shared prefix |
| `--min-tinyids N` | Drop patterns with fewer than N tinyIds (0 = disabled) |
| `--min-tinyids-scale F` | Adaptive tinyId threshold scale factor (0.0 = disabled) |
| `--generate-strip-patterns FILE` | Generate strip-ready files from group-hierarchy TSV |
| `--group-semantic FILE` | Semantic grouping with POS-based boundary trimming |
| `--min-group-size N` | Minimum patterns per group (default: 2) |
| `--min-prefix-words N` | Minimum words in shared prefix (default: 2) |
| `--no-temporal-implied` | Disable implied-ONE temporal variant generation |

### Expand Verbatim Options

| Option | Description |
|--------|-------------|
| `--expand-verbatim`, `-e` FILE | Input curated patterns TSV to expand with variants |
| `-o, --output FILE` | Output expanded TSV file (required) |
| `--no-case-variants` | Skip case variant generation (original + lowercase) |
| `--no-number-variants` | Skip digit ↔ word variants (`7` ↔ `seven`) |
| `--no-plural-variants` | Skip singular ↔ plural variants (`day` ↔ `days`) |
| `--no-temporal-variants` | Skip temporal preposition variants (in/over/during/for/within × past/last) |
| `--rescan` | Re-scan source JSON for tinyIds per variant (requires `-i` and `-m`) |

### Normalize Options

| Option | Description |
|--------|-------------|
| `--to-minimal FILE` | Normalize TSV to 2-column format (pattern, tinyIds) for merging |
| `-o, --output FILE` | Output normalized TSV file (required) |

### Import Options

| Option | Description |
|--------|-------------|
| `--add-to-supplementary FILE` | Curated TSV to import |
| `--supplementary-section` | YAML section name (default: `added_patterns`) |

## Examples

### Full Pipeline Example

```bash
# 1. Start with discovered patterns
cde-analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv \
    --pattern-list instruments.tsv --expand-variants

# 2. Coalesce with prefix extraction and parent filtering
cde-analyzer pattern_util --coalesce-variants discovered.tsv -o coalesced.tsv \
    --coalesce-report subsumption.tsv --min-prefix-tinyids 3 --min-parent-tinyids 20

# 3. Enrich with field analysis and filter
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i cdes.json -m CDE -o coalesced_fields.tsv \
    --min-field-count 6 --min-tokens 3

# 4. Strip with cleanup
cde-analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json \
    --patterns coalesced_fields.tsv --clean-remnants \
    --detect-remnants --remnant-report remnants.tsv
```

### Merge Multiple Pattern Files

To combine patterns from multiple sources (e.g., `coalesced.tsv` and `abbrev_patterns.tsv`):

```bash
# 1. Normalize each file to minimal 2-column format
#    (handles column name variations, normalizes tinyId separator to pipe)
cde-analyzer pattern_util --to-minimal coalesced.tsv -o coalesced_min.tsv
cde-analyzer pattern_util --to-minimal abbrev_patterns.tsv -o abbrev_min.tsv

# 2. Concatenate files (skip header on subsequent files)
head -1 coalesced_min.tsv > combined.tsv
tail -n +2 coalesced_min.tsv >> combined.tsv
tail -n +2 abbrev_min.tsv >> combined.tsv

# 3. Merge duplicate patterns (combines tinyId sets for identical patterns)
cde-analyzer pattern_util --merge-patterns combined.tsv -o merged.tsv

# 4. Clean up intermediate files
rm coalesced_min.tsv abbrev_min.tsv combined.tsv
```

**Note**: `--merge-patterns` operates on a single file, deduplicating rows with identical patterns and merging their tinyId sets. Use the normalize-concatenate-merge workflow above to combine multiple source files.

### Import Supplementary Patterns

After false-negative analysis:

```bash
# 1. Review false_negatives.tsv and set 'include' to 'yes' for patterns to add
# 2. Import to supplementary config
cde-analyzer pattern_util --add-to-supplementary false_negatives.tsv

# 3. Re-run phrase_miner to pick up new patterns
cde-analyzer phrase_miner -i cdes.json -o output/ --extract-supplementary
```

## Additional Capabilities (v0.5.x)

Several enhancements were added in the v0.5.x series:

- **Anchor Trimming** (default on in `--coalesce-variants`): Patterns containing anchor phrases ("as part of", "based on") are trimmed to the bare instrument name. Disable with `--no-trim-anchors`.
- **Rollup-Subset TinyIds** (`--rollup-subset-tinyids`): After text-based subsumption, removes short patterns whose tinyIds are a strict subset of a longer pattern's tinyIds.
- **Definition-Form Variants** (`--emit-def-variants`): Emits patterns both with and without trailing separators (` -`, ` - `) so that definitions are stripped alongside designations.
- **Tier Splitting** (`--split-tiers MIN_TOKENS`): Splits coalesced output into tier-1 (>=MIN_TOKENS) and tier-2 (<MIN_TOKENS) for two-pass stripping.
- **Group Hierarchy** (`--group-hierarchy`): Assigns `group`, `sub_group`, `suffix` labels based on shared prefix.
- **Verbatim Variant Expansion** (`--expand-verbatim`): Expands curated patterns with temporal/case/number/plural variants. Pipeline order: temporal -> plural -> number -> case. With `--rescan`, only variants that exist in the source data survive.

See [Extensions v0.5.x](../appendix/extensions_v0.5.x.md#2-pattern_util-enhancements) for full implementation details.

## Related Commands

- [strip_discover](strip_discover.md) — Pattern discovery
- [strip_analyze](strip_analyze.md) — Conflict and false-negative analysis
- [strip_phrases](strip_phrases.md) — Apply stripping with remnant cleanup
- [discovery_report](discovery_report.md) — Generate pipeline summary reports
