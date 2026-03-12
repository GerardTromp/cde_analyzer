# Information Loss Estimation

> **Purpose**: Quantify how much text (total words, content words) is removed by
> each stripping variant so we can assess the trade-off between noise reduction
> and potential information loss.

## Methodology

The analysis script `scripts/branching_loss_analysis.py` extracts text from two
CDE fields — `definitions.*.definition` and `designations.*.designation` — across
the original (unstripped) JSON and each of the 5 branching-strip outputs.

### Metrics

| Metric | Definition |
|---|---|
| **Total words** | All `\b\w+\b` tokens in the field |
| **Content words** | Total words minus English stopwords (55 function words, determiners, prepositions — same set as `logic/phrase_grouper.py:STOPWORDS`) |
| **Stopwords** | Total − Content |
| **Empty records** | CDEs with zero words in the field |

### Per-record loss distribution

For each CDE, content word loss = `(original_content − stripped_content) / original_content`.
Percentiles (P25, median, P75, P90, P95) reveal the distribution shape — a heavy
right tail means a minority of CDEs are predominantly formulaic.

## Branching Strip Variants

| Code | What is removed |
|---|---|
| `MTSFPF` | Main instrument names fully removed |
| `MFSTPF` | Sub-group instrument prefix removed, suffix retained |
| `MFSFPT` | Curated phrase patterns removed, no instrument stripping |
| `MTSFPT` | Full instrument removal + phrase removal |
| `MFSTPT` | Sub-group instrument removal + phrase removal |

## Usage

```bash
python scripts/branching_loss_analysis.py \
    --original /path/to/cdes_subset.json \
    --branch-dir /path/to/branching_output \
    [-o /path/to/results.txt]
```

Output: 4 formatted tables (word counts, per-field loss, aggregate loss,
per-record distribution).

## Interpretation Guide

- **Content word loss %** is the primary metric. Stopword loss is a side effect.
- **Median = 0%** means most CDEs are untouched by that stripping variant.
  The action concentrates on a subset of CDEs that use formulaic text.
- **P90–P95 tail** identifies CDEs that are mostly boilerplate. These benefit
  most from stripping but also carry the highest risk of over-removal.
- **inst_full vs inst_sub gap** measures how much sub-group suffixes contribute.
  A small gap suggests most instruments don't have meaningful sub-group structure.
- **both_full < inst_full + phrase_only** indicates overlap — CDEs hit by both
  instrument and phrase patterns. The non-additivity measures this overlap.

## Relationship to Slides

The same analysis approach was used to produce the tables in:
- `docs/slides/phrase_stripping_summary.html` — corpus-level word counts
- `docs/slides/phrase_stripping_pipeline.html` — cumulative stage-by-stage loss

Those slides used a different (larger) dataset and a 2-stage pipeline (instruments
then phrases). The branching analysis extends this to 6 parallel variants on the
same input.
