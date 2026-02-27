# `batch_expand_abbreviations` Command

Batch expand abbreviations to discover full instrument phrases.

## Overview

The `batch_expand_abbreviations` action discovers extended instrument phrases by iterating over abbreviations from instrument mining output. For each abbreviation, it:

1. Subsets CDEs containing that abbreviation
2. Mines phrases from the focused subset
3. Reports the most frequent phrases (likely the full instrument name)

This bootstrapping approach discovers mappings like:
- `PROMIS` → "Patient-Reported Outcome Measure Information System"
- `PHQ` → "Patient Health Questionnaire"
- `SF-36` → "36-Item Short Form Health Survey"

## Usage

```bash
cde-analyzer batch_expand_abbreviations \
    -i <input.json> \
    --abbreviations <instruments.tsv> \
    -o <output_dir>
```

## Options

### Required

| Option | Description |
|--------|-------------|
| `-i, --input` | Input CDE JSON file to search for extended phrases |
| `--abbreviations` | TSV file with abbreviations (from `instrument_miner`) |

### Output

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output-dir` | `abbreviation_expansions` | Output directory for results |

### Column Selection

| Option | Default | Description |
|--------|---------|-------------|
| `--acronym-column` | `acronym` | Column name containing abbreviations |
| `--fields` | `designation definition` | Fields to search for abbreviations |

### Phrase Mining Parameters

| Option | Default | Description |
|--------|---------|-------------|
| `--k-max` | `15` | Maximum k-mer length for phrase mining |
| `--k-min` | `3` | Minimum k-mer length for phrase mining |
| `--min-tinyids` | `2` | Minimum distinct tinyIds for phrase to be reported |
| `--top-phrases` | `10` | Number of top phrases to report per abbreviation |

### Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--min-subset-size` | `3` | Minimum CDEs in subset to run phrase mining |
| `--skip-abbreviations` | - | Abbreviations to skip (e.g., common false positives) |

## Output Files

The action produces two TSV files in the output directory:

### expanded_phrases.tsv

One row per discovered phrase, sorted by frequency:

| Column | Description |
|--------|-------------|
| `abbreviation` | Source abbreviation |
| `expanded_phrase` | Discovered phrase text |
| `frequency` | How many times this phrase appears |
| `n_tinyids` | Distinct document count |
| `tinyids` | Pipe-separated document IDs (first 10) |

### expansion_summary.tsv

One row per abbreviation processed:

| Column | Description |
|--------|-------------|
| `abbreviation` | The abbreviation |
| `subset_size` | Number of CDEs containing this abbreviation |
| `status` | `success`, `skipped_too_small`, `no_phrases`, or `mining_failed` |
| `top_phrase` | Most frequent phrase found (if successful) |
| `top_frequency` | Frequency of top phrase |

## Examples

### Basic Usage

```bash
# Run after instrument_miner
cde-analyzer batch_expand_abbreviations \
    -i cdes.json \
    --abbreviations phase1_output/instruments.tsv \
    -o phase1_output/abbreviation_expansions
```

### Custom Parameters

```bash
# More aggressive mining with longer phrases
cde-analyzer batch_expand_abbreviations \
    -i cdes.json \
    --abbreviations instruments.tsv \
    -o expansions/ \
    --k-max 20 \
    --top-phrases 20 \
    --min-subset-size 5
```

### Skip Problematic Abbreviations

```bash
# Skip common false positives
cde-analyzer batch_expand_abbreviations \
    -i cdes.json \
    --abbreviations instruments.tsv \
    -o expansions/ \
    --skip-abbreviations NA NR TBD
```

## Workflow Integration

This action is typically used in the `instrument_detection.yaml` workflow after initial instrument mining:

```yaml
steps:
  - name: mine_instruments
    action: instrument_miner
    args:
      input: "${input_json}"
      output_dir: "${output_dir}/"
      detect_families: true

  - name: expand_abbreviations
    action: batch_expand_abbreviations
    args:
      input: "${input_json}"
      abbreviations: "${instruments_tsv}"
      output_dir: "${expansions_dir}"
```

The output `expanded_phrases.tsv` can then be passed to `strip_discover` as an additional pattern source:

```yaml
  - name: discover_verbatim
    action: strip_discover
    args:
      pattern_list: "${instruments_verbatim},full_match,tinyids"
      additional_patterns:
        - "${expanded_phrases},expanded_phrase"
```

## Algorithm

For each abbreviation:

1. **Subset**: Filter CDEs where any designation or definition contains the abbreviation (case-insensitive)

2. **Mine**: Run `phrase_miner` on the subset with subsumption enabled
   - Uses the same k-mer descent algorithm as standalone phrase mining
   - Focuses on phrases appearing in multiple documents

3. **Rank**: Sort discovered phrases by frequency
   - High-frequency phrases in a focused subset are likely the full instrument name

4. **Report**: Output top N phrases per abbreviation

## Performance

- Processes abbreviations sequentially (no parallelization)
- Skips abbreviations with fewer than `--min-subset-size` matches
- Typical runtime: 1-5 seconds per abbreviation depending on subset size

## Related Commands

- [instrument_miner](instrument_miner.md) — Initial instrument extraction
- [subset](subset.md) — Text-based CDE filtering (used internally)
- [phrase_miner](phrase_miner.md) — Phrase mining algorithm
- [strip_discover](strip_discover.md) — Pattern discovery for stripping
