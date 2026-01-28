# pattern_util

TSV pattern utilities (merge, coalesce, import).

## Synopsis

```bash
# Merge duplicate patterns
cde-analyzer pattern_util --merge-patterns FILE -o OUTPUT.tsv

# Coalesce patterns (remove subsumed)
cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT.tsv \
    [--coalesce-report REPORT.tsv] [--min-prefix-tinyids N]

# Import patterns to supplementary config
cde-analyzer pattern_util --add-to-supplementary CURATED.tsv
```

## Description

The `pattern_util` command provides TSV manipulation utilities for pattern files. These operations work on TSV files only - no CDE JSON input required.

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

### Prefix Extraction

Group patterns by common prefix during coalesce:

```bash
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --min-prefix-tinyids 3
```

Example: "as part of Neuro-QOL Lower..." and "as part of Neuro-QOL Upper..." become "as part of Neuro-QOL" if it covers enough tinyIds.

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
| `--coalesce-report FILE` | Optional report showing removed patterns |
| `--min-prefix-tinyids N` | Enable prefix extraction (0 = disabled) |

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

# 2. Merge duplicates (if patterns were edited)
cde-analyzer pattern_util --merge-patterns discovered.tsv -o merged.tsv

# 3. Coalesce with prefix extraction
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --coalesce-report subsumption.tsv --min-prefix-tinyids 3

# 4. Review coalesced.tsv, then strip
cde-analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json \
    --patterns coalesced.tsv
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

- [strip_discover](strip_discover.md) - Pattern discovery
- [strip_analyze](strip_analyze.md) - Conflict and false-negative analysis
- [strip_phrases](strip_phrases.md) - Apply stripping
