# Vignette: Pipeline Orchestration

How to use the workflow engine effectively — variable resolution, config
files, scaffold scripts, checkpoints, resume, and advanced execution control.

## What This Vignette Covers

The CDE Analyzer workflow engine executes YAML-defined pipelines with
variable substitution, human checkpoints, and resume capability. This
vignette is the "power user" guide:

- The variable resolution chain and three ways to customize parameters
- Using `workflow scaffold` to generate project-specific scripts
- Checkpoint and resume mechanics
- Advanced features: `--from-step`, `--dry-run`, state files
- Common recipes for re-running and debugging

**Prerequisites**: Familiarity with the [Quickstart](quickstart.md) walkthrough.

**Related documentation**:

- [workflow reference](../help/workflow.md) — complete flag reference
- [Workflow Architecture](../workflow-architecture.md) — pipeline diagrams
- [Parameter Tuning](parameter-tuning.md) — what values to set

---

## 1. The Workflow Engine

A workflow YAML file defines:

- **Variables** — configurable values with defaults and environment fallbacks
- **Steps** — sequential actions, each mapping to a `cde-analyzer` command
- **Checkpoints** — human review gates that pause execution

```yaml
name: phrase_stripping
variables:
  input_json: "${PHRASE_INPUT:-inst_stripped.json}"
  k_max: "${K_MAX:-25}"
  workers: 0

steps:
  - name: mine_phrases
    action: phrase_miner
    args:
      input: "${input_json}"
      k_max: "${k_max}"
  # ...
```

The engine resolves variables, converts `args` to CLI flags (underscores
become hyphens), and calls each action in-process — no shell subprocess.
Boolean `true` becomes a flag (`--enable-subsumption`), `false` is omitted.

---

## 2. Variable Resolution Chain

Variables resolve through four layers, lowest to highest priority:

| Priority | Source | Persistence | Example |
|----------|--------|-------------|---------|
| 1 (lowest) | System defaults | Session | `cpu_count`, `workers` |
| 2 | YAML `variables:` section | Version-controlled | `k_max: 25` |
| 3 | Local config file | Per-project | `phrase_stripping_config.yaml` |
| 4 (highest) | `--set KEY=VALUE` | Ephemeral | `--set k_max=35` |

Within each variable's value, `${VAR}` references resolve against the
variables dict first, then the OS environment, then an inline default:

```yaml
# ${VAR:-default} syntax
input_json: "${PHRASE_INPUT:-inst_stripped.json}"
#            ^^^^^^^^^^^^    ^^^^^^^^^^^^^^^^^^
#            env var name    fallback if unset
```

Three resolution passes handle nested references like
`${output_dir}/coalesced.tsv` where `output_dir` itself was just set.

---

## 3. Three Ways to Customize

### Method A: Edit the YAML (permanent)

Copy the workflow template to your project and edit the `variables:` section:

```bash
cde-analyzer workflow copy phrase_pipeline --as my_phrase_pipeline.yaml
```

Edit `my_phrase_pipeline.yaml`:

```yaml
variables:
  k_max: 35                    # changed from 25
  min_parent_tinyids: 5        # changed from 20
```

Run your copy:

```bash
cde-analyzer workflow run ./my_phrase_pipeline.yaml \
    --set "input_json=/data/inst_stripped.json" \
    --set "output_dir=/data/phase2_output"
```

**When to use**: You are maintaining a project-specific pipeline that
diverges significantly from the defaults.

### Method B: Local config file (persistent per-run)

Create a YAML file named `{output_dir}/{workflow_name}_config.yaml`:

```yaml
# phase2_output/phrase_stripping_config.yaml
k_max: 35
min_parent_tinyids: 5
min_field_count: 4
```

The workflow engine auto-discovers this file when `output_dir` resolves
to the directory containing it. The filename must match the workflow's
`name:` field (e.g., `phrase_stripping` → `phrase_stripping_config.yaml`).

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "output_dir=/data/phase2_output"
# k_max, min_parent_tinyids, min_field_count loaded from config file
```

**When to use**: You want persistent per-dataset overrides without editing
the shared YAML templates.

### Method C: `--set KEY=VALUE` (ephemeral, always wins)

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/inst_stripped.json" \
    --set "output_dir=/data/phase2_output" \
    --set "k_max=35" \
    --set "min_parent_tinyids=5"
```

`--set` overrides are applied last and always win, even over config files.
They are not saved — you must specify them again on re-run.

**When to use**: Quick experiments, one-off overrides, or when running via
the scaffold script (which passes `--set` from shell variables).

### Same parameter, all three methods

Here is `k_max` set to 35 via each method:

=== "YAML edit"

    ```yaml
    # my_phrase_pipeline.yaml
    variables:
      k_max: 35
    ```

=== "Config file"

    ```yaml
    # phase2_output/phrase_stripping_config.yaml
    k_max: 35
    ```

=== "--set override"

    ```bash
    --set "k_max=35"
    ```

---

## 4. Using `workflow scaffold`

For multi-phase pipelines, the scaffold command generates a bash script that
wires together all three phases with configurable shell variables at the top:

```bash
cde-analyzer workflow scaffold allcde01 \
    -i /data/cdes.json \
    -d /data/allcde01_output \
    --with-iterate
```

### Generated script structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── PARAMETERS ──          ← Edit these
PROJECT="allcde01"
CDE_RUN="cde-analyzer"
WORKFLOWS="/path/to/workflows"
INPUT_JSON="/data/cdes.json"
BASE="/data/allcde01_output"
WORKERS=0
K_MAX=25
MIN_PARENT_TINYIDS=20

# ── DERIVED PATHS ──       ← Auto-computed from PARAMETERS
PHASE1_DIR="$BASE/phase1_output"
INST_CURATED="$PHASE1_DIR/curated.tsv"
...

# ── HELPERS ──              ← log_phase(), check_file()
# ── PHASE 1 ──             ← Calls workflow run instrument_pipeline.yaml
# ── PHASE 1 ITERATE ──     ← Residual harvesting loop (if --with-iterate)
# ── PREPARE STRIP ──       ← Inter-phase: hierarchy + strip patterns
# ── PHASE 2 ──             ← Calls workflow run phrase_pipeline.yaml
# ── PHASE 3 ──             ← Calls workflow run branching_strip.yaml
# ── DISPATCH ──             ← case statement: phase1|phase2|phase3|all
```

### Customizing the generated script

Edit the `PARAMETERS` section at the top. The phase functions pass these
as `--set` overrides to the workflow engine:

```bash
# Before (default)
K_MAX=25
MIN_PARENT_TINYIDS=20

# After (tuned for small dataset)
K_MAX=25
MIN_PARENT_TINYIDS=2
```

### Running phases

```bash
./run_pipeline.sh phase1           # Instrument detection
./run_pipeline.sh phase1_iterate   # Iterative harvesting (3 rounds)
./run_pipeline.sh phase1_iterate 5 # Iterative harvesting (5 rounds)
./run_pipeline.sh prepare_strip    # Generate hierarchy + strip patterns
./run_pipeline.sh phase2           # Phrase mining
./run_pipeline.sh phase3           # 5-way branching strip
./run_pipeline.sh all              # Run phase1, then prompt for next steps
```

### Scaffold options

| Flag | Default | Purpose |
|------|---------|---------|
| `project_name` | (required) | Short name for header and directories |
| `-i` / `--input-json` | (required) | Path to raw CDE JSON |
| `-d` / `--output-dir` | `.` | Base output directory |
| `-o` / `--output` | `{output_dir}/run_pipeline.sh` | Script output path |
| `--cde-command` | `cde-analyzer` | How to invoke the tool |
| `--phases` | `1,2,3` | Which phases to include |
| `--with-iterate` | off | Include iterative harvesting loop |
| `-f` / `--force` | off | Overwrite existing script |

!!! tip "Windows users"
    On Windows, scaffold auto-converts paths to WSL format
    (`D:\data\cdes.json` → `/mnt/d/data/cdes.json`). Run the generated
    script inside WSL.

---

## 5. Checkpoints and Resume

### How checkpoints work

When the workflow reaches a step with `checkpoint: true`, it:

1. Saves state to `{output_dir}/.workflow_state.json`
2. Prints the checkpoint message with instructions
3. Exits with code 0

The state file records which steps completed and with what variables.

### Resuming after curation

After reviewing and saving your curated file:

```bash
cde-analyzer workflow resume \
    --state-file phase1_output/.workflow_state.json
```

The engine loads the state, skips completed steps, and continues from the
post-checkpoint step.

### Manual override pattern

Sometimes you want to re-run an intermediate step with different parameters
(e.g., re-coalesce with lower `min_parent_tinyids`). You can:

1. Re-run the step manually with `cde-analyzer pattern_util ...`
2. The output file is overwritten in place
3. Resume the workflow — it picks up the updated file

The state file's parameter values won't reflect your manual override, but
the workflow correctly treats completed steps as done and uses whatever
files exist on disk.

!!! warning "State file caveat"
    The state file records the parameters from the *original* run. If you
    need to reproduce the exact pipeline later, document your manual
    overrides separately.

---

## 6. Advanced Execution Control

### `--from-step`: Skip earlier steps

Re-run the pipeline starting from a specific step:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "output_dir=/data/phase2_output" \
    --from-step coalesce_patterns
```

This skips `mine_phrases` and `discover_verbatim`, starting directly at
`coalesce_patterns`. Useful when earlier outputs are still valid and you
want to experiment with coalescing parameters.

### `--dry-run`: Preview resolved commands

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/inst_stripped.json" \
    --set "output_dir=/data/phase2_output" \
    --dry-run
```

Output:

```
[DRY RUN] Workflow: phrase_stripping

Step 1: mine_phrases
  Command: cde-analyzer phrase_miner --input /data/inst_stripped.json \
      --output /data/phase2_output/ --enable-subsumption --k-max 25 --k-min 3

Step 2: discover_verbatim
  Command: cde-analyzer strip_discover --input /data/inst_stripped.json \
      --model CDE --output /data/phase2_output/discovered.tsv ...
```

This shows all resolved variables and the exact CLI commands that would run,
without executing anything.

### `--only-steps`: Run a subset of steps

Run only specific named steps from a workflow, preserving YAML-defined order:

```bash
cde-analyzer workflow run workflows/branching_strip.yaml \
    --only-steps "strip_MTSFPF,expand_temporal,temporal_MTSFPT,strip_MTSFPT,quality_report" \
    --set input_json=/data/cdes.json \
    --set output_dir=/data/output
```

Unknown step names produce a warning and are ignored. Can be combined with
`--from-step` (filtering happens first, then the start point is located within
the filtered list).

### State file inspection

```bash
cde-analyzer workflow status \
    --state-file phase1_output/.workflow_state.json -v
```

Shows which steps completed, their duration, and the current checkpoint state.

---

## 7. Recipes

### Re-run Phase 2 with different k_max

```bash
# Option A: --set override (one-off)
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/inst_stripped.json" \
    --set "output_dir=/data/phase2_rerun" \
    --set "k_max=35"

# Option B: config file (persistent)
echo "k_max: 35" > /data/phase2_rerun/phrase_stripping_config.yaml
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "output_dir=/data/phase2_rerun"
```

### Run only Phase 3 (already have Phase 1+2 outputs)

Generate a scaffold with only Phase 3:

```bash
cde-analyzer workflow scaffold myproject \
    -i /data/cdes.json \
    -d /data/output \
    --phases 3
```

The generated script will include `TODO` placeholders for the Phase 1/2
output paths that Phase 3 needs:

```bash
# TODO: Set path to strip pattern base from a prior Phase 1 run
STRIP_PATTERNS_BASE=""  # e.g., /path/to/phase1_output/strip_patterns
```

Or run directly:

```bash
cde-analyzer workflow run workflows/branching_strip.yaml \
    --set "input_json=/data/cdes.json" \
    --set "output_dir=/data/branching_output" \
    --set "inst_patterns_base=/data/phase1_output/strip_patterns" \
    --set "phrase_patterns=/data/phase2_output/curated.tsv"
```

### Multiple projects sharing workflow templates

The built-in YAML templates are designed to be shared. Each project uses its
own `output_dir` and passes project-specific paths via `--set` or config files:

```bash
# Project A (small dataset)
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/projectA/inst_stripped.json" \
    --set "output_dir=/data/projectA/phase2" \
    --set "min_parent_tinyids=2"

# Project B (large dataset)
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/projectB/inst_stripped.json" \
    --set "output_dir=/data/projectB/phase2" \
    --set "min_parent_tinyids=20"
```

The templates themselves never need to be copied or modified. Config files
in each project's output directory provide persistent customization.

### Run specific strip variants (skip unused branches)

The full branching strip produces 5 variants. For production, use `workflow configure`
to determine the minimal step set for the variant(s) you need:

```bash
# See what steps MTSFPT needs
cde-analyzer workflow configure MTSFPT

# Generate a production YAML for two variants
cde-analyzer workflow configure MTSFPT MFSTPT -o production_strip.yaml
cde-analyzer workflow run production_strip.yaml \
    --set input_json=/data/cdes.json \
    --set output_dir=/data/output \
    --set inst_patterns_base=/data/phase1/strip_patterns \
    --set phrase_patterns=/data/phase2/curated.tsv
```

Alternatively, use `--only-steps` directly with the full template:

```bash
cde-analyzer workflow run workflows/branching_strip.yaml \
    --only-steps "strip_MTSFPF,expand_temporal,temporal_MTSFPT,strip_MTSFPT,quality_report" \
    --set input_json=/data/cdes.json \
    --set output_dir=/data/output \
    --set inst_patterns_base=/data/phase1/strip_patterns \
    --set phrase_patterns=/data/phase2/curated.tsv
```

### List available workflow templates

```bash
cde-analyzer workflow list
```

```
Available workflows:
  instrument_pipeline    Phase 1 - Mine and strip instrument patterns
  phrase_pipeline         Phase 2 - Mine and strip generic phrases
  branching_strip         Phase 3 - 5-way branching strip
```
