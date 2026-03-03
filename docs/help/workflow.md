# `workflow` Command

YAML-based workflow orchestrator for CDE analysis pipelines.

## Overview

The `workflow` command executes sequential pipelines defined in YAML files. It provides:

- **Template management** - List and copy built-in workflow templates
- **Variable substitution** - Environment variables, YAML defaults, and CLI overrides
- **Human checkpoints** - Pause for curator review, resume later
- **State persistence** - Track progress across sessions
- **Dry-run mode** - Preview commands without executing

## Usage

```bash
# List and copy templates (recommended first steps)
cde-analyzer workflow list
cde-analyzer workflow copy <workflow_name> [--as NAME] [--dest DIR]

# Configure branching strip for specific variants
cde-analyzer workflow configure <CODE> [CODE...] [-o FILE]

# Execute workflows
cde-analyzer workflow run <workflow.yaml> [--set KEY=VALUE] [--only-steps S1,S2] [--dry-run]
cde-analyzer workflow resume [--state-file FILE]
cde-analyzer workflow status [--state-file FILE]
```

## Recommended Workflow

The built-in workflows in the codebase are templates. Copy them to your working directory before running to allow customization without modifying the codebase:

```bash
# 1. List available templates
cde-analyzer workflow list

# 2. Copy template to current directory
cde-analyzer workflow copy instrument_detection

# 3. Edit the copied file to customize variables/arguments
#    (e.g., change input paths, output directory, parameters)

# 4. Run your customized workflow
cde-analyzer workflow run ./instrument_detection.yaml
```

## Subcommands

### list

List available workflow templates.

```bash
cde-analyzer workflow list
cde-analyzer workflow list --dir /path/to/workflows
```

Options:
- `--dir DIR` - Directory to search for workflow files (default: built-in workflows/)

### copy

Copy a workflow template to the current directory for customization.

```bash
cde-analyzer workflow copy instrument_detection
cde-analyzer workflow copy instrument_detection --as my_pipeline.yaml
cde-analyzer workflow copy instrument_detection --dest ./pipelines/
cde-analyzer workflow copy instrument_detection --force
```

Options:
- `--as NAME` - Output filename (default: same as source)
- `--dest DIR` - Destination directory (default: current directory)
- `--force` - Overwrite existing file without prompting

After copying, edit the workflow YAML to customize variables and arguments for your project.

### run

Execute a workflow from a YAML file.

```bash
cde-analyzer workflow run workflows/instrument_pipeline.yaml
cde-analyzer workflow run workflows/instrument_pipeline.yaml --set input_json=/path/to/cdes.json
cde-analyzer workflow run workflows/instrument_pipeline.yaml --dry-run
cde-analyzer workflow run workflows/instrument_pipeline.yaml --from-step coalesce_patterns
```

Options:
- `--set KEY=VALUE` - Override workflow variable (can be specified multiple times)
- `--dry-run` - Preview workflow without executing
- `--state-dir DIR` - Directory to store workflow state
- `--from-step STEP` - Start execution from specific step
- `--only-steps STEP1,STEP2,...` - Run only these steps (comma-separated); order preserved from YAML

### resume

Resume a paused workflow after a checkpoint.

```bash
cde-analyzer workflow resume
cde-analyzer workflow resume --state-file /path/to/.workflow_state.json
```

Options:
- `--state-file FILE` - Path to workflow state file (default: .workflow_state.json)
- `--dry-run` - Preview remaining steps without executing

### status

Show workflow execution status.

```bash
cde-analyzer workflow status
cde-analyzer workflow status --verbose
```

Options:
- `--state-file FILE` - Path to workflow state file
- `--verbose` - Show detailed step information including variables

### configure

Configure the branching strip pipeline for specific strip variants. Resolves step
dependencies and either prints a ready-to-use command or generates a production YAML
with only the needed steps and variables.

```bash
# Show required steps for one variant
cde-analyzer workflow configure MTSTPT

# Show steps for multiple variants
cde-analyzer workflow configure MTSFPT MTSTPT

# Generate a production YAML with only needed steps
cde-analyzer workflow configure MTSFPT MTSTPT -o production_strip.yaml

# Without quality report
cde-analyzer workflow configure MTSTPT --no-report
```

Options:
- `CODE` - One or more strip codes (positional, required). Valid: MTSFPF, MFSTPF, MFSFPT, MTSFPT, MFSTPT, MTSTPT
- `-o FILE` - Write a production YAML (without: prints steps and command)
- `--no-report` - Exclude the quality_report step
- `--template FILE` - Use a custom template instead of built-in branching_strip.yaml

When generating a YAML with `-o`, variables are filtered to only those referenced by
the selected steps. The generated YAML can be run directly with `workflow run`.

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
  # Action step - executes a cde-analyzer action
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
      When ready, run: cde-analyzer workflow resume

  # Conditional checkpoint - skips if a file already exists
  - name: curator_review
    checkpoint: true
    skip_if_file: "${output_dir}/curated.tsv"
    message: |
      Review ${output_dir}/needs_review.tsv
      When ready, run: cde-analyzer workflow resume

  # More action steps after checkpoint
  - name: strip_instruments
    action: strip_phrases
    args:
      input: "${input_json}"
      output: "${output_dir}/stripped.json"
      patterns: "${output_dir}/curated.tsv"
```

### Centralized Curation Step

Instead of a checkpoint (which pauses for manual file-based review), you can
use a `serve_curation` action step that starts a centralized server. The
server blocks until Ctrl-C, then the workflow continues:

```yaml
  # Centralized curation (replaces a checkpoint step)
  - name: centralized_review
    action: pattern_util
    args:
      serve_curation: "${curation_config}"
      curation_source: "${field_enriched_tsv}"
      no_browser: false

  # After the server stops, merge curator submissions
  - name: merge_curation
    action: pattern_util
    args:
      merge_curation:
        - "${curation_output}/curator_1.tsv"
        - "${curation_output}/curator_2.tsv"
      output: "${curation_output}/results/"
```

See [Distributed Curation — Centralized Mode](../vignettes/distributed-curation.md#centralized-server-mode) for setup details.

### Conditional Checkpoints

Checkpoints can be conditionally skipped using the `skip_if_file` property.
If the specified file exists when the checkpoint is reached, the workflow
proceeds to the next step without pausing:

```yaml
  - name: curator_review
    checkpoint: true
    skip_if_file: "${output_dir}/curated.tsv"
    message: |
      Review ${output_dir}/needs_review.tsv
```

This is used by the incremental curation feature: the `curation_gate` step
writes `curated.tsv` when all patterns are auto-resolved from the ledger,
causing the checkpoint to be skipped. When new patterns require human review,
`curated.tsv` is not written and the checkpoint pauses as usual.

The `skip_if_file` path supports variable substitution (`${var}`).

## Variable Resolution

Variables are resolved in this order (later overrides earlier):

1. **System variables** - Auto-detected (see below)
2. **YAML defaults** - Variables section in workflow file
3. **Local config file** - `{output_dir}/{workflow_name}_config.yaml` (auto-discovered)
4. **CLI overrides** - `--set key=value` arguments (highest priority)

Default value syntax: `${VAR:-default}` uses "default" if VAR is not set. Environment variables referenced in `${VAR}` expressions are resolved after all other sources are merged.

### Local Config File

The workflow engine automatically looks for a project-specific config file in the output directory:

```
{output_dir}/{workflow_name}_config.yaml
```

The `workflow_name` comes from the `name:` field in the workflow YAML (e.g., `phrase_stripping` for `phrase_pipeline.yaml`). Example:

```yaml
# phase2_output/phrase_stripping_config.yaml
k_max: 35
min_parent_tinyids: 10
min_field_count: 6
```

This separates project-specific tuning from the invocation script. The config file is a flat YAML mapping — no `${VAR}` syntax needed (though it is supported).

**Behaviors**:

- If the file does not exist, the workflow proceeds with YAML defaults (no warning)
- `--set` always overrides config file values
- On `resume`, the resolved values from the initial run are used (config is not re-read)
- Loading is logged: which file was read and which values were overridden

### Auto-Detected System Variables

The following variables are automatically detected at runtime:

| Variable | Description |
|----------|-------------|
| `${cpu_count}` | Total logical CPUs on the system |
| `${workers}` | Recommended worker count (cpu_count - 1, min 1) |

These can be overridden in the workflow YAML, config file, or via `--set workers=N`.

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
cde-analyzer workflow run workflows/instrument_pipeline.yaml

# Run with custom paths
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
    --set input_json=/data/cdes.json \
    --set output_dir=/data/phase1_output

# Preview without executing
cde-analyzer workflow run workflows/instrument_pipeline.yaml --dry-run
```

### After Checkpoint

```bash
# Check status
cde-analyzer workflow status --state-file ./phase1_output/.workflow_state.json

# After curator review, resume
cde-analyzer workflow resume --state-file ./phase1_output/.workflow_state.json
```

## Built-in Workflow Templates

The codebase includes pre-built workflow templates. Use `workflow list` to see them, and `workflow copy` to copy them to your working directory for customization:

| Template | Description |
|----------|-------------|
| `instrument_detection` | Full instrument detection with abbreviation expansion |
| `instrument_major_only` | Major instruments only (sub-instruments removed), with deduplication |
| `instrument_pipeline` | Phase 1: Basic instrument mining and stripping |
| `phrase_pipeline` | Phase 2: Generic phrase mining and stripping |
| `abbreviation_expander` | Standalone abbreviation expansion |
| `temporal_stripping` | Temporal phrase stripping |
| `phrase_family_stripping` | Phrase family stripping |
| `quick_strip` | Quick strip with minimal steps |
| `full_pipeline` | Complete multi-phase stripping pipeline |
| `branching_strip` | Phase 3: 6-way branching strip (use `configure` for production subsets) |

## Related Commands

- [Workflow Architecture](../workflow-architecture.md) — Pipeline diagrams and command reference
- [strip_discover](strip_discover.md) — Pattern discovery command
- [strip_phrases](strip_phrases.md) — Pattern stripping command
