# `recall_analyze` Command

Analyze recall and detect false negatives in instrument detection by comparing source pattern matches against pipeline output.

## Overview

The `recall_analyze` command measures how well the detection pipeline captures ground-truth instrument patterns. It searches the source JSON for patterns, compares against pipeline output, and reports per-family recall metrics with false negative analysis.

Key features:

- **Ground truth comparison**: Search source data for regex patterns with family labels
- **Recall metrics**: Per-family and per-pattern recall percentages
- **Iteration tracking**: Compare against previous reports to measure marginal gains
- **Pattern suggestions**: Generate enhanced patterns for underperforming families
- **Markdown reports**: Human-readable summaries with version history

## Usage

```bash
cde-analyzer recall_analyze \
    -i SOURCE.json -m CDE \
    --pattern-file PATTERNS.txt \
    --pipeline-output PIPELINE.tsv \
    -o recall_report.tsv \
    [--markdown-report REPORT.md] \
    [--previous-report PREV.tsv]
```

## Arguments

### Input Files

| Argument | Required | Description |
|----------|----------|-------------|
| `-i, --input` | yes | Path to source CDE JSON (ground truth for pattern matching) |
| `-m, --model` | yes | Pydantic model for validation: `CDE`, `Form`, `EmbedText` |
| `-F, --pattern-file` | yes | File with patterns and labels. Format: `pattern<TAB>label` |
| `--pipeline-output` | no | Pipeline output TSV with tinyIds column. If omitted, reports source matches only |
| `--pipeline-tinyid-column` | no | Column name for tinyIds in pipeline output (default: `tinyIds`) |

### Output Files

| Argument | Required | Description |
|----------|----------|-------------|
| `-o, --output` | yes | Path to recall report TSV |
| `--false-negatives-file` | no | Output file listing false negative tinyIds grouped by family |
| `--markdown-report`, `-r` | no | Path to human-readable markdown report with summary and details |
| `--markdown-detail` | no | Standalone detailed report for this phase only |
| `--report-version` | no | Version label for iteration tracking (e.g., `v1`, `iter-02`) |
| `--report-title` | no | Title for markdown report (default: `Instrument Detection Recall Report`) |

### Search Options

| Argument | Default | Description |
|----------|---------|-------------|
| `-f, --fields` | `designation definition` | Fields to search for pattern matches |
| `--case-sensitive`, `-C` | false | Make pattern matching case-sensitive |

### Iteration Analysis

| Argument | Default | Description |
|----------|---------|-------------|
| `--min-recall` | `0.0` | Minimum recall threshold to flag families needing attention |
| `--previous-report` | — | Previous recall report TSV for computing marginal gains |
| `--stopping-threshold` | `2` | Stop iterating when marginal gain ≤ this value |

### Pattern Suggestion

| Argument | Default | Description |
|----------|---------|-------------|
| `--suggest-patterns` | — | Output file for suggested patterns (families below threshold) |
| `--suggest-min-matches` | `2` | Minimum false negatives a suggested pattern must match |

## Pattern File Format

The pattern file contains one pattern per line with optional family labels:

```
pattern<TAB>label
```

**Examples:**

```
Hamilton Anxiety Rating Scale (HAM-A)	HAM-A
Patient Health Questionnaire	PHQ
PROMIS[ -]Emotional[ -]Distress	PROMIS
```

Patterns can be:

- **Plain text**: Automatically escaped and converted to flexible regex (spaces/hyphens interchangeable)
- **Regex**: Character classes like `[ -]`, quantifiers, and alternation are preserved

Unlabeled patterns derive family names from parenthetical abbreviations (e.g., `(HAM-A)` → `HAM-A`).

## Output Format

### Recall Report TSV

The TSV output contains per-family and per-pattern metrics:

| Column | Description |
|--------|-------------|
| `family` | Instrument family label |
| `pattern` | Pattern string or `[FAMILY: name]` for summary rows |
| `source_count` | tinyIds matched in source JSON |
| `pipeline_count` | tinyIds also found in pipeline output |
| `missing_count` | False negative count |
| `recall` | Recall percentage (0.000–1.000) |
| `missing_tinyids` | Pipe-separated list of missing tinyIds |

### Markdown Report

The markdown report includes:

- **Summary table**: Overall recall, families at 100%, families below threshold
- **Recall by family**: Sorted table with status indicators (✓ Complete, △ Needs Work, ✗ Low)
- **Iteration gains**: Comparison with previous report (if provided)
- **Details by family**: Per-pattern breakdown with missing tinyIds
- **Version history**: Accumulated across iterations

## Examples

### Basic Recall Analysis

```bash
cde-analyzer recall_analyze \
    -i cdes.json -m CDE \
    --pattern-file instrument_patterns.txt \
    --pipeline-output coalesced_instruments.tsv \
    -o recall_report.tsv
```

### With Markdown Report and Iteration Tracking

```bash
cde-analyzer recall_analyze \
    -i cdes.json -m CDE \
    --pattern-file instrument_patterns.txt \
    --pipeline-output final_coalesced.tsv \
    -o recall_phase3.tsv \
    --markdown-report recall_report.md \
    --report-version "phase3-v2" \
    --previous-report recall_phase2.tsv \
    --min-recall 0.8
```

### Generate Pattern Suggestions

```bash
cde-analyzer recall_analyze \
    -i cdes.json -m CDE \
    --pattern-file instrument_patterns.txt \
    --pipeline-output coalesced.tsv \
    -o recall.tsv \
    --min-recall 0.7 \
    --suggest-patterns suggested_patterns.tsv \
    --suggest-min-matches 3
```

### Export False Negatives for Review

```bash
cde-analyzer recall_analyze \
    -i cdes.json -m CDE \
    --pattern-file patterns.txt \
    --pipeline-output instruments.tsv \
    -o recall.tsv \
    --false-negatives-file false_negatives.txt
```

## Iteration Workflow

The command supports iterative improvement with marginal gain tracking:

1. **Initial run**: Generate baseline recall metrics
2. **Improve patterns**: Add patterns for low-recall families
3. **Subsequent runs**: Use `--previous-report` to track improvements
4. **Stopping criterion**: When marginal gain ≤ threshold, diminishing returns reached

```bash
# Iteration 1
cde-analyzer recall_analyze ... -o recall_iter1.tsv --report-version iter-01

# Iteration 2 (after adding patterns)
cde-analyzer recall_analyze ... -o recall_iter2.tsv \
    --previous-report recall_iter1.tsv \
    --report-version iter-02
```

The report will show:
- Per-family gains: `PHQ: 45 → 52 (+7)`
- Total new CDEs captured
- Stopping criterion status

## Related Commands

- [discovery_report](discovery_report.md) — Generate pipeline summary reports
- [pipeline_report](pipeline_report.md) — Generate comprehensive workflow reports
- [strip_discover](strip_discover.md) — Discover pattern occurrences
- [pattern_util](pattern_util.md) — TSV utilities for pattern manipulation
