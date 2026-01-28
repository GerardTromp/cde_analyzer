# `instrument_miner` Command

Extract measurement instruments from CDE text fields using anchor-based pattern detection.

## Overview

The `instrument_miner` action detects instrument patterns from "as part of \<Instrument\>" phrases in CDE text. It provides dedicated instrument extraction with family grouping capabilities, separated from general phrase mining.

## Usage

```bash
cde-analyzer instrument_miner -i cdes.json -o output/ [options]
```

## Options

### Required

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input JSON file (list of CDE items) |

### Output

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir`, `-o` | `instrument_output` | Output directory for results |

### Field Selection

| Option | Default | Description |
|--------|---------|-------------|
| `--fields`, `-f` | `designation definition` | Field names to extract instruments from |

### Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--min-tinyids` | `2` | Minimum distinct tinyIds (document support) |
| `--min-instrument-words` | `3` | Minimum words required in instrument name |

### Extraction Modes

| Option | Description |
|--------|-------------|
| `--extract-abbreviation-only` | Extract abbreviation-only references like "as part of (PHQ-9)". Maps to canonical names using first-pass acronyms. |
| `--extract-supplementary` | Extract non-Title-Case instruments (animal models, behavioral tests). Uses patterns from `config/supplementary_patterns.yaml`. |

### Family Detection

| Option | Default | Description |
|--------|---------|-------------|
| `--detect-families` | off | Enable instrument family detection (groups by family, e.g., Neuro-QOL, PROMIS) |
| `--family-confidence-threshold` | `0.7` | Minimum confidence for automatic family assignment. Below threshold, instruments are flagged for review. |
| `--family-summary` | off | Generate `instrument_families.tsv` summary file |

## Output Files

| File | Description |
|------|-------------|
| `instruments.tsv` | All detected instruments with family assignments |
| `instruments_verbatim.tsv` | Verbatim surface forms for each instrument |
| `instrument_families.tsv` | Summary grouped by family (with `--family-summary`) |

## Examples

### Basic Extraction

```bash
cde-analyzer instrument_miner \
    -i cdes.json \
    -o output/
```

### Full Extraction with Family Detection

```bash
cde-analyzer instrument_miner \
    -i cdes.json \
    -o output/ \
    --extract-abbreviation-only \
    --extract-supplementary \
    --detect-families \
    --family-summary
```

### Custom Fields

```bash
cde-analyzer instrument_miner \
    -i cdes.json \
    -o output/ \
    --fields designation definition valueDomain.permissibleValues.*.permissibleValue
```

## Family Detection

When `--detect-families` is enabled, instruments are grouped into known families:

- **Neuro-QOL**: Neuro-QOL Ability to Participate in Social Roles and Activities, etc.
- **PROMIS**: PROMIS Anxiety Short Form 8a, etc.
- **MDS-UPDRS**: Movement Disorder Society-UPDRS, etc.
- **SF Health Surveys**: SF-12, SF-36, etc.
- **Beck Inventories**: Beck Depression Inventory, etc.
- **PHQ Series**: PHQ-9, PHQ-2, etc.

Instruments with `family_confidence < threshold` are flagged for manual review or LLM adjudication.

## Workflow Integration

This command is Phase 1 in the [Instrument & Phrase Stripping Workflow](../workflows/instrument-phrase-stripping-workflow.md):

```
instrument_miner → strip_discover → strip_phrases → phrase_miner → ...
```

## Related Commands

- [phrase_miner](phrase_miner.md) - General phrase mining (non-instrument)
- [strip_discover](strip_discover.md) - Pattern discovery for stripping
- [llm_classify](../llm/llm_classify.md) - LLM-based family adjudication
