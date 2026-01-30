# `discovery_report` Command

Generate markdown pipeline summary reports with per-step metrics, remnant analysis, and version tracking.

## Overview

The `discovery_report` command scans a pipeline output directory and generates a structured markdown report summarizing all steps: row counts, tinyId coverage, subsumption statistics, remnant analysis, and version history.

Supports both instrument detection and phrase stripping pipelines.

## Usage

```bash
cde-analyzer discovery_report \
    --output-dir PIPELINE_DIR/ \
    --pipeline {instrument,phrase} \
    -o REPORT.md \
    [--version LABEL] [--input-json FILE]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `-d, --output-dir` | yes | Pipeline output directory to scan for step outputs |
| `-p, --pipeline` | yes | Pipeline type: `instrument` or `phrase` |
| `-o, --output` | yes | Path to markdown report output |
| `--version` | no | Version label for iteration tracking (e.g., `iter-01`) |
| `-i, --input-json` | no | Original input JSON (for input record count) |

## Report Contents

### Summary Table

Per-step row counts and tinyId coverage for each output file found in the pipeline directory.

### Pipeline Steps

Status, row counts, and tinyId coverage for each expected output file. Steps with missing files are marked as skipped.

### Subsumption Summary

Action type counts from coalesce reports (e.g., prefix extraction, anchor trimming, subsumed patterns).

### Remnant Analysis

If remnant report TSVs are found (`remnants.tsv`, `remnants_naive.tsv`, `remnants_smart.tsv`), the report includes:

- Per-type remnant counts
- Comparison table when multiple reports exist (e.g., naive vs smart strip)
- Total remnant count

### Sanity Check Survivors (instrument pipeline only)

Top remaining patterns from `sanity_check.tsv`, showing patterns that survived stripping.

### Version History

Accumulated across iterations, showing pattern count and tinyId progression over time.

## Step Definitions

The report knows which files to scan per pipeline type:

**Instrument pipeline**: `instruments.tsv` → `instruments_verbatim.tsv` → `expanded_phrases.tsv` → `abbrev_patterns.tsv` → `discovered_instruments.tsv` → `coalesced_instruments.tsv` → `curated_instruments.tsv` → `final_discovered.tsv` → `final_coalesced.tsv` → `final_coalesced_short.tsv` → `tier1_stripped.json` → `no_instruments.json` → `sanity_check.tsv`

**Phrase pipeline**: `verbatim_phrases.tsv` → `discovered.tsv` → `coalesced.tsv` → `coalesce_report.tsv` → `coalesced_fields.tsv` → `curated.tsv` → `final_stripped.json` → `strip_trace.tsv`

## Examples

### Instrument Pipeline Report

```bash
cde-analyzer discovery_report \
    --output-dir phase1_output/ \
    --pipeline instrument \
    -o phase1_output/discovery_report.md \
    --version iter-01 \
    --input-json cdes.json
```

### Phrase Pipeline Report

```bash
cde-analyzer discovery_report \
    --output-dir scheuermann09/ \
    --pipeline phrase \
    -o scheuermann09/discovery_report.md \
    --input-json cdes.json
```

## Related Commands

- [strip_phrases](strip_phrases.md) — Apply stripping (produces remnant reports)
- [pattern_util](pattern_util.md) — TSV utilities (produces coalesce reports)
- [strip_discover](strip_discover.md) — Pattern discovery
