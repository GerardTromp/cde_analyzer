# `strip_phrases` Command

Remove curated phrases from specific paths in CDE JSON documents.

## Overview

The `strip_phrases` command processes CDE data and removes or replaces specified phrases at designated paths within the JSON structure. This is essential for cleaning CDE text fields before embedding or clustering operations, where certain repeated phrases (e.g., boilerplate text, standardized prefixes) may interfere with semantic analysis.

Supports two input modes:
1. **Discovered patterns** (`--patterns`): TSV from `strip_discover` with `pattern`, `tinyIds` columns
2. **Legacy phrase map** (`--phrases`): JSON/CSV/TSV with `path`, `phrase`, `replace`, `tinyIds` columns

## Usage

```bash
cde-analyzer strip_phrases -i INPUT -m MODEL -o OUTPUT \
    {--patterns FILE | --phrases FILE} [OPTIONS]
```

## Required Arguments

| Argument | Description |
|----------|-------------|
| `-i, --input` | Path to input JSON file containing CDE records |
| `-m, --model` | Pydantic model name (e.g., `CDE`, `Form`) |
| `-o, --output` | Path to output JSON file |
| `--patterns FILE` | Discovered patterns TSV (from `strip_discover` or curated merge) |
| `--phrases FILE` | Legacy phrase map file (JSON, CSV, or TSV) — mutually exclusive with `--patterns` |

### Patterns File Format

The `--patterns` argument accepts flexible column specification:

- `file.tsv` — uses `pattern` column (default)
- `file.tsv,column_name` — custom pattern column
- `file.tsv,pattern_col,tinyids_col` — both custom columns

Column matching is case-insensitive. Excel-quoted fields are automatically unquoted.

## Optional Arguments

### Processing Options

| Argument | Description |
|----------|-------------|
| `-f, --fields` | Field paths to strip phrases from (default: `definitions.*.definition designations.*.designation`) |
| `--sort-order` | Pattern processing order: `length` (longest-first, default), `file` (preserve TSV order), `alpha` (alphabetical) |
| `-w, --workers` | Parallel workers: `0` = auto-detect, `1` = sequential (default), `N` = exactly N workers |
| `--word-boundary`, `-B` | Use `\b` regex word boundary anchors for pattern matching. Prevents partial-word matches: `"in the past"` will NOT match inside `"within the past"`. Composable with `--ignore-case` |
| `--ignore-case`, `-I` | Case-insensitive pattern matching via `re.IGNORECASE`. Composable with `--word-boundary` |

### Remnant Detection and Cleanup

| Argument | Description |
|----------|-------------|
| `--detect-remnants` | After stripping, scan output for post-strip artifacts (orphan articles, floating punctuation, excess whitespace, etc.) |
| `--remnant-report FILE` | Write detailed remnant report TSV to FILE. Implies `--detect-remnants` |
| `--clean-remnants` | After stripping, apply iterative cleanup to fix post-strip artifacts. Modifies the output JSON before writing |

The `--clean-remnants` flag applies iterative regex-based normalization to remove:

- Orphan articles (`the`, `a`, `an`) before punctuation or at string boundaries
- Floating punctuation (`, ` `;` `:` `-` surrounded by spaces)
- Leading/trailing punctuation artifacts
- Orphan prepositions (`of`, `for`, `in`, etc.) at boundaries
- Dangling possessives (`'s`)
- Empty parentheses/brackets
- Double punctuation and excess whitespace

Cleanup runs in a loop until the text stabilizes (up to 5 passes). In testing on 22,743 CDEs, this reduced 7,652 remnants to 6 (99.9% reduction).

### Pattern Matching Options

| Argument | Description |
|----------|-------------|
| `--expand-anchors` | Expand patterns with anchor prefixes (e.g., "as part of the X"). Enables cleaner stripping by matching longer context (default: on) |
| `--no-expand-anchors` | Disable anchor prefix expansion. Use bare patterns only |
| `--verbatim-patterns` | Merge patterns from `config/verbatim_strip_patterns.yaml` and local override. Pre-curated patterns that escape discovery logic (default: on) |
| `--no-verbatim-patterns` | Disable loading verbatim patterns from config files |

### Diagnostics

| Argument | Description |
|----------|-------------|
| `--trace-matching`, `-T` FILE | Write detailed matching trace TSV (tinyId, pattern length, pattern text per match) |
| `--match-log` FILE | Write detailed match log TSV (tinyId, matched_pattern, source_pattern, verbatim_text). Full audit trail of what was stripped and where |
| `--match-summary` FILE | Write pattern match summary TSV (source_pattern, match_count, unique_records). Aggregated counts per pattern |

### Diff Output

| Argument | Description |
|----------|-------------|
| `-d, --diff` | Show diff between original and cleaned JSON |
| `--diff-output FILE` | Write diff information to a file |
| `-c, --color` | Colorize diff output |
| `--summary` | Show summary of changed lines |
| `-C, --context N` | Number of context lines before/after changes (default: 3) |

## Path Syntax

Paths use dot notation with wildcard support:

- `designations.*.designation` — All designation fields
- `definitions[0].definition` — First definition only
- `valueDomain.permissibleValues.*.permissibleValue` — Nested arrays

## Examples

### Basic Usage

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json -m CDE \
    -p curated_patterns.tsv \
    -o cdes_cleaned.json
```

### With Remnant Cleanup and Report

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json -m CDE \
    -p patterns.tsv \
    -o cdes_cleaned.json \
    --clean-remnants \
    --detect-remnants --remnant-report remnants.tsv
```

### With Diff and Trace

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json -m CDE \
    -p patterns.tsv \
    -o cdes_cleaned.json \
    --diff --color --summary \
    --trace-matching trace.tsv
```

### Custom Fields and Sort Order

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json -m CDE \
    -p patterns.tsv \
    -o cdes_cleaned.json \
    --fields designations.*.designation \
    --sort-order file
```

## Workflow Integration

This command is typically used after pattern curation:

1. **Mine phrases** using `phrase_miner`
2. **Discover patterns** using `strip_discover` with variant expansion
3. **Coalesce patterns** using `pattern_util --coalesce-variants`
4. **Filter patterns** using `pattern_util --field-analysis`
5. **Strip phrases** using this command with `--clean-remnants`
6. **Verify output** with `--detect-remnants` and `discovery_report`

## Output

The command produces:

- **Output JSON**: Cleaned CDE records in the same format as input
- **Diff output** (optional): Shows all modifications made
- **Remnant report** (optional): TSV listing post-strip artifacts with type, location, and snippet
- **Trace log** (optional): TSV showing every pattern match

## Notes

- Phrase matching is exact (verbatim) by default. Use `--word-boundary` for regex word-boundary matching or `--ignore-case` for case-insensitive matching
- Multiple spaces are normalized after phrase removal
- When `--clean-remnants` is used, cleanup runs after stripping but before writing
- When both `--clean-remnants` and `--detect-remnants` are used, remnant detection runs after cleanup (measuring residual artifacts)
- The command validates output against the Pydantic model to ensure schema compliance

## Word Boundary Matching (v0.5.x)

The `--word-boundary` flag adds `\b` regex word boundary anchors to prevent partial-word matches during stripping. Without word boundaries, the pattern `"in the past"` matches inside `"within the past week"`, leaving the artifact `"with week"`. With `--word-boundary`, the anchors require word boundaries at both ends.

Both `--word-boundary` and `--ignore-case` can be active simultaneously. The recommended workflow is to pre-expand patterns with `pattern_util --expand-verbatim` (which handles case variants explicitly), then strip with `--word-boundary` for precision.

See [Extensions v0.5.x](../appendix/extensions_v0.5.x.md#10-word-boundary-matching-strip_phrases---word-boundary--v053) for full implementation details.

## Related Commands

- [strip_discover](strip_discover.md) — Pattern discovery
- [strip_analyze](strip_analyze.md) — Conflict and false-negative analysis
- [pattern_util](pattern_util.md) — TSV utilities (merge, coalesce, field analysis)
- [diagnose_strip](diagnose_strip.md) — Diagnose remaining patterns after stripping
