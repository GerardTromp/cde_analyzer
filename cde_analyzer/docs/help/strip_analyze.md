# strip_analyze

Analyze patterns for conflicts and false negatives.

## Synopsis

```bash
# Conflict analysis
cde-analyzer strip_analyze --analyze-conflicts REPORT.tsv \
    --pattern-list patterns.tsv [--sort-order length|file|alpha]

# False-negative analysis
cde-analyzer strip_analyze --analyze-false-negatives \
    -i cleaned.json -o false_negatives.tsv [--fn-anchor "as part of"]
```

## Description

The `strip_analyze` command provides analysis utilities for the pattern stripping workflow:

- **Conflict Analysis**: Detect pattern containment relationships that affect stripping order
- **False-Negative Analysis**: Find remaining anchor patterns after stripping

## Options

### Conflict Analysis Mode

| Option | Description |
|--------|-------------|
| `--analyze-conflicts FILE` | Output file for conflict report |
| `-p, --pattern-list FILE` | TSV file with patterns to analyze (required) |
| `--sort-order` | Pattern processing order: `length` (default), `file`, `alpha` |
| `--expand-variants` | Generate spelling/punctuation variants for analysis |
| `--include-name-only` | Include bare instrument names in variants (default: True) |

### False-Negative Analysis Mode

| Option | Description |
|--------|-------------|
| `--analyze-false-negatives` | Enable false-negative analysis mode |
| `-i, --input FILE` | Cleaned JSON file to analyze (required) |
| `-o, --output FILE` | Output TSV file for report (required) |
| `--fn-anchor STRING` | Anchor phrase to search for (default: "as part of") |

## Output Format

### Conflict Analysis Report

TSV with columns:
- `short_pattern`: The contained (shorter) pattern
- `long_pattern`: The containing (longer) pattern
- `relationship`: `prefix`, `suffix`, or `interior`
- `position`: Character position where short appears in long
- `is_conflict`: `YES` if actual ordering conflict, `no` otherwise
- `remainder`: What remains if short is stripped from long
- `recommendation`: Suggested action for curator

### False-Negative Analysis Report

TSV with columns:
- `count`: Number of occurrences
- `pattern`: Remaining pattern text
- `suggested_name`: Canonical name suggestion
- `acronym`: Extracted acronym if present
- `include`: Set to `yes` to include in supplementary patterns

## Examples

### Conflict Analysis

Analyze patterns for containment issues before stripping:

```bash
cde-analyzer strip_analyze --analyze-conflicts conflict_report.tsv \
    --pattern-list curated_instruments.tsv \
    --sort-order length
```

### False-Negative Analysis

Find remaining patterns after stripping:

```bash
cde-analyzer strip_analyze --analyze-false-negatives \
    -i cleaned_cdes.json \
    -o remaining_patterns.tsv \
    --fn-anchor "as part of"
```

## Workflow Integration

This command is typically used in the iterative pattern improvement workflow:

1. Run `strip_discover` to find patterns
2. Run `strip_phrases` to strip patterns
3. Run `strip_analyze --analyze-false-negatives` on output
4. Review report and mark patterns to add
5. Run `pattern_util --add-to-supplementary` with curated patterns
6. Repeat until false negatives are acceptable

## Related Commands

- [strip_discover](strip_discover.md) - Pattern discovery
- [pattern_util](pattern_util.md) - TSV utilities (merge, coalesce)
- [strip_phrases](strip_phrases.md) - Apply stripping
