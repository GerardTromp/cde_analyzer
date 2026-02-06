# `pipeline_report` Command

Generate comprehensive markdown summary reports for workflow execution with phase details and key metrics.

## Overview

The `pipeline_report` command creates human-readable markdown reports summarizing pipeline progress across all phases. It can read from workflow state files or scan output directories directly.

Key features:

- **Phase tracking**: Step completion status for each pipeline phase
- **File metrics**: Row counts and tinyId coverage for each output file
- **Executive summary**: Overall progress and key metrics at a glance
- **Version history**: Track iterations across multiple runs
- **Optional recall analysis**: Integrate ground truth comparison

## Usage

```bash
# From workflow state file
cde-analyzer pipeline_report \
    --state-file OUTPUT/.workflow_state.json \
    -o report.md

# From output directory scan
cde-analyzer pipeline_report \
    --output-dir OUTPUT/ \
    -o report.md \
    [--phase N] [--version LABEL]
```

## Arguments

### Input Source (one required)

| Argument | Description |
|----------|-------------|
| `-s, --state-file` | Path to workflow state file (`.workflow_state.json`). Reads completed steps and output paths from workflow execution |
| `-d, --output-dir` | Path to pipeline output directory. Scans for known output files and generates metrics |

### Output

| Argument | Required | Description |
|----------|----------|-------------|
| `-o, --output` | yes | Path to output markdown report |

### Report Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--phase` | — | Generate report for specific phase only (1–4). Without this, generates full pipeline report |
| `--title` | `Pipeline Execution Report` | Title for the report |
| `--version` | — | Version label for this report (e.g., `v1`, `phase2-final`). Tracked in version history |

### Recall Analysis (optional)

| Argument | Description |
|----------|-------------|
| `--ground-truth` | Ground truth pattern file for recall analysis. Format: `pattern<TAB>label` |
| `--pipeline-output` | Pipeline output TSV for recall comparison. Uses `final_coalesced.tsv` by default if `--state-file` provided |
| `--tinyid-column` | Column name for tinyIds in pipeline output (default: `tinyIds`) |
| `--source-json` | Source CDE JSON file for recall analysis. Required if `--ground-truth` is provided |

## Pipeline Phases

The report tracks four standard phases for instrument detection pipelines:

### Phase 1: Initial Mining

**Steps**: `mine_instruments` → `expand_abbreviations` → `discover_abbreviations` → `expansion_review`

**Outputs**:
- `instruments.tsv` — Extracted instrument patterns
- `instruments_verbatim.tsv` — Verbatim pattern occurrences
- `instrument_families.tsv` — Family assignments
- `abbrev_patterns.tsv` — Abbreviation-based patterns

### Phase 2: Discovery & Coalesce

**Steps**: `discover_verbatim` → `coalesce_patterns` → `recall_phase2` → `initial_review`

**Outputs**:
- `discovered_instruments.tsv` — All discovered occurrences
- `coalesced_instruments.tsv` — Deduplicated patterns
- `subsumption_report.tsv` — Subsumption analysis
- `recall_phase2.tsv` — Phase 2 recall metrics

### Phase 3: Family Analysis & Final Coalesce

**Steps**: `family_discovery` → `discover_abbreviations_final` → `final_discover` → `final_coalesce` → `recall_phase3` → `final_review`

**Outputs**:
- `final_discovered.tsv` — Final discovery pass
- `final_coalesced.tsv` — Final pattern set
- `final_subsumption.tsv` — Final subsumption report
- `recall_phase3.tsv` — Phase 3 recall metrics
- `recall_report.md` — Human-readable recall report

### Phase 4: Stripping & Verification

**Steps**: `strip_instruments` → `sanity_check` → `pipeline_complete`

**Outputs**:
- `no_instruments.json` — Stripped CDE data
- `strip_trace.tsv` — Pattern match trace
- `sanity_check.tsv` — Remaining patterns after stripping

## Report Contents

### Executive Summary

Overview of pipeline status with key metrics:

| Metric | Description |
|--------|-------------|
| Pipeline Status | Not Started / Running / Paused / Completed / Failed |
| Current Phase | Active pipeline phase |
| Progress | Steps completed out of total |
| Final Patterns | Pattern count from `final_coalesced.tsv` |
| Unique tinyIds | Coverage from final output |
| Sanity Check | Clean or remaining pattern count |

### Phase Details

For each phase:

- **Steps**: Checklist with completion status
- **Outputs**: Table with file status, row counts, and tinyId coverage

### Version History

Accumulated across reports, tracking:

| Column | Description |
|--------|-------------|
| Version | User-provided version label |
| Date | Report generation date |
| Phase | Current phase at generation time |
| Notes | Key metrics (pattern count, tinyIds) |

## Examples

### Full Pipeline Report from State File

```bash
cde-analyzer pipeline_report \
    --state-file phase1_output/.workflow_state.json \
    -o phase1_output/pipeline_report.md \
    --version "iter-01"
```

### Phase-Specific Report

```bash
cde-analyzer pipeline_report \
    --output-dir phase2_output/ \
    --phase 2 \
    -o phase2_report.md \
    --title "Phase 2 Discovery Report"
```

### Report with Recall Analysis

```bash
cde-analyzer pipeline_report \
    --state-file output/.workflow_state.json \
    -o report.md \
    --ground-truth instrument_patterns.txt \
    --source-json cdes.json
```

### Directory Scan (No State File)

```bash
cde-analyzer pipeline_report \
    --output-dir scheuermann10/phase1_output/ \
    -o report.md \
    --version "phase1-complete"
```

## Workflow Integration

The `pipeline_report` command integrates with the workflow engine:

1. **During execution**: Generate reports at checkpoints
2. **After completion**: Summarize full pipeline execution
3. **Version tracking**: Accumulate history across iterations

Example workflow integration:

```yaml
# In workflow YAML
- name: generate_report
  action: pipeline_report
  args:
    output_dir: "${output_dir}"
    output: "${output_dir}/pipeline_report.md"
    version: "${version_label}"
```

## Related Commands

- [discovery_report](discovery_report.md) — Lightweight per-pipeline summary reports
- [recall_analyze](recall_analyze.md) — Detailed recall analysis with pattern suggestions
- [workflow](workflow.md) — Execute YAML-defined pipelines
- [diagnose_strip](diagnose_strip.md) — Diagnose strip results and suggest patterns
