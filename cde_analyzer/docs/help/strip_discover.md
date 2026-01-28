# `strip_discover` Command

Flexible regex discovery for finding verbatim pattern occurrences in CDE text fields.

## Overview

The `strip_discover` action is the **discovery phase** of the two-phase stripping workflow:

1. **strip_discover**: Uses flexible regex to find verbatim text variations
2. **strip_phrases**: Uses exact string replacement for precision

This separation allows human curation between discovery and stripping.

## Usage

```bash
cde-analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv --pattern-list patterns.tsv [options]
```

## Modes

### Discovery Mode (Default)

Find verbatim occurrences of patterns in CDE text:

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments.tsv,full_match
```

### Conflict Analysis Mode

Detect pattern containment conflicts before stripping:

```bash
cde-analyzer strip_discover \
    --pattern-list patterns.tsv \
    --analyze-conflicts conflicts.tsv
```

### False-Negative Analysis Mode

Find remaining anchor patterns after stripping:

```bash
cde-analyzer strip_discover \
    -i cleaned.json \
    -o false_negatives.tsv \
    --analyze-false-negatives
```

### Merge Mode

Deduplicate patterns with merged tinyId sets:

```bash
cde-analyzer strip_discover \
    --merge-patterns curated.tsv \
    -o merged.tsv
```

### Import Mode

Add patterns to supplementary config:

```bash
cde-analyzer strip_discover \
    --add-to-supplementary curated.tsv
```

### Coalesce Mode

Reduce pattern redundancy via subsumption analysis and prefix extraction:

```bash
cde-analyzer strip_discover \
    --coalesce-variants discovered.tsv \
    -o coalesced.tsv \
    --coalesce-report subsumption_report.tsv \
    --min-prefix-tinyids 5
```

**Coalesce performs two reduction phases**:

1. **Subsumption Analysis**: Removes patterns where one is a substring of another with overlapping tinyIds
2. **Prefix Extraction**: Groups patterns by common word prefix and replaces with shortest prefix meeting the tinyId threshold

### Abbreviation Discovery Mode

Find designation patterns using abbreviations from instruments.tsv:

```bash
cde-analyzer strip_discover \
    --discover-abbreviations instruments.tsv \
    -i cdes.json \
    -o abbrev_patterns.tsv \
    --min-pattern-tinyids 2
```

**Discovers two pattern types**:
- **Bracketed suffix**: `[PROMIS]`, `[NHANES]`
- **Hyphen prefix**: `PROMIS - Pain Interference`, `Neuro-QOL - Anxiety`

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

### Coalesce Mode

| Option | Default | Description |
|--------|---------|-------------|
| `--coalesce-variants` | | TSV file to coalesce (subsumption + prefix extraction) |
| `--coalesce-report` | | Write subsumption/prefix report showing removed patterns |
| `--min-prefix-tinyids` | `0` | Enable prefix extraction: groups patterns by common prefix and replaces with shortest prefix meeting this tinyId threshold. Default 0 = disabled. |

### Abbreviation Discovery

| Option | Default | Description |
|--------|---------|-------------|
| `--discover-abbreviations` | | Extract abbreviations from instruments.tsv and scan for designation patterns |
| `--min-pattern-tinyids` | `2` | Minimum tinyIds for abbreviation prefix patterns to be output |

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
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments_verbatim.tsv,full_match
```

### With Variant Expansion

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments_verbatim.tsv,full_match \
    --expand-variants \
    --discover-bare-names
```

### Parallel Processing

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list patterns.tsv \
    --workers 0
```

### Analyze Conflicts Before Stripping

```bash
cde-analyzer strip_discover \
    --pattern-list discovered.tsv \
    --analyze-conflicts conflicts.tsv

# Review conflicts.tsv, then strip
cde-analyzer strip_phrases \
    -i cdes.json -m CDE \
    -o cleaned.json \
    --patterns discovered.tsv
```

### Iterative False-Negative Reduction

```bash
# 1. Analyze what's left after stripping
cde-analyzer strip_discover \
    -i cleaned.json \
    -o false_negatives.tsv \
    --analyze-false-negatives

# 2. Review and curate false_negatives.tsv
# Set 'include' column to 'yes' for patterns to add

# 3. Import to supplementary patterns
cde-analyzer strip_discover \
    --add-to-supplementary false_negatives_curated.tsv

# 4. Re-run instrument_miner with --extract-supplementary
```

### Coalesce with Prefix Extraction

```bash
# Reduce 553 patterns to ~50 by extracting common prefixes
cde-analyzer strip_discover \
    --coalesce-variants discovered_instruments.tsv \
    -o coalesced_instruments.tsv \
    --coalesce-report subsumption_report.tsv \
    --min-prefix-tinyids 5
```

**How prefix extraction works**:

```
Input patterns (3 patterns, overlapping tinyIds):
  "as part of Neuro-QOL Lower Extremity Function" (15 tinyIds)
  "as part of Neuro-QOL Upper Extremity Function" (12 tinyIds)
  "as part of Neuro-QOL Anxiety" (8 tinyIds)

With --min-prefix-tinyids=5:
  Output: "as part of Neuro-QOL" (35 tinyIds, union of above)
```

### Abbreviation Pattern Discovery

```bash
# Find [PROMIS] and "PROMIS - ..." patterns
cde-analyzer strip_discover \
    --discover-abbreviations instruments.tsv \
    -i cdes.json \
    -o abbrev_patterns.tsv \
    --min-pattern-tinyids 2
```

Catches patterns that k-mer mining misses:
- `[PROMIS]` - bracketed suffix (often at end of designation)
- `PROMIS - Pain Interference` - hyphen prefix patterns

## Workflow Integration

Part of the [Instrument & Phrase Stripping Workflow](../workflows/instrument-phrase-stripping-workflow.md):

```
instrument_miner → strip_discover → [curator review] → strip_phrases
```

## Related Commands

- [strip_phrases](../help/strip_phrases.md) - Apply exact string replacement
- [diagnose_strip](diagnose_strip.md) - Diagnose remaining patterns
- [instrument_miner](instrument_miner.md) - Extract instrument patterns
