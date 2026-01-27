# `strip_discover` Command

Flexible regex discovery for finding verbatim pattern occurrences in CDE text fields.

## Overview

The `strip_discover` action is the **discovery phase** of the two-phase stripping workflow:

1. **strip_discover**: Uses flexible regex to find verbatim text variations
2. **strip_phrases**: Uses exact string replacement for precision

This separation allows human curation between discovery and stripping.

## Usage

```bash
cde_analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv --pattern-list patterns.tsv [options]
```

## Modes

### Discovery Mode (Default)

Find verbatim occurrences of patterns in CDE text:

```bash
cde_analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments.tsv,full_match
```

### Conflict Analysis Mode

Detect pattern containment conflicts before stripping:

```bash
cde_analyzer strip_discover \
    --pattern-list patterns.tsv \
    --analyze-conflicts conflicts.tsv
```

### False-Negative Analysis Mode

Find remaining anchor patterns after stripping:

```bash
cde_analyzer strip_discover \
    -i cleaned.json \
    -o false_negatives.tsv \
    --analyze-false-negatives
```

### Merge Mode

Deduplicate patterns with merged tinyId sets:

```bash
cde_analyzer strip_discover \
    --merge-patterns curated.tsv \
    -o merged.tsv
```

### Import Mode

Add patterns to supplementary config:

```bash
cde_analyzer strip_discover \
    --add-to-supplementary curated.tsv
```

## Options

### Input/Output

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input JSON file (CDE records) |
| `--model`, `-m` | Pydantic model: `CDE`, `Form`, `Embed`, `EmbedText` |
| `--output`, `-o` | Output TSV file |
| `--pattern-list`, `-p` | TSV file with patterns. Format: `filename`, `filename,column`, or `filename,pattern_col,tinyids_col` |
| `--additional-patterns` | Additional TSV files to merge with pattern list |

### Field Selection

| Option | Default | Description |
|--------|---------|-------------|
| `--fields`, `-f` | `definitions.*.definition designations.*.designation` | Field paths to search |

### Variant Expansion

| Option | Description |
|--------|-------------|
| `--expand-variants` | Generate spelling/punctuation variants (spacing, punctuation, possessives) |
| `--include-name-only` | Include bare instrument names without "as part of" prefix (default: on) |
| `--no-include-name-only` | Disable bare name inclusion |
| `--discover-bare-names` | Second pass: discover bare names after prefixed patterns |

### Filtering

| Option | Description |
|--------|-------------|
| `--use-expected-tinyids` | Only search patterns in their expected tinyIds |

### Performance

| Option | Default | Description |
|--------|---------|-------------|
| `--workers`, `-w` | `1` | Parallel workers. `0` = auto-detect with headroom |

### Diagnostics

| Option | Description |
|--------|-------------|
| `--discover-fails FILE` | Write failed patterns to TSV for diagnosis |
| `--analyze-conflicts FILE` | Detect containment conflicts, output recommendations |
| `--sort-order` | Pattern order for conflict analysis: `length`, `file`, `alpha` |

### False-Negative Analysis

| Option | Default | Description |
|--------|---------|-------------|
| `--analyze-false-negatives` | off | Analyze remaining anchor patterns in cleaned JSON |
| `--fn-anchor` | `as part of` | Anchor phrase to search for |

### Supplementary Import

| Option | Default | Description |
|--------|---------|-------------|
| `--add-to-supplementary` | | Import curated TSV to `supplementary_patterns.yaml` |
| `--supplementary-section` | `added_patterns` | YAML section name for imports |

### Merge Mode

| Option | Default | Description |
|--------|---------|-------------|
| `--merge-patterns` | | TSV file to deduplicate |
| `--merge-pattern-column` | `pattern` | Column name for patterns |
| `--merge-tinyids-column` | `tinyIds` | Column name for tinyIds |

## Output Format

The output TSV contains:

| Column | Description |
|--------|-------------|
| `pattern` | Verbatim text found in CDE |
| `tinyIds` | Pipe-separated list of document IDs |
| `type` | Pattern type (e.g., `instrument`, `phrase`) |
| `source_pattern` | Original pattern that generated this match |

## Examples

### Basic Discovery

```bash
cde_analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments_verbatim.tsv,full_match
```

### With Variant Expansion

```bash
cde_analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments_verbatim.tsv,full_match \
    --expand-variants \
    --discover-bare-names
```

### Parallel Processing

```bash
cde_analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list patterns.tsv \
    --workers 0
```

### Analyze Conflicts Before Stripping

```bash
cde_analyzer strip_discover \
    --pattern-list discovered.tsv \
    --analyze-conflicts conflicts.tsv

# Review conflicts.tsv, then strip
cde_analyzer strip_phrases \
    -i cdes.json -m CDE \
    -o cleaned.json \
    --patterns discovered.tsv
```

### Iterative False-Negative Reduction

```bash
# 1. Analyze what's left after stripping
cde_analyzer strip_discover \
    -i cleaned.json \
    -o false_negatives.tsv \
    --analyze-false-negatives

# 2. Review and curate false_negatives.tsv
# Set 'include' column to 'yes' for patterns to add

# 3. Import to supplementary patterns
cde_analyzer strip_discover \
    --add-to-supplementary false_negatives_curated.tsv

# 4. Re-run instrument_miner with --extract-supplementary
```

## Workflow Integration

Part of the [Instrument & Phrase Stripping Workflow](../workflows/instrument-phrase-stripping-workflow.md):

```
instrument_miner → strip_discover → [curator review] → strip_phrases
```

## Related Commands

- [strip_phrases](../help/strip_phrases.md) - Apply exact string replacement
- [diagnose_strip](diagnose_strip.md) - Diagnose remaining patterns
- [instrument_miner](instrument_miner.md) - Extract instrument patterns
