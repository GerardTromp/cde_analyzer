# `diagnose_strip` Command

Diagnose remaining anchor patterns after stripping for iterative improvement.

## Overview

The `diagnose_strip` action analyzes cleaned JSON files to find patterns that weren't fully stripped. It searches for configurable anchor phrases (like "as part of") and reports what remains, helping identify gaps in the stripping pipeline.

## Usage

```bash
cde_analyzer diagnose_strip -i cleaned.json -m CDE -o remaining.tsv [options]
```

## Options

### Required

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input JSON file (cleaned output from strip_phrases) |
| `--model`, `-m` | Pydantic model: `CDE`, `Form`, `Embed`, `EmbedText` |
| `--output`, `-o` | Output TSV file with remaining patterns and frequencies |

### Field Selection

| Option | Default | Description |
|--------|---------|-------------|
| `--fields`, `-f` | `definitions.*.definition designations.*.designation` | Field paths to search for remaining patterns |

### Comparison

| Option | Description |
|--------|-------------|
| `--original` | Original JSON file (before stripping) for comparison metrics |

### Anchor Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--anchors` | `as part of`, `as a part of`, `based on`, `field of` | Anchor phrases to search for |
| `--context-chars` | `100` | Characters of context to capture after anchor |

### Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--min-count` | `1` | Minimum occurrence count to include in output |

### Output Options

| Option | Description |
|--------|-------------|
| `--suggest-patterns` | Output suggested patterns for `config/supplementary_patterns.yaml` |

## Output Format

The output TSV contains:

| Column | Description |
|--------|-------------|
| `anchor` | The anchor phrase found |
| `pattern` | Extracted pattern after anchor |
| `count` | Number of occurrences |
| `tinyIds` | Document IDs where pattern appears |
| `context` | Sample context showing the pattern in use |

## Examples

### Basic Diagnosis

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv
```

### With Original Comparison

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv \
    --original original.json
```

### Custom Anchors

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv \
    --anchors "as part of" "derived from" "component of"
```

### Generate Pattern Suggestions

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv \
    --suggest-patterns
```

### Filter Low-Frequency Patterns

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv \
    --min-count 3
```

## Workflow Integration

Use `diagnose_strip` at the end of the stripping workflow to identify gaps:

```bash
# 1. Extract instruments
cde_analyzer instrument_miner -i cdes.json -o instruments/

# 2. Discover patterns
cde_analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list instruments/instruments_verbatim.tsv

# 3. Strip patterns
cde_analyzer strip_phrases \
    -i cdes.json -m CDE \
    -o cleaned.json \
    --patterns discovered.tsv

# 4. Diagnose what remains
cde_analyzer diagnose_strip \
    -i cleaned.json \
    -m CDE \
    -o remaining.tsv \
    --original cdes.json \
    --suggest-patterns
```

## Iterative Improvement

After diagnosis, patterns can be added to the supplementary config:

1. Review `remaining.tsv` output
2. Identify legitimate instrument patterns missed
3. Add to `config/supplementary_patterns.yaml`:

```yaml
added_patterns:
  - pattern: "Montreal Cognitive Assessment"
    name: "Montreal Cognitive Assessment"
    acronym: "MoCA"
```

4. Re-run `instrument_miner` with `--extract-supplementary`
5. Repeat stripping workflow

## Use Cases

### Quality Assurance

Verify stripping completeness:

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json -m CDE \
    -o qa_report.tsv \
    --min-count 1

# Check if any "as part of" patterns remain
wc -l qa_report.tsv
```

### Coverage Metrics

Compare before and after:

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json -m CDE \
    -o remaining.tsv \
    --original original.json

# Output includes comparison metrics
```

### Pattern Discovery

Find new instrument patterns not in the original list:

```bash
cde_analyzer diagnose_strip \
    -i cleaned.json -m CDE \
    -o candidates.tsv \
    --suggest-patterns \
    --min-count 2
```

## Related Commands

- [strip_discover](strip_discover.md) - Pattern discovery phase
- [strip_phrases](../help/strip_phrases.md) - Pattern stripping phase
- [instrument_miner](instrument_miner.md) - Extract instrument patterns
