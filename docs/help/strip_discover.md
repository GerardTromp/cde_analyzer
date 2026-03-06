# `strip_discover` Command

Flexible regex discovery for finding verbatim pattern occurrences in CDE text fields.

## Overview

The `strip_discover` action is the **discovery phase** of the two-phase stripping workflow:

1. **strip_discover**: Uses flexible regex to find verbatim text variations
2. **strip_phrases**: Uses exact string replacement for precision

This separation allows human curation between discovery and stripping.

## Related Commands

Commands split from strip_discover in v0.4.2:

- [strip_analyze](strip_analyze.md) - Conflict analysis and false-negative detection
- [pattern_util](pattern_util.md) - TSV utilities (merge, coalesce, supplementary import)

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
| `--expand-variants`, `-e` | Generate spelling/punctuation variants (spacing, punctuation, possessives) |
| `--include-name-only` | Include bare instrument names without "as part of" prefix (default: on) |
| `--no-include-name-only` | Disable bare name inclusion |
| `--discover-bare-names`, `-b` | Second pass: discover bare names after prefixed patterns |

### Variant Matching

| Option | Description |
|--------|-------------|
| `--min-bare-words N` | Minimum word count for bare instrument names. Filters short fragments like "Score" during `--discover-bare-names` (default: 2) |
| `--allow-abbrev-variants` | Enable abbreviation variant matching. Patterns like `(PHQ)` will also match `(PHQ-9)`, `(PHQ-15)`, etc. |
| `--allow-embedded-abbrev` | Allow embedded abbreviation parentheticals between words. E.g., `Scale Long` matches `Scale (GDS) Long` |

### Filtering

| Option | Description |
|--------|-------------|
| `--use-expected-tinyids` | Only search patterns in their expected tinyIds |

### Performance

| Option | Default | Description |
|--------|---------|-------------|
| `--workers`, `-w` | `1` | Parallel workers. `0` = auto-detect with headroom |

### Parent Phrase Tracking

| Option | Description |
|--------|-------------|
| `--parent-column COLUMN` | Column in `--pattern-list` TSV containing the parent (generic) phrase. Adds `parent_phrase` and `parent_tinyid_count` columns to output. Used with `phrase_pipeline.yaml` to propagate generic phrase coverage through the pipeline. |

### Diagnostics

| Option | Description |
|--------|-------------|
| `--discover-fails FILE` | Write failed patterns to TSV for diagnosis |

### Abbreviation Discovery

| Option | Default | Description |
|--------|---------|-------------|
| `--discover-abbreviations`, `-a` | | Extract abbreviations from instruments.tsv and scan for designation patterns |
| `--min-pattern-tinyids` | `2` | Minimum tinyIds for abbreviation prefix patterns to be output |

## Output Format

The output TSV contains:

| Column | Description |
|--------|-------------|
| `pattern` | Verbatim text found in CDE |
| `tinyIds` | Space-separated list of document IDs |
| `type` | Pattern type: `prefix` or `bare` |
| `source_pattern` | Original pattern that generated this match |
| `parent_phrase` | *(optional)* Parent generic phrase (when `--parent-column` used) |
| `parent_tinyid_count` | *(optional)* Unique tinyIds across all verbatim variants of the parent |

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

### With Parent Phrase Tracking

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list verbatim_phrases.tsv,verbatim_text \
    --expand-variants \
    --parent-column lemma_text
```

Adds `parent_phrase` and `parent_tinyid_count` columns to discovered.tsv. The parent
tinyId count aggregates unique tinyIds across all verbatim variants sharing the same
generic (lemmatized) parent phrase. Used by downstream `--min-parent-tinyids` filtering
in `pattern_util` coalesce.

### Parallel Processing

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list patterns.tsv \
    --workers 0
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
instrument_miner → strip_discover → pattern_util (coalesce) → [curator review] → strip_phrases
```

### Full Pipeline Example

```bash
# 1. Discover patterns
cde-analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv \
    --pattern-list instruments.tsv --expand-variants

# 2. Coalesce patterns (use pattern_util)
cde-analyzer pattern_util --coalesce-variants discovered.tsv -o coalesced.tsv \
    --min-prefix-tinyids 3

# 3. Review coalesced.tsv, then strip
cde-analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json \
    --patterns coalesced.tsv

# 4. Analyze remaining patterns (use strip_analyze)
cde-analyzer strip_analyze --analyze-false-negatives \
    -i cleaned.json -o false_negatives.tsv
```

## Additional Capabilities (v0.5.x)

- **Field Distribution Functions**: `compute_field_distribution()` and `_field_profile()` compute per-field tinyId sets for each pattern, classifying distribution as `def-only`, `desig-only`, `both-all`, or `mixed`. Reused by `pattern_util --field-analysis`.
- **Minimum Bare-Name Words** (`--min-bare-words`): Filters short bare instrument names during `--discover-bare-names`. Default: 2 words. Prevents fragments like "Score" from producing false positives.
- **Abbreviation Pattern Discovery** (`--discover-abbreviations`): Discovers designation patterns based on known abbreviations: `(ABBREV) - ...` separator patterns, `[ABBREV]` bracketed patterns, and open `(ANYABBREV) -` scan.

See [Extensions v0.5.x](../appendix/extensions_v0.5.x.md#3-strip_discover-enhancements) for full implementation details.

## Related Commands

- [strip_analyze](strip_analyze.md) - Pattern conflict and false-negative analysis
- [pattern_util](pattern_util.md) - TSV utilities (merge, coalesce, import)
- [strip_phrases](../help/strip_phrases.md) - Apply exact string replacement
- [diagnose_strip](diagnose_strip.md) - Diagnose remaining patterns
- [instrument_miner](instrument_miner.md) - Extract instrument patterns
