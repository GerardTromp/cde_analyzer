# `phrase_grouper` Command

Bottom-up k-mer analysis for discovering phrase families that share common patterns.

## Overview

The `phrase_grouper` action analyzes phrases to identify families based on shared prefixes, suffixes, or internal patterns (infixes). It uses three independent tree-building strategies:

1. **Prefix tree (trie)**: Groups phrases by shared beginnings
2. **Suffix tree (reversed trie)**: Groups phrases by shared endings
3. **Infix index (inverted index)**: Groups phrases by shared internal k-mers

## Usage

```bash
cde-analyzer phrase_grouper -i verbatim_phrases.tsv -o phrase_families/ [options]
```

## Options

### Required

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input TSV file (typically `verbatim_phrases.tsv` from phrase_miner) |

### Output

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir`, `-o` | `phrase_families` | Output directory for results |

### Column Mapping

| Option | Default | Description |
|--------|---------|-------------|
| `--text-column` | `verbatim_text` | Column name containing phrase text |
| `--id-column` | `phrase_id` | Column name for phrase identifier |
| `--tinyid-column` | `tinyids` | Column name for document IDs |

### K-mer Parameters

| Option | Default | Description |
|--------|---------|-------------|
| `--k-min`, `-k` | `3` | Minimum k-mer length in tokens |
| `--k-max`, `-K` | `10` | Maximum k-mer length in tokens |
| `--min-content-words` | `1` | Minimum non-stopword tokens required in pattern. Filters patterns like "of the" that are entirely stopwords. |

### Family Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--min-family-size`, `-n` | `3` | Minimum phrases to form a family |
| `--min-pattern-freq` | `3` | Minimum frequency for pattern to be considered |

### Tree Selection

| Option | Default | Description |
|--------|---------|-------------|
| `--trees` | `prefix suffix infix` | Which trees to build (any combination) |

### Assignment Strategy

| Option | Default | Description |
|--------|---------|-------------|
| `--assignment` | `frequency` | How to assign phrases when multiple patterns match: `frequency` (highest pattern frequency wins), `longest` (longest matching pattern wins), `all` (report all matches) |

### Performance

| Option | Description |
|--------|-------------|
| `--parallel` | Build trees in parallel (uses multiprocessing) |
| `--lowercase` | Normalize phrases to lowercase before analysis |

## Output Files

| File | Description |
|------|-------------|
| `families.tsv` | All discovered families with patterns and member counts |
| `phrase_assignments.tsv` | Each phrase with its best-fit family assignment |
| `family_members.tsv` | Detailed listing of phrases in each family |

## Examples

### Basic Usage

```bash
cde-analyzer phrase_grouper \
    -i phrase_output/verbatim_phrases.tsv \
    -o phrase_families/
```

### Custom K-mer Range

```bash
cde-analyzer phrase_grouper \
    -i verbatim_phrases.tsv \
    -o families/ \
    --k-min 3 \
    --k-max 15
```

### Prefix-Only Analysis

```bash
cde-analyzer phrase_grouper \
    -i verbatim_phrases.tsv \
    -o prefix_families/ \
    --trees prefix \
    --min-family-size 5
```

### Filter Low-Content Patterns

```bash
cde-analyzer phrase_grouper \
    -i verbatim_phrases.tsv \
    -o families/ \
    --min-content-words 2
```

## How It Works

### Stopword Filtering

Patterns consisting entirely of stopwords (e.g., "of the", "in a") are filtered out based on `--min-content-words`. Common English stopwords include:

- Articles: a, an, the
- Prepositions: of, to, in, on, at, by, for, with, from
- Conjunctions: and, or, but
- Pronouns: it, this, that, which, who

### Subsumption Filtering

Longer patterns that contain all members of shorter patterns "subsume" them. The algorithm keeps maximal (longest) patterns to reduce redundancy.

### Assignment Confidence

When a phrase matches multiple family patterns, confidence is calculated as the ratio of the best match's frequency to total frequencies across all matches.

## Use Cases

### Identify Temporal Phrase Families

Phrases like "In the past 7 days..." often share common prefixes:

```
Prefix family: "In the past 7 days"
  - "In the past 7 days, how often..."
  - "In the past 7 days, have you..."
  - "In the past 7 days, I have..."
```

### Find Response Scale Patterns

Phrases may share common suffixes (rating scales):

```
Suffix family: "strongly agree"
  - "I strongly agree"
  - "Somewhat strongly agree"
  - "Very strongly agree"
```

## Workflow Integration

Use after `phrase_miner` to analyze discovered phrases:

```bash
# 1. Mine phrases
cde-analyzer phrase_miner -i cdes.json -o phrase_output/

# 2. Group into families
cde-analyzer phrase_grouper \
    -i phrase_output/verbatim_phrases.tsv \
    -o phrase_families/
```

## Related Commands

- [phrase_miner](phrase_miner.md) - Extract repeated phrases
- [instrument_miner](instrument_miner.md) - Extract measurement instruments
