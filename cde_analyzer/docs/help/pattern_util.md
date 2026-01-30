# pattern_util

TSV pattern utilities (merge, coalesce, field analysis, import).

## Synopsis

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

# Import patterns to supplementary config
cde-analyzer pattern_util --add-to-supplementary CURATED.tsv
```

## Description

The `pattern_util` command provides TSV manipulation utilities for pattern files. Most operations work on TSV files only — no CDE JSON input required (except `--field-analysis`).

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
| `--merge-patterns FILE` | Input TSV file with duplicate patterns |
| `-o, --output FILE` | Output merged TSV file (required) |
| `--merge-pattern-column` | Column name for patterns (default: `pattern`) |
| `--merge-tinyids-column` | Column name for tinyIds (default: `tinyIds`) |

### Coalesce Options

| Option | Description |
|--------|-------------|
| `--coalesce-variants FILE` | Input TSV file for subsumption analysis |
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
| `--field-analysis FILE` | Input patterns TSV to enrich |
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

### Import Supplementary Patterns

After false-negative analysis:

```bash
# 1. Review false_negatives.tsv and set 'include' to 'yes' for patterns to add
# 2. Import to supplementary config
cde-analyzer pattern_util --add-to-supplementary false_negatives.tsv

# 3. Re-run phrase_miner to pick up new patterns
cde-analyzer phrase_miner -i cdes.json -o output/ --extract-supplementary
```

## Related Commands

- [strip_discover](strip_discover.md) — Pattern discovery
- [strip_analyze](strip_analyze.md) — Conflict and false-negative analysis
- [strip_phrases](strip_phrases.md) — Apply stripping with remnant cleanup
- [discovery_report](discovery_report.md) — Generate pipeline summary reports
