# `strip_report` Command

Generate markdown quality reports for stripped JSON outputs with per-branch remnant detection, temporal phrase inventory, and embed data manifest.

## Overview

The `strip_report` command scans an output directory for stripped JSON files, runs the full remnant detector (15 detritus types) against each file, optionally inventories remaining temporal phrases, and produces a structured markdown report with version history tracking.

Designed to run as the final step in the `branching_strip.yaml` workflow, providing automated quality verification after stripping.

## Usage

```bash
# Basic report
cde-analyzer strip_report -d branching_output/ -o branching_output/strip_report.md

# With input baseline and version label
cde-analyzer strip_report -d branching_output/ \
    -i cdes_subset.json --version v2-temporal-fix \
    -o branching_output/strip_report.md

# Include embed CSV manifest
cde-analyzer strip_report -d branching_output/ \
    -i cdes_subset.json --embed-dir embed_data/ \
    -o branching_output/strip_report.md

# Custom JSON glob (scan all JSON, not just *_stripped.json)
cde-analyzer strip_report -d output/ --json-pattern "*.json" \
    -o output/report.md
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `-d, --output-dir` | yes | Directory containing stripped JSON files |
| `-o, --output` | yes | Path to markdown report output |
| `-i, --input-json` | no | Original input JSON (for baseline record count) |
| `--version` | no | Version label for iteration tracking (e.g., `v2-temporal-fix`) |
| `--embed-dir` | no | Embed data directory for CSV file manifest |
| `--no-temporal-scan` | no | Skip scanning for remaining temporal phrases |
| `--json-pattern` | no | Glob pattern for JSON files (default: `*_stripped.json`) |

## Report Contents

### Branch Summary

File inventory with record counts and sizes for each stripped JSON found in the output directory.

### Quality Checks

Per-branch remnant detection matrix. Rows are remnant types (15 total), columns are branches. Each cell shows either a checkmark (zero remnants) or a count. The status row summarizes: **CLEAN** or **N in M records**.

Remnant types detected:

- `orphan_article` — trailing article before punctuation ("the ,")
- `trailing_article` — trailing article at end of text
- `leading_article` — leading article followed by punctuation
- `dangling_s` — orphan possessive 's after whitespace
- `floating_punct` — floating punctuation surrounded by spaces
- `excess_whitespace` — double or more spaces
- `orphan_preposition` — trailing preposition before punctuation
- `orphan_conjunction` — trailing conjunction before punctuation
- `empty_parens` — empty parentheses "()"
- `empty_brackets` — empty brackets "[]"
- `leading_punct` — leading punctuation
- `trailing_punct_space` — space before trailing punctuation
- `double_punct` — repeated punctuation
- `orphan_anchor` — trailing anchor phrase remnant (as part of, etc.)
- `orphan_suffix` — trailing orphan suffix (questionnaire, form)

### Remaining Temporal Phrases

Per-branch inventory of uncurated temporal patterns still present in the text. Matches the regex:

```
\b(in|over|during|for|within)\s+the\s+(past|last)\s+(\d+|[a-z]+)\s+(days?|weeks?|months?|years?)
```

Shows phrase text, occurrence count, and sample tinyIds. Useful for identifying the next round of patterns to curate.

### Embed Data Manifest (optional)

CSV file sizes and row counts from the embed data directory. Only shown when `--embed-dir` is provided.

### Version History

Append-only table tracking report iterations. Previous history rows are preserved when the report is regenerated to the same file.

## Workflow Integration

The `branching_strip.yaml` workflow includes `strip_report` as its final step:

```yaml
- name: quality_report
  action: strip_report
  args:
    output_dir: "${output_dir}"
    input_json: "${input_json}"
    output: "${output_dir}/strip_report.md"
    version: "${version}"
```

Set the version via `--set version=v2` when running the workflow.
