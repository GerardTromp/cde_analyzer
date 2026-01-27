# workflow

YAML-based workflow orchestrator for CDE analysis pipelines.

## Synopsis

```bash
cde_analyzer workflow run <workflow.yaml> [--set KEY=VALUE] [--dry-run]
cde_analyzer workflow resume [--state-file FILE]
cde_analyzer workflow status [--state-file FILE]
cde_analyzer workflow list [--dir DIR]
```

## Description

The `workflow` command executes sequential pipelines defined in YAML files. It provides:

- **Variable substitution** - Environment variables, YAML defaults, and CLI overrides
- **Human checkpoints** - Pause for curator review, resume later
- **State persistence** - Track progress across sessions
- **Dry-run mode** - Preview commands without executing

## Subcommands

### run

Execute a workflow from a YAML file.

```bash
cde_analyzer workflow run workflows/instrument_pipeline.yaml
cde_analyzer workflow run workflows/instrument_pipeline.yaml --set input_json=/path/to/cdes.json
cde_analyzer workflow run workflows/instrument_pipeline.yaml --dry-run
cde_analyzer workflow run workflows/instrument_pipeline.yaml --from-step coalesce_patterns
```

Options:
- `--set KEY=VALUE` - Override workflow variable (can be specified multiple times)
- `--dry-run` - Preview workflow without executing
- `--state-dir DIR` - Directory to store workflow state
- `--from-step STEP` - Start execution from specific step

### resume

Resume a paused workflow after a checkpoint.

```bash
cde_analyzer workflow resume
cde_analyzer workflow resume --state-file /path/to/.workflow_state.json
```

Options:
- `--state-file FILE` - Path to workflow state file (default: .workflow_state.json)
- `--dry-run` - Preview remaining steps without executing

### status

Show workflow execution status.

```bash
cde_analyzer workflow status
cde_analyzer workflow status --verbose
```

Options:
- `--state-file FILE` - Path to workflow state file
- `--verbose` - Show detailed step information including variables

### list

List available workflow files.

```bash
cde_analyzer workflow list
cde_analyzer workflow list --dir /path/to/workflows
```

Options:
- `--dir DIR` - Directory to search for workflow files (default: workflows/)

## Workflow YAML Format

```yaml
name: my_workflow
description: What this workflow does

variables:
  # Default values - can use environment variables with defaults
  input_json: "${CDE_INPUT:-cdes.json}"
  output_dir: "./output"

  # Derived variables reference other variables
  instruments_tsv: "${output_dir}/instruments.tsv"

steps:
  # Action step - executes a cde_analyzer action
  - name: mine_instruments
    action: instrument_miner
    args:
      input: "${input_json}"
      output: "${output_dir}/"
      detect_families: true

  # Checkpoint step - pauses for human review
  - name: curator_review
    checkpoint: true
    message: |
      Review ${output_dir}/coalesced.tsv
      When ready, run: cde_analyzer workflow resume

  # More action steps after checkpoint
  - name: strip_instruments
    action: strip_phrases
    args:
      input: "${input_json}"
      output: "${output_dir}/stripped.json"
      patterns: "${output_dir}/curated.tsv"
```

## Variable Resolution

Variables are resolved in this order (later overrides earlier):

1. **Environment variables** - `$VAR` or `${VAR}`
2. **YAML defaults** - Variables section in workflow file
3. **CLI overrides** - `--set key=value` arguments

Default value syntax: `${VAR:-default}` uses "default" if VAR is not set.

## State File

Workflow state is saved to `.workflow_state.json` in the state directory (defaults to output_dir). This tracks:

- Current step index
- Completed steps with timestamps
- Variable values used
- Checkpoint messages

## Example Usage

### Full Instrument Pipeline

```bash
# Run with default paths
cde_analyzer workflow run workflows/instrument_pipeline.yaml

# Run with custom paths
cde_analyzer workflow run workflows/instrument_pipeline.yaml \
    --set input_json=/data/cdes.json \
    --set output_dir=/data/phase1_output

# Preview without executing
cde_analyzer workflow run workflows/instrument_pipeline.yaml --dry-run
```

### After Checkpoint

```bash
# Check status
cde_analyzer workflow status --state-file ./phase1_output/.workflow_state.json

# After curator review, resume
cde_analyzer workflow resume --state-file ./phase1_output/.workflow_state.json
```

## Built-in Workflows

The `workflows/` directory contains pre-built pipelines:

- **instrument_pipeline.yaml** - Phase 1: Instrument mining and stripping
- **phrase_pipeline.yaml** - Phase 2: Generic phrase mining and stripping

## See Also

- [workflow-diagram.md](../workflow-diagram.md) - Visual workflow documentation
- [strip_discover](strip_discover.md) - Pattern discovery command
- [strip_phrases](strip_phrases.md) - Pattern stripping command
