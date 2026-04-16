#
# File: actions/workflow/run.py
#
"""
Workflow runner implementation.

Executes YAML-defined workflows with:
- Sequential step execution
- Variable resolution (system → yaml → local config → CLI → env fallback)
- Local config auto-discovery ({output_dir}/{workflow_name}_config.yaml)
- Checkpoint/resume capability
- State persistence
- Auto-detected system variables (cpu_count, workers)
"""
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Step dependencies for each branching strip code.
# Maps strip code -> list of step names required (order matches YAML).
STRIP_CODE_STEPS: Dict[str, List[str]] = {
    "MTSFPF": ["strip_MTSFPF"],
    "MFSTPF": ["strip_MFSTPF"],
    "MTSTPF": ["strip_MTSFPF", "strip_MFSTPF"],
    "MFSFPT": ["expand_temporal", "temporal_MFSFPT", "strip_MFSFPT"],
    "MTSFPT": ["strip_MTSFPF", "expand_temporal", "temporal_MTSFPT", "strip_MTSFPT"],
    "MFSTPT": ["strip_MFSTPF", "expand_temporal", "temporal_MFSTPT", "strip_MFSTPT"],
    "MTSTPT": ["strip_MTSFPF", "strip_MFSTPF", "expand_temporal", "temporal_MTSTPT", "strip_MTSTPT"],
}
ALL_STRIP_CODES = sorted(STRIP_CODE_STEPS.keys())


def get_system_variables() -> Dict[str, Any]:
    """
    Get auto-detected system variables for workflow execution.

    Returns variables like:
    - cpu_count: Total logical CPUs
    - workers: Recommended worker count (cpu_count - 1, min 1)
    - _package_root: Absolute path to the cde_analyzer package root
    """
    import multiprocessing
    from pathlib import Path

    cpu_count = multiprocessing.cpu_count()
    # Leave one CPU free for OS/other tasks, minimum 1 worker
    workers = max(1, cpu_count - 1)

    # Package root: actions/workflow/run.py → actions/workflow/ → actions/ → cde_analyzer/
    package_root = str(Path(__file__).resolve().parents[2])

    return {
        "cpu_count": cpu_count,
        "workers": workers,
        "_package_root": package_root,
    }


class WorkflowError(Exception):
    """Workflow execution error."""
    pass


class WorkflowState:
    """Tracks workflow execution state for checkpoints and resume."""

    def __init__(self, state_file: str = ".workflow_state.json"):
        self.state_file = Path(state_file)
        self.workflow_name: str = ""
        self.workflow_file: str = ""
        self.variables: Dict[str, str] = {}
        self.current_step_index: int = 0
        self.completed_steps: List[Dict] = []
        self.status: str = "not_started"  # not_started, running, paused, completed, failed
        self.started_at: Optional[str] = None
        self.paused_at: Optional[str] = None
        self.checkpoint_message: Optional[str] = None

    def save(self):
        """Save state to file."""
        state = {
            "workflow_name": self.workflow_name,
            "workflow_file": self.workflow_file,
            "variables": self.variables,
            "current_step_index": self.current_step_index,
            "completed_steps": self.completed_steps,
            "status": self.status,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "checkpoint_message": self.checkpoint_message,
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved workflow state to {self.state_file}")

    def load(self) -> bool:
        """Load state from file. Returns True if state exists."""
        if not self.state_file.exists():
            return False
        with open(self.state_file, encoding="utf-8") as f:
            state = json.load(f)
        self.workflow_name = state.get("workflow_name", "")
        self.workflow_file = state.get("workflow_file", "")
        self.variables = state.get("variables", {})
        self.current_step_index = state.get("current_step_index", 0)
        self.completed_steps = state.get("completed_steps", [])
        self.status = state.get("status", "not_started")
        self.started_at = state.get("started_at")
        self.paused_at = state.get("paused_at")
        self.checkpoint_message = state.get("checkpoint_message")
        return True

    def mark_step_completed(self, step_name: str, result: Dict):
        """Record a completed step."""
        self.completed_steps.append({
            "name": step_name,
            "completed_at": datetime.now().isoformat(),
            "result": result
        })
        self.current_step_index += 1


def _find_var_expression(text: str, start: int) -> tuple:
    """Find balanced ${...} expression handling nested braces.

    Returns (end_index, inner_content) or (-1, None) if unbalanced.
    start should point to the '$' of '${'.
    """
    if start + 1 >= len(text) or text[start + 1] != '{':
        return -1, None
    depth = 1
    i = start + 2
    while i < len(text) and depth > 0:
        if text[i] == '{' and i > 0 and text[i - 1] == '$':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    if depth == 0:
        return i, text[start + 2:i - 1]
    return -1, None


def resolve_variables(text: str, variables: Dict[str, Any]) -> str:
    """
    Resolve variable references in text.

    Supports:
    - ${VAR} - simple variable reference
    - ${VAR:-default} - variable with default value (default may contain ${...})
    - Environment variable fallback
    """
    if not isinstance(text, str):
        return text

    result = []
    i = 0
    while i < len(text):
        if text[i] == '$' and i + 1 < len(text) and text[i + 1] == '{':
            end, inner = _find_var_expression(text, i)
            if end == -1:
                result.append(text[i])
                i += 1
                continue

            # Check for default value syntax: ${VAR:-default}
            if ":-" in inner:
                var_name, default = inner.split(":-", 1)
            else:
                var_name = inner
                default = None

            # Resolution order: variables dict → environment → default
            if var_name in variables:
                result.append(str(variables[var_name]))
            elif var_name in os.environ:
                result.append(os.environ[var_name])
            elif default is not None:
                # Recursively resolve the default value (may contain ${...})
                result.append(resolve_variables(default, variables))
            else:
                logger.warning(f"Unresolved variable: ${{{var_name}}}")
                result.append(text[i:end])  # Keep original if unresolved

            i = end
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


def resolve_args(args: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve variables in args dictionary."""
    resolved = {}
    for key, value in args.items():
        if isinstance(value, str):
            resolved[key] = resolve_variables(value, variables)
        elif isinstance(value, list):
            resolved[key] = [
                resolve_variables(v, variables) if isinstance(v, str) else v
                for v in value
            ]
        elif isinstance(value, dict):
            resolved[key] = resolve_args(value, variables)
        else:
            resolved[key] = value
    return resolved


def _load_workflow_config(variables: Dict[str, Any], workflow_name: str) -> bool:
    """
    Look for a local config YAML in output_dir and merge variables.

    Checks for ``{output_dir}/{workflow_name}_config.yaml``.  If found, each
    key in the config overrides the corresponding workflow variable.  CLI
    ``--set`` overrides are re-applied by the caller after this function
    returns, so they always take highest priority.

    Resolution order (lowest → highest):
        1. Workflow YAML defaults
        2. Local config YAML  ← this function
        3. ``--set`` CLI overrides  (caller re-applies)

    Args:
        variables: Mutable variables dict (modified in-place).
        workflow_name: The ``name:`` field from the workflow YAML.

    Returns:
        True if a config file was loaded, False otherwise.
    """
    if not workflow_name:
        return False

    # Early-resolve output_dir so we know where to look.
    output_dir = variables.get("output_dir", "")
    if not output_dir:
        return False
    output_dir = resolve_variables(str(output_dir), variables)

    config_filename = f"{workflow_name}_config.yaml"
    config_path = Path(output_dir) / config_filename

    if not config_path.exists():
        return False

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load {config_path}: {e}")
        return False

    if not isinstance(config, dict):
        logger.warning(f"Ignoring {config_path}: expected YAML mapping, got {type(config).__name__}")
        return False

    # Merge: config values override YAML defaults
    overridden = []
    for key, value in config.items():
        # Convert non-string values so variable resolution works uniformly
        str_value = str(value) if not isinstance(value, str) else value
        if key in variables and str(variables[key]) != str_value:
            overridden.append(f"{key}={str_value} (was {variables[key]})")
        variables[key] = str_value

    logger.info(f"Loaded {len(config)} variable(s) from {config_path}")
    if overridden:
        for desc in overridden:
            logger.info(f"  Config override: {desc}")

    return True


def load_workflow(workflow_path: str) -> Dict:
    """Load and validate workflow YAML."""
    path = Path(workflow_path)
    if not path.exists():
        raise WorkflowError(f"Workflow file not found: {workflow_path}")

    with open(path, encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    # Validate required fields
    if not workflow.get("name"):
        raise WorkflowError("Workflow must have a 'name' field")
    if not workflow.get("steps"):
        raise WorkflowError("Workflow must have 'steps' field")

    return workflow


def build_action_args(action: str, args: Dict[str, Any]) -> List[str]:
    """Convert args dict to CLI argument list."""
    cli_args = []
    for key, value in args.items():
        # Convert underscores to hyphens for CLI
        cli_key = key.replace("_", "-")

        # Handle booleans (native YAML bool or string "true"/"false")
        if isinstance(value, bool) or (isinstance(value, str) and value.lower() in ("true", "false")):
            is_true = value if isinstance(value, bool) else value.lower() == "true"
            if is_true:
                cli_args.append(f"--{cli_key}")
            else:
                cli_args.append(f"--no-{cli_key}")
            continue
        elif isinstance(value, list):
            cli_args.append(f"--{cli_key}")
            for item in value:
                cli_args.append(str(item))
        else:
            cli_args.append(f"--{cli_key}")
            cli_args.append(str(value))

    return cli_args


def execute_step(step: Dict, variables: Dict[str, Any], dry_run: bool = False) -> Dict:
    """
    Execute a single workflow step.

    Returns dict with execution result.
    """
    import argparse

    step_name = step.get("name", "unnamed")
    action = step.get("action")
    args = step.get("args", {})

    # Resolve variables in args
    resolved_args = resolve_args(args, variables)

    # Build CLI command
    cli_args = build_action_args(action, resolved_args)

    print(f"\n{'='*70}")
    print(f"Step: {step_name}")
    print(f"Action: {action}")
    print(f"Command: cde-analyzer {action} {' '.join(cli_args)}")
    print(f"{'='*70}")

    if dry_run:
        print("[DRY RUN] Would execute above command")
        return {"status": "skipped", "dry_run": True}

    # Import and execute the action
    try:
        # Dynamic import of CLI module to get argparse registration
        cli_module = __import__(
            f"actions.{action}.cli",
            fromlist=["register_subparser"]
        )

        # Dynamic import of run module
        run_module = __import__(
            f"actions.{action}.run",
            fromlist=["run_action"]
        )
        run_action = run_module.run_action

        # Create a parser and register the action's arguments
        # This ensures we get proper default values
        parser = argparse.ArgumentParser()
        cli_module.register_subparser(parser)

        # Parse the CLI args to get a proper Namespace with defaults
        args_ns = parser.parse_args(cli_args)

        # Execute
        result = run_action(args_ns)

        return {
            "status": "success" if result == 0 else "failed",
            "return_code": result
        }

    except ImportError as e:
        logger.error(f"Failed to import action '{action}': {e}")
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error(f"Step '{step_name}' failed: {e}")
        return {"status": "failed", "error": str(e)}


def run_workflow(
    workflow: Dict,
    workflow_path: str,
    variables: Dict[str, Any],
    state: WorkflowState,
    dry_run: bool = False,
    from_step: Optional[str] = None,
    only_steps: Optional[set] = None,
) -> int:
    """
    Execute workflow steps sequentially.

    Returns 0 on success/checkpoint, non-zero on failure.
    """
    steps = workflow.get("steps", [])

    # Filter to requested steps only (preserving YAML order)
    if only_steps:
        original_count = len(steps)
        known_names = {s.get("name") for s in steps}
        unknown = only_steps - known_names
        if unknown:
            print(f"Warning: Unknown step names ignored: {', '.join(sorted(unknown))}")
        steps = [s for s in steps if s.get("name") in only_steps]
        if not steps:
            print("Error: No valid steps to execute after --only-steps filtering")
            return 1
        print(f"Filtered: {len(steps)}/{original_count} steps selected by --only-steps")

    # Determine starting point
    start_index = state.current_step_index
    if from_step:
        for i, step in enumerate(steps):
            if step.get("name") == from_step:
                start_index = i
                break
        else:
            print(f"Error: Step '{from_step}' not found in workflow")
            return 1

    # Initialize state
    state.workflow_name = workflow.get("name", "unnamed")
    state.workflow_file = str(workflow_path)
    state.variables = variables
    state.status = "running"
    if not state.started_at:
        state.started_at = datetime.now().isoformat()

    print(f"\nWorkflow: {state.workflow_name}")
    print(f"Steps: {len(steps)} total, starting from step {start_index + 1}")
    print(f"Variables: {json.dumps(variables, indent=2)}")

    # Execute steps
    for i in range(start_index, len(steps)):
        step = steps[i]
        step_name = step.get("name", f"step_{i+1}")

        # Check for checkpoint
        if step.get("checkpoint"):
            # Conditional skip: if skip_if_file exists, skip checkpoint
            skip_file = step.get("skip_if_file")
            if skip_file:
                resolved_skip = resolve_variables(str(skip_file), variables)
                if Path(resolved_skip).exists():
                    print(f"\n  Checkpoint '{step_name}' skipped: "
                          f"{resolved_skip} exists (all patterns auto-resolved)")
                    if not dry_run:
                        state.mark_step_completed(step_name, {
                            "status": "skipped",
                            "skip_reason": "skip_if_file exists",
                            "skip_file": resolved_skip,
                        })
                    continue  # Proceed to next step

            message = step.get("message", "Workflow paused for human review")
            message = resolve_variables(message, variables)

            print(f"\n{'#'*70}")
            print(f"# CHECKPOINT: {step_name}")
            print(f"#")
            for line in message.strip().split("\n"):
                print(f"#   {line}")
            print(f"#")
            print(f"# Resume with: cde-analyzer workflow resume")
            print(f"{'#'*70}")

            # Save state (skip in dry-run mode)
            if not dry_run:
                state.current_step_index = i + 1  # Next step after checkpoint
                state.status = "paused"
                state.paused_at = datetime.now().isoformat()
                state.checkpoint_message = message
                state.save()

            return 0  # Success - checkpoint reached

        # Check conditional execution
        condition = step.get("condition")
        if condition is not None:
            resolved = resolve_variables(str(condition), variables).strip()
            if not resolved:
                print(f"  Skipping '{step_name}' (condition not met)")
                if not dry_run:
                    state.mark_step_completed(step_name, {"status": "skipped"})
                continue

        # Execute action step
        result = execute_step(step, variables, dry_run=dry_run)

        if result.get("status") == "failed" and not dry_run:
            print(f"\nStep '{step_name}' failed!")
            state.status = "failed"
            state.current_step_index = i
            state.save()
            return 1

        # Record completion
        if not dry_run:
            state.mark_step_completed(step_name, result)

    # Workflow completed
    if not dry_run:
        state.status = "completed"
        state.save()

    print(f"\n{'='*70}")
    print(f"Workflow '{state.workflow_name}' completed successfully!")
    print(f"{'='*70}")

    return 0


def cmd_run(args) -> int:
    """Handle 'workflow run' command."""
    workflow_path = args.workflow_file

    # Load workflow
    try:
        workflow = load_workflow(workflow_path)
    except WorkflowError as e:
        print(f"Error: {e}")
        return 1

    # Build variables: system → YAML → local config → CLI overrides
    # System variables (cpu_count, workers) can be overridden by any later stage
    variables = get_system_variables()
    variables.update(workflow.get("variables", {}))

    # Parse CLI overrides into a dict (applied twice: once now, once after config)
    cli_overrides = {}
    if args.overrides:
        for override in args.overrides:
            if "=" not in override:
                print(f"Error: Invalid override format '{override}', expected KEY=VALUE")
                return 1
            key, value = override.split("=", 1)
            cli_overrides[key] = value
    variables.update(cli_overrides)

    # Load local config from output_dir (e.g., phase2_output/phrase_stripping_config.yaml)
    workflow_name = workflow.get("name", "")
    config_loaded = _load_workflow_config(variables, workflow_name)

    # Re-apply CLI overrides so --set always wins over config file
    if config_loaded and cli_overrides:
        variables.update(cli_overrides)

    # Resolve variables that reference other variables
    # (multiple passes for nested references)
    for _ in range(3):
        resolved = {}
        for key, value in variables.items():
            if isinstance(value, str):
                resolved[key] = resolve_variables(value, variables)
            else:
                resolved[key] = value
        variables = resolved

    # Determine state directory
    state_dir = args.state_dir
    if not state_dir:
        # Use output_dir if defined, else current directory
        state_dir = variables.get("output_dir", ".")
    state_dir = resolve_variables(state_dir, variables)

    # Create state tracker
    state = WorkflowState(Path(state_dir) / ".workflow_state.json")

    # Parse --only-steps
    only_steps = None
    raw_only = getattr(args, "only_steps", None)
    if raw_only:
        only_steps = {s.strip() for s in raw_only.split(",") if s.strip()}

    # Run workflow
    return run_workflow(
        workflow,
        workflow_path,
        variables,
        state,
        dry_run=args.dry_run,
        from_step=getattr(args, "from_step", None),
        only_steps=only_steps,
    )


def cmd_resume(args) -> int:
    """Handle 'workflow resume' command."""
    state = WorkflowState(args.state_file)

    if not state.load():
        print(f"Error: No workflow state found at {args.state_file}")
        print("Run a workflow first with: cde-analyzer workflow run <workflow.yaml>")
        return 1

    if state.status == "completed":
        print(f"Workflow '{state.workflow_name}' is already completed.")
        return 0

    if state.status not in ("paused", "failed"):
        print(f"Warning: Workflow status is '{state.status}', expected 'paused' or 'failed'")

    # Reload workflow
    try:
        workflow = load_workflow(state.workflow_file)
    except WorkflowError as e:
        print(f"Error loading workflow: {e}")
        return 1

    print(f"Resuming workflow '{state.workflow_name}' from step {state.current_step_index + 1}")

    # Continue execution
    return run_workflow(
        workflow,
        state.workflow_file,
        state.variables,
        state,
        dry_run=args.dry_run
    )


def cmd_status(args) -> int:
    """Handle 'workflow status' command."""
    state = WorkflowState(args.state_file)

    if not state.load():
        print(f"No workflow state found at {args.state_file}")
        return 1

    print(f"Workflow: {state.workflow_name}")
    print(f"Status: {state.status}")
    print(f"Started: {state.started_at or 'N/A'}")

    if state.status == "paused":
        print(f"Paused: {state.paused_at}")
        print(f"Checkpoint message:")
        for line in (state.checkpoint_message or "").split("\n"):
            print(f"  {line}")

    print(f"\nCompleted steps ({len(state.completed_steps)}):")
    for step in state.completed_steps:
        print(f"  - {step['name']} ({step['completed_at']})")

    print(f"\nNext step index: {state.current_step_index}")

    if args.verbose:
        print(f"\nVariables:")
        for key, value in state.variables.items():
            print(f"  {key}: {value}")

    return 0


def get_builtin_workflows_dir() -> Path:
    """Get path to the built-in workflows directory in the package."""
    # The workflows/ directory is at the package root level
    package_root = Path(__file__).parent.parent.parent
    return package_root / "workflows"


def cmd_list(args) -> int:
    """Handle 'workflow list' command."""
    search_dir = Path(args.dir)

    # If using default "workflows" and it doesn't exist locally,
    # fall back to built-in workflows directory
    if args.dir == "workflows" and not search_dir.exists():
        search_dir = get_builtin_workflows_dir()

    if not search_dir.exists():
        print(f"Directory not found: {search_dir}")
        print(f"Create {search_dir}/ and add workflow YAML files.")
        return 1

    yaml_files = list(search_dir.glob("*.yaml")) + list(search_dir.glob("*.yml"))

    if not yaml_files:
        print(f"No workflow files found in {search_dir}/")
        return 0

    print(f"Available workflow templates in {search_dir}/:\n")
    for path in sorted(yaml_files):
        try:
            with open(path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
            name = workflow.get("name", "unnamed")
            desc = workflow.get("description", "")[:60]
            steps = len(workflow.get("steps", []))
            print(f"  {path.name}")
            print(f"    Name: {name}")
            print(f"    Steps: {steps}")
            if desc:
                print(f"    Description: {desc}")
            print()
        except Exception as e:
            print(f"  {path.name} (error: {e})")

    print("To copy a workflow for customization:")
    print("  cde-analyzer workflow copy <workflow_name>")

    return 0


def cmd_copy(args) -> int:
    """Handle 'workflow copy' command."""
    import shutil

    workflow_name = args.workflow_name

    # Normalize workflow name (add .yaml if missing)
    if not workflow_name.endswith(('.yaml', '.yml')):
        workflow_name = f"{workflow_name}.yaml"

    # Look for the workflow in built-in workflows directory
    builtin_dir = get_builtin_workflows_dir()
    source_path = builtin_dir / workflow_name

    # Also check for .yml extension
    if not source_path.exists():
        alt_name = workflow_name.replace('.yaml', '.yml')
        alt_path = builtin_dir / alt_name
        if alt_path.exists():
            source_path = alt_path
            workflow_name = alt_name

    if not source_path.exists():
        print(f"Workflow not found: {workflow_name}")
        print(f"\nAvailable workflows:")
        yaml_files = list(builtin_dir.glob("*.yaml")) + list(builtin_dir.glob("*.yml"))
        for path in sorted(yaml_files):
            print(f"  - {path.stem}")
        return 1

    # Determine output path
    dest_dir = Path(args.dest)
    output_name = args.output_name if args.output_name else workflow_name
    if not output_name.endswith(('.yaml', '.yml')):
        output_name = f"{output_name}.yaml"

    dest_path = dest_dir / output_name

    # Check if destination exists
    if dest_path.exists() and not args.force:
        print(f"File already exists: {dest_path}")
        print("Use --force to overwrite, or --as to specify a different name.")
        return 1

    # Ensure destination directory exists
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy the file
    shutil.copy2(source_path, dest_path)

    # Load workflow to show info
    try:
        with open(dest_path, encoding="utf-8") as f:
            workflow = yaml.safe_load(f)
        name = workflow.get("name", "unnamed")
        steps = len(workflow.get("steps", []))
        variables = workflow.get("variables", {})
    except Exception:
        name = "unknown"
        steps = 0
        variables = {}

    print(f"Copied workflow template to: {dest_path}")
    print(f"\n  Name: {name}")
    print(f"  Steps: {steps}")

    if variables:
        print(f"\n  Variables (customize in the YAML file):")
        for key, value in variables.items():
            # Truncate long values
            value_str = str(value)[:50]
            if len(str(value)) > 50:
                value_str += "..."
            print(f"    {key}: {value_str}")

    print(f"\nNext steps:")
    print(f"  1. Edit {dest_path} to customize variables and arguments")
    print(f"  2. Run: cde-analyzer workflow run {dest_path}")

    return 0


# ── Configure helpers ────────────────────────────────────────────────────────

def _collect_referenced_variables(workflow: Dict) -> set:
    """Scan step args and variable definitions for ${var} references."""
    var_pattern = re.compile(r'\$\{([^}:]+?)(?::-[^}]*)?\}')
    referenced = set()

    # Collect from step args
    for step in workflow.get("steps", []):
        for _key, value in step.get("args", {}).items():
            if isinstance(value, str):
                for m in var_pattern.finditer(value):
                    referenced.add(m.group(1))

    # Follow transitive references (variables that reference other variables)
    changed = True
    while changed:
        changed = False
        for key, value in workflow.get("variables", {}).items():
            if key in referenced and isinstance(value, str):
                for m in var_pattern.finditer(value):
                    if m.group(1) not in referenced:
                        referenced.add(m.group(1))
                        changed = True

    return referenced


def _print_configure_summary(
    codes: List[str],
    step_names: List[str],
    intermediate_outputs: set,
    template_path: str,
    needs_inst: bool,
    needs_phrases: bool,
) -> int:
    """Print step list and ready-to-use command."""
    print(f"Strip codes: {', '.join(codes)}")
    print(f"Required steps ({len(step_names)}):")
    for i, name in enumerate(step_names, 1):
        print(f"  {i}. {name}")

    if intermediate_outputs:
        print(f"\nNote: Intermediate files also produced:")
        for code in sorted(intermediate_outputs):
            print(f"  stripped_{code}.json (required as input to later steps)")

    if len(codes) == len(ALL_STRIP_CODES):
        print(f"\nAll strip codes selected — equivalent to running the full pipeline.")

    # Show ready-to-use command with relative path for built-in template
    display_path = template_path
    builtin = str(get_builtin_workflows_dir())
    if display_path.startswith(builtin):
        display_path = "workflows/branching_strip.yaml"

    steps_csv = ",".join(step_names)
    print(f"\nReady-to-use command:")
    print(f"  cde-analyzer workflow run {display_path} \\")
    print(f"      --only-steps \"{steps_csv}\" \\")
    print(f"      --set input_json=<INPUT> \\")
    print(f"      --set output_dir=<OUTPUT_DIR>", end="")
    if needs_inst:
        print(f" \\\n      --set inst_patterns_base=<PATTERN_BASE>", end="")
    if needs_phrases:
        print(f" \\\n      --set phrase_patterns=<PHRASE_TSV>", end="")
    print()

    return 0


def _print_nway_configure_summary(
    codes: List[str],
    step_names: List[str],
    template_path: str,
    needs_inst: bool,
    needs_phrases: bool,
    variants_csv: str,
) -> int:
    """Print nway configuration summary and ready-to-use command."""
    print(f"Strip codes: {', '.join(codes)}")
    print(f"Mode: N-way single-pass (all variants in one step)")
    print(f"Steps ({len(step_names)}):")
    for i, name in enumerate(step_names, 1):
        print(f"  {i}. {name}")

    if len(codes) == len(ALL_STRIP_CODES):
        print(f"\nAll strip codes selected — full pipeline.")

    # Show ready-to-use command
    display_path = template_path
    builtin = str(get_builtin_workflows_dir())
    if display_path.startswith(builtin):
        display_path = "workflows/branching_strip_nway.yaml"

    print(f"\nReady-to-use command:")
    print(f"  cde-analyzer workflow run {display_path} \\")
    print(f"      --set variants={variants_csv} \\")
    print(f"      --set input_json=<INPUT> \\")
    print(f"      --set output_dir=<OUTPUT_DIR>", end="")
    if needs_inst:
        print(f" \\\n      --set inst_patterns_base=<PATTERN_BASE>", end="")
    if needs_phrases:
        print(f" \\\n      --set phrase_patterns=<PHRASE_TSV>", end="")
    print()

    return 0


def _write_configured_yaml(
    workflow: Dict,
    selected_steps: List[Dict],
    codes: List[str],
    no_report: bool,
    output_path: str,
    nway_variants: Optional[str] = None,
) -> int:
    """Generate a production YAML with only the needed steps."""
    import copy

    configured = copy.deepcopy(workflow)
    codes_str = "_".join(sorted(codes))
    configured["name"] = f"branching_strip_{codes_str}"
    configured["description"] = (
        f"Branching strip configured for: {', '.join(sorted(codes))}"
    )

    # Filter steps
    configured["steps"] = copy.deepcopy(selected_steps)

    # Filter variables to only those referenced by selected steps
    used_vars = _collect_referenced_variables(configured)
    original_vars = configured.get("variables", {})
    filtered_vars = {}

    # Always keep core variables
    for core_var in ("input_json", "output_dir", "model", "workers", "version"):
        if core_var in original_vars:
            filtered_vars[core_var] = original_vars[core_var]

    # Add referenced variables in original definition order
    for key, value in original_vars.items():
        if key in used_vars and key not in filtered_vars:
            filtered_vars[key] = value

    configured["variables"] = filtered_vars

    # For nway mode, set the variants variable to the requested codes
    if nway_variants:
        configured["variables"]["variants"] = nway_variants

    # Write
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    mode_label = "nway single-pass" if nway_variants else "step-filtered"
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Configured branching strip ({mode_label}): {', '.join(sorted(codes))}\n")
        f.write(f"# Generated by: cde-analyzer workflow configure {' '.join(codes)}\n")
        f.write(f"# Steps: {len(configured['steps'])}\n")
        f.write("#\n")
        yaml.dump(configured, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)

    print(f"Wrote configured workflow: {output_path}")
    print(f"  Strip codes: {', '.join(sorted(codes))}")
    print(f"  Mode: {mode_label}")
    print(f"  Steps: {len(configured['steps'])}")
    print(f"\nRun with:")
    print(f"  cde-analyzer workflow run {output_path} \\")
    print(f"      --set input_json=<INPUT> \\")
    print(f"      --set output_dir=<OUTPUT_DIR> \\")
    print(f"      --set inst_patterns_base=<PATTERN_BASE> \\")
    print(f"      --set phrase_patterns=<PHRASE_TSV>")

    return 0


def _is_nway_template(template_path: str) -> bool:
    """Check if a template is the nway (single-pass) branching strip."""
    return "nway" in Path(template_path).stem


def cmd_configure(args) -> int:
    """Handle 'workflow configure' command."""
    codes = [c.upper() for c in args.codes]
    no_report = args.no_report
    output_path = args.output
    template_path = args.template

    # Validate codes
    invalid = [c for c in codes if c not in STRIP_CODE_STEPS]
    if invalid:
        print(f"Error: Invalid strip code(s): {', '.join(invalid)}")
        print(f"Valid codes: {', '.join(ALL_STRIP_CODES)}")
        return 1

    # Deduplicate while preserving order
    seen = set()
    unique_codes = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique_codes.append(c)
    codes = unique_codes

    # Determine which input types are needed from code positions:
    # M[1]S[3]P[5] — T=stripped, F=present
    needs_inst = any(c[1] == "T" or c[3] == "T" for c in codes)
    needs_phrases = any(c[5] == "T" for c in codes)

    # Detect nway template (--template nway or --nway flag)
    use_nway = getattr(args, "nway", False)

    if template_path:
        template = Path(template_path)
        if _is_nway_template(template_path):
            use_nway = True
    elif use_nway:
        template = get_builtin_workflows_dir() / "branching_strip_nway.yaml"
    else:
        template = get_builtin_workflows_dir() / "branching_strip.yaml"

    if not template.exists():
        print(f"Error: Template not found: {template}")
        return 1

    try:
        workflow = load_workflow(str(template))
    except WorkflowError as e:
        print(f"Error: {e}")
        return 1

    # ── N-way mode: configure --variants parameter ──
    if use_nway:
        variants_csv = ",".join(sorted(codes))
        all_steps = workflow.get("steps", [])
        step_names = [s.get("name") for s in all_steps]

        if no_report:
            all_steps = [s for s in all_steps if s.get("name") != "quality_report"]
            step_names = [s.get("name") for s in all_steps]

        if output_path:
            return _write_configured_yaml(
                workflow, all_steps, codes, no_report, output_path,
                nway_variants=variants_csv,
            )
        else:
            return _print_nway_configure_summary(
                codes, step_names, str(template),
                needs_inst, needs_phrases, variants_csv,
            )

    # ── Legacy mode: step-based filtering ──
    # Collect required steps (union, deduplicated)
    required_steps = set()
    for code in codes:
        required_steps.update(STRIP_CODE_STEPS[code])
    if not no_report:
        required_steps.add("quality_report")

    all_steps = workflow.get("steps", [])

    # Filter and order steps according to YAML order
    selected_steps = [s for s in all_steps if s.get("name") in required_steps]
    step_names = [s.get("name") for s in selected_steps]

    # Identify intermediate outputs (steps producing files for codes not requested)
    intermediate_outputs = set()
    for s in selected_steps:
        name = s.get("name", "")
        for code in STRIP_CODE_STEPS:
            if name == f"strip_{code}" and code not in codes:
                intermediate_outputs.add(code)

    if output_path:
        return _write_configured_yaml(
            workflow, selected_steps, codes, no_report, output_path
        )
    else:
        return _print_configure_summary(
            codes, step_names, intermediate_outputs, str(template),
            needs_inst, needs_phrases,
        )


# ── Scaffold helpers ──────────────────────────────────────────────────────────

def _win_to_wsl_path(path: str) -> str:
    """Convert a Windows path (D:\\foo\\bar) to WSL format (/mnt/d/foo/bar)."""
    path = path.replace("\\", "/")
    # Match drive letter pattern: D:/... → /mnt/d/...
    if len(path) >= 2 and path[1] == ":":
        drive = path[0].lower()
        path = f"/mnt/{drive}{path[2:]}"
    return path


def _scaffold_header(project_name: str, timestamp: str, is_windows: bool,
                     phases: set, with_iterate: bool) -> str:
    """Generate script header with shebang, metadata, and usage."""
    lines = [
        '#!/usr/bin/env bash',
        f'# Pipeline Orchestration Script: {project_name}',
        f'# Generated by: cde-analyzer workflow scaffold',
        f'# Date: {timestamp}',
        '#',
        '# Usage:',
    ]
    script = f'./{project_name}_pipeline.sh'
    if 1 in phases:
        lines.append(f'#   {script} phase1           # Run instrument detection')
        if with_iterate:
            lines.append(f'#   {script} phase1_iterate   # Iterative residual harvesting')
    if 3 in phases and 1 in phases:
        lines.append(f'#   {script} prepare_strip    # Generate hierarchy + strip patterns')
    if 2 in phases:
        lines.append(f'#   {script} phase2           # Run phrase mining')
    if 3 in phases:
        lines.append(f'#   {script} phase3           # Run 5-way branching strip')
    lines.append(f'#   {script} all              # Run full pipeline (stops at checkpoints)')
    lines.extend(['', 'set -euo pipefail'])
    if is_windows:
        lines.append('')
        lines.append('# NOTE: Paths auto-converted from Windows to WSL format (/mnt/d/...)')
    return '\n'.join(lines)


def _scaffold_parameters(
    project_name: str,
    cde_command: str,
    workflows_dir: str,
    input_json: str,
    output_dir: str,
    phases: set,
) -> str:
    """Generate PARAMETERS section with all configurable values."""
    lines = [
        '',
        '# ── PARAMETERS ──────────────────────────────────────────────────────────',
        f'PROJECT="{project_name}"',
        f'CDE_RUN="{cde_command}"',
        f'WORKFLOWS="{workflows_dir}"',
        f'INPUT_JSON="{input_json}"',
        f'BASE="{output_dir}"',
    ]
    if 1 in phases:
        lines.append('PHASE1_DIR="$BASE/phase1_output"')
    if 2 in phases:
        lines.append('PHASE2_DIR="$BASE/phase2_output"')
    if 3 in phases:
        lines.append('PHASE3_DIR="$BASE/branching_output"')
    lines.append('')
    lines.append('# Tuning parameters')
    lines.append('WORKERS=0')
    if 2 in phases:
        lines.append('MIN_PARENT_TINYIDS=20')
        lines.append('MIN_FIELD_COUNT=6')
        lines.append('MIN_TOKENS=3')
        lines.append('K_MAX=25')
        lines.append('K_MIN=3')
    return '\n'.join(lines)


def _scaffold_derived_paths(phases: set) -> str:
    """Generate DERIVED PATHS section."""
    lines = [
        '',
        '# ── DERIVED PATHS ───────────────────────────────────────────────────────',
    ]
    if 1 in phases:
        lines.extend([
            'INST_CURATED="$PHASE1_DIR/curated.tsv"',
            'INST_STRIPPED="$PHASE1_DIR/inst_stripped.json"',
            'INST_SANITY="$PHASE1_DIR/sanity_check.tsv"',
        ])
        if 3 in phases:
            lines.extend([
                'INST_HIERARCHY="$PHASE1_DIR/hierarchy.tsv"',
                'STRIP_PATTERNS_BASE="$PHASE1_DIR/strip_patterns"',
            ])
    else:
        # Phase 1 not included — add placeholders for cross-phase dependencies
        if 2 in phases:
            lines.append('# TODO: Set path to instrument-stripped JSON from a prior Phase 1 run')
            lines.append('INST_STRIPPED=""  # e.g., /path/to/phase1_output/inst_stripped.json')
        if 3 in phases:
            lines.append('# TODO: Set path to strip pattern base from a prior Phase 1 run')
            lines.append('STRIP_PATTERNS_BASE=""  # e.g., /path/to/phase1_output/strip_patterns')
    if 2 in phases:
        lines.append('PHRASE_CURATED="$PHASE2_DIR/curated.tsv"')
    return '\n'.join(lines)


def _scaffold_helpers() -> str:
    """Generate helper bash functions."""
    return '''
# ── HELPERS ─────────────────────────────────────────────────────────────

log_phase() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║  $1"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
}

check_file() {
    if [[ ! -f "$1" ]]; then
        echo "ERROR: Required file not found: $1"
        echo "       $2"
        exit 1
    fi
}'''


def _scaffold_phase1(with_iterate: bool) -> str:
    """Generate Phase 1 function."""
    lines = [
        '',
        '# ── PHASE 1: Instrument Detection ───────────────────────────────────────',
        '',
        'phase1() {',
        '    log_phase "Phase 1: Instrument Detection"',
        '',
        '    $CDE_RUN workflow run "$WORKFLOWS/instrument_pipeline.yaml" \\',
        '        --set "input_json=$INPUT_JSON" \\',
        '        --set "output_dir=$PHASE1_DIR" \\',
        '        --set "workers=$WORKERS"',
        '',
        '    echo ""',
        '    echo ">>> CHECKPOINT: Review $PHASE1_DIR/coalesced_fields.tsv"',
        '    echo ">>>   Save curated version as: $INST_CURATED"',
        '    echo ">>>   Then resume:  cde-analyzer workflow resume --state-file $PHASE1_DIR/.workflow_state.json"',
        '}',
    ]
    return '\n'.join(lines)


def _scaffold_phase1_iterate() -> str:
    """Generate Phase 1 iterative harvesting loop."""
    return '''
# ── PHASE 1 ITERATE: Residual Harvesting ────────────────────────────────

phase1_iterate() {
    local MAX_ROUNDS="${1:-3}"
    log_phase "Phase 1 Iterate: Residual Harvesting (max $MAX_ROUNDS rounds)"

    check_file "$INST_CURATED" "Run phase1 and curate first"

    # Dynamic min-count based on CDE count
    local CDE_COUNT
    CDE_COUNT=$(python3 -c "import json; print(len(json.load(open('$INPUT_JSON'))))")
    local MIN_COUNT
    MIN_COUNT=$(python3 -c "print(max(round($CDE_COUNT * 0.0005), 5))")
    echo "CDE count: $CDE_COUNT, dynamic min-count: $MIN_COUNT"

    local CURATED="$INST_CURATED"
    for round in $(seq 1 "$MAX_ROUNDS"); do
        echo ""
        echo "── Round $round/$MAX_ROUNDS ──"

        # Strip with current curated patterns
        local STRIPPED="$PHASE1_DIR/iter_${round}_stripped.json"
        $CDE_RUN strip_phrases \\
            --input "$INPUT_JSON" \\
            --model CDE \\
            --output "$STRIPPED" \\
            --patterns "$CURATED,pattern" \\
            --workers "$WORKERS"

        # Diagnose residuals
        local SANITY="$PHASE1_DIR/iter_${round}_sanity.tsv"
        $CDE_RUN diagnose_strip \\
            --input "$STRIPPED" \\
            --model CDE \\
            --output "$SANITY" \\
            --min-count "$MIN_COUNT" \\
            --suggest-patterns \\
            --emit-tinyids

        # Check if any residuals found
        local RESIDUAL_COUNT
        RESIDUAL_COUNT=$(tail -n +2 "$SANITY" | wc -l)
        echo "Round $round: $RESIDUAL_COUNT residuals found"

        if [[ "$RESIDUAL_COUNT" -eq 0 ]]; then
            echo "No residuals — iteration complete"
            # Copy final stripped as inst_stripped.json
            cp "$STRIPPED" "$INST_STRIPPED"
            break
        fi

        # Harvest residuals into supplementary patterns
        $CDE_RUN supplementary --harvest-to-supplementary "$SANITY"

        # Merge: curated + harvested
        local MERGED="$PHASE1_DIR/iter_${round}_merged.tsv"
        $CDE_RUN pattern_util --merge-patterns "$CURATED" "$SANITY" -o "$MERGED"

        echo ""
        echo ">>> CHECKPOINT: Review $MERGED"
        echo ">>>   Remove false positives, save as $CURATED"
        echo ">>>   Then re-run: $0 phase1_iterate $((MAX_ROUNDS - round))"
        return 0
    done

    echo ""
    echo "Iteration complete. Final patterns: $CURATED"
}'''


def _scaffold_prepare_strip() -> str:
    """Generate inter-phase prepare_strip_patterns function."""
    return '''
# ── INTER-PHASE: Prepare Strip Patterns ─────────────────────────────────

prepare_strip_patterns() {
    log_phase "Prepare Strip Patterns (hierarchy + full/sub generation)"

    check_file "$INST_CURATED" "Run phase1 and curate first"

    # Step 1: Assign group hierarchy (adds group/suffix columns)
    $CDE_RUN instrument_util --group-hierarchy "$INST_CURATED" -o "$INST_HIERARCHY"

    # Step 2: Generate full-removal and sub-group pattern files
    $CDE_RUN instrument_util --generate-strip-patterns "$INST_HIERARCHY" -o "$STRIP_PATTERNS_BASE"

    echo ""
    echo "Generated:"
    echo "  ${STRIP_PATTERNS_BASE}_full.tsv  (full instrument removal)"
    echo "  ${STRIP_PATTERNS_BASE}_sub.tsv   (sub-group prefix removal)"
}'''


def _scaffold_phase2() -> str:
    """Generate Phase 2 function."""
    return '''
# ── PHASE 2: Phrase Mining ──────────────────────────────────────────────

phase2() {
    log_phase "Phase 2: Phrase Mining"

    check_file "$INST_STRIPPED" "Run phase1 (and resume after curation) first"

    $CDE_RUN workflow run "$WORKFLOWS/phrase_pipeline.yaml" \\
        --set "input_json=$INST_STRIPPED" \\
        --set "output_dir=$PHASE2_DIR" \\
        --set "workers=$WORKERS" \\
        --set "k_max=$K_MAX" \\
        --set "k_min=$K_MIN" \\
        --set "min_parent_tinyids=$MIN_PARENT_TINYIDS" \\
        --set "min_field_count=$MIN_FIELD_COUNT" \\
        --set "min_tokens=$MIN_TOKENS"

    echo ""
    echo ">>> CHECKPOINT: Review $PHASE2_DIR/coalesced_fields.tsv"
    echo ">>>   Save curated version as: $PHRASE_CURATED"
    echo ">>>   Then resume:  cde-analyzer workflow resume --state-file $PHASE2_DIR/.workflow_state.json"
}'''


def _scaffold_phase3() -> str:
    """Generate Phase 3 function."""
    return '''
# ── PHASE 3: Branching Strip ────────────────────────────────────────────

phase3() {
    log_phase "Phase 3: 6-Way Branching Strip"

    check_file "${STRIP_PATTERNS_BASE}_full.tsv" "Run prepare_strip first"
    check_file "$PHRASE_CURATED" "Run phase2 and curate first"

    $CDE_RUN workflow run "$WORKFLOWS/branching_strip.yaml" \\
        --set "input_json=$INPUT_JSON" \\
        --set "output_dir=$PHASE3_DIR" \\
        --set "inst_patterns_base=$STRIP_PATTERNS_BASE" \\
        --set "phrase_patterns=$PHRASE_CURATED" \\
        --set "workers=$WORKERS"

    echo ""
    echo "Phase 3 complete. Outputs:"
    echo "  $PHASE3_DIR/stripped_MTSFPF.json"
    echo "  $PHASE3_DIR/stripped_MFSTPF.json"
    echo "  $PHASE3_DIR/stripped_MFSFPT.json"
    echo "  $PHASE3_DIR/stripped_MTSFPT.json"
    echo "  $PHASE3_DIR/stripped_MFSTPT.json"
}'''


def _scaffold_dispatch(phases: set, with_iterate: bool) -> str:
    """Generate the case dispatch block."""
    lines = [
        '',
        '# ── DISPATCH ────────────────────────────────────────────────────────────',
        '',
        'case "${1:-help}" in',
    ]
    if 1 in phases:
        lines.append('    phase1)           phase1 ;;')
        if with_iterate:
            lines.append('    phase1_iterate)   phase1_iterate "${2:-3}" ;;')
    if 3 in phases and 1 in phases:
        lines.append('    prepare_strip)    prepare_strip_patterns ;;')
    if 2 in phases:
        lines.append('    phase2)           phase2 ;;')
    if 3 in phases:
        lines.append('    phase3)           phase3 ;;')

    # Build 'all' target
    if 1 in phases and 2 in phases and 3 in phases:
        lines.append('    all)              phase1; echo ">>> Curate phase1, resume, then: $0 phase2" ;;')
    elif 1 in phases and 2 in phases:
        lines.append('    all)              phase1; echo ">>> Curate phase1, resume, then: $0 phase2" ;;')
    elif 1 in phases:
        lines.append('    all)              phase1 ;;')

    # Help / default
    targets = []
    if 1 in phases:
        targets.append('phase1')
        if with_iterate:
            targets.append('phase1_iterate')
    if 3 in phases and 1 in phases:
        targets.append('prepare_strip')
    if 2 in phases:
        targets.append('phase2')
    if 3 in phases:
        targets.append('phase3')
    targets.append('all')

    targets_str = '|'.join(targets)
    lines.extend([
        f'    help|*)           echo "Usage: $0 [{targets_str}]" ;;',
        'esac',
    ])
    return '\n'.join(lines)


def _load_pipeline_config(config_path: str) -> Dict[str, Any]:
    """Load and validate a pipeline config YAML for scaffold generation."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise WorkflowError(f"Config must be a YAML mapping, got {type(cfg).__name__}")
    required = ["project", "input_json"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise WorkflowError(f"Config missing required keys: {', '.join(missing)}")
    # Defaults
    cfg.setdefault("description", f"{cfg['project']} pipeline")
    cfg.setdefault("phases", [1, 2, 3])
    cfg.setdefault("directories", {})
    dirs = cfg["directories"]
    dirs.setdefault("phase1", "phase1_output")
    dirs.setdefault("phase2", "phase2_output")
    dirs.setdefault("branching", "branching_output_nway")
    dirs.setdefault("branching_legacy", "branching_output")
    dirs.setdefault("ledger", ".curation_ledger")
    cfg.setdefault("phase1", {})
    cfg["phase1"].setdefault("with_iterate", False)
    cfg["phase1"].setdefault("iterate_max_rounds", 3)
    cfg.setdefault("phase2", {})
    cfg["phase2"].setdefault("config_file", "")
    cfg.setdefault("phase3", {})
    cfg["phase3"].setdefault("mode", "nway")
    cfg["phase3"].setdefault("include_legacy", False)
    cfg.setdefault("features", {})
    feats = cfg["features"]
    feats.setdefault("status_dashboard", True)
    feats.setdefault("completion_guards", True)
    feats.setdefault("curation_resume", True)
    return cfg


def _cfg_scaffold_header(cfg: Dict[str, Any]) -> str:
    """Generate script header from config."""
    project = cfg["project"]
    desc = cfg["description"]
    phases = set(cfg["phases"])
    ph1 = cfg["phase1"]
    ph3 = cfg["phase3"]
    lines = [
        '#!/usr/bin/env bash',
        '#',
        f'# {project}: {desc}',
        '#',
        '# Generated by: cde-analyzer workflow scaffold --from-config',
        f'# Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '#',
        '# Usage:',
    ]
    script = f'./run_pipeline.sh'
    if 1 in phases:
        lines.append(f'#   {script} phase1           # Run instrument detection')
        if ph1.get("with_iterate"):
            lines.append(f'#   {script} phase1_iterate   # Iterative residual harvesting')
    if 2 in phases:
        lines.append(f'#   {script} phase2           # Run phrase mining')
    if 3 in phases:
        mode = ph3.get("mode", "nway")
        lines.append(f'#   {script} phase3           # Run branching strip ({mode})')
        if ph3.get("include_legacy"):
            lines.append(f'#   {script} phase3_legacy   # Run legacy branching strip')
    lines.append(f'#   {script} status           # Show pipeline state')
    lines.extend(['#', 'set -euo pipefail'])
    return '\n'.join(lines)


def _cfg_scaffold_parameters(cfg: Dict[str, Any], is_windows: bool) -> str:
    """Generate PARAMETERS section from config."""
    phases = set(cfg["phases"])
    dirs = cfg["directories"]

    # Resolve paths
    cde_analyzer_dir = cfg.get("cde_analyzer_dir", "")
    python_venv = cfg.get("python_venv", "")
    input_json = cfg["input_json"]

    if is_windows:
        if cde_analyzer_dir:
            cde_analyzer_dir = _win_to_wsl_path(os.path.abspath(cde_analyzer_dir))
        if python_venv:
            python_venv = _win_to_wsl_path(os.path.abspath(python_venv))
        input_json_path = input_json
        if os.path.isabs(input_json):
            input_json_path = _win_to_wsl_path(input_json)

    lines = [
        '',
        '# ── PARAMETERS ──────────────────────────────────────────────────────────',
        '',
        'BASE="$(cd "$(dirname "$0")" && pwd)"',
    ]

    if cde_analyzer_dir:
        lines.append(f'CDE_ANALYZER="{cde_analyzer_dir}"')
    if python_venv:
        lines.append(f'VENV="{python_venv}"')

    workflows_dir = str(get_builtin_workflows_dir())
    if is_windows:
        workflows_dir = _win_to_wsl_path(workflows_dir)
    if cde_analyzer_dir:
        lines.append(f'WORKFLOWS="$CDE_ANALYZER/workflows"')
    else:
        lines.append(f'WORKFLOWS="{workflows_dir}"')

    lines.append('')

    # Input JSON — if relative, make it relative to $BASE
    if not os.path.isabs(input_json):
        lines.append(f'INPUT_JSON="$BASE/{input_json}"')
    else:
        lines.append(f'INPUT_JSON="{input_json_path if is_windows else input_json}"')

    # Phase directories
    if 1 in phases:
        lines.append(f'PHASE1_DIR="$BASE/{dirs["phase1"]}"')
    if 2 in phases:
        lines.append(f'PHASE2_DIR="$BASE/{dirs["phase2"]}"')
    if 3 in phases:
        lines.append(f'BRANCH_NWAY_DIR="$BASE/{dirs["branching"]}"')
        if cfg["phase3"].get("include_legacy"):
            lines.append(f'BRANCH_DIR="$BASE/{dirs["branching_legacy"]}"')
    lines.append(f'LEDGER_DIR="$BASE/{dirs["ledger"]}"')

    return '\n'.join(lines)


def _cfg_scaffold_cde_run(cfg: Dict[str, Any]) -> str:
    """Generate cde_run() helper function."""
    has_venv = bool(cfg.get("python_venv"))
    has_analyzer_dir = bool(cfg.get("cde_analyzer_dir"))

    lines = ['', '# ── HELPERS ─────────────────────────────────────────────────────────────', '']

    if has_venv and has_analyzer_dir:
        lines.extend([
            'cde_run() {',
            '    source "$VENV"',
            '    PYTHONPATH="$CDE_ANALYZER:${PYTHONPATH:-}" python "$CDE_ANALYZER/cde_analyzer.py" "$@"',
            '}',
        ])
    elif has_analyzer_dir:
        lines.extend([
            'cde_run() {',
            '    PYTHONPATH="$CDE_ANALYZER:${PYTHONPATH:-}" python "$CDE_ANALYZER/cde_analyzer.py" "$@"',
            '}',
        ])
    else:
        lines.extend([
            'cde_run() {',
            '    cde-analyzer "$@"',
            '}',
        ])

    return '\n'.join(lines)


def _cfg_scaffold_status(cfg: Dict[str, Any]) -> str:
    """Generate show_status() function."""
    phases = set(cfg["phases"])
    project = cfg["project"]
    ph3 = cfg["phase3"]

    lines = [
        '',
        'show_status() {',
        f'    echo "=== {project} Pipeline Status ==="',
        '    echo ""',
        '    echo "Input: $INPUT_JSON"',
        '    echo "Ledger: $LEDGER_DIR"',
        '    echo ""',
    ]

    if 1 in phases:
        lines.extend([
            '',
            '    # Phase 1',
            '    if [ -f "$PHASE1_DIR/inst_stripped.json" ]; then',
            '        echo "[DONE]    Phase 1 — Instrument stripping complete"',
            '    elif [ -f "$PHASE1_DIR/curated.tsv" ]; then',
            '        echo "[READY]   Phase 1 — Curated, ready to resume stripping"',
            '    elif [ -f "$PHASE1_DIR/needs_review.tsv" ]; then',
            '        local auto_n=$(( $(wc -l < "$PHASE1_DIR/auto_resolved.tsv" 2>/dev/null || echo 1) - 1 ))',
            '        local review_n=$(( $(wc -l < "$PHASE1_DIR/needs_review.tsv") - 1 ))',
            '        echo "[CURATE]  Phase 1 — Curation gate done"',
            '        echo "          Auto-resolved: $auto_n patterns"',
            '        echo "          Needs review:  $review_n patterns"',
            '        echo "          Edit: cde-analyzer curation --edit $PHASE1_DIR/needs_review.tsv"',
            '    elif [ -f "$PHASE1_DIR/coalesced_fields.tsv" ]; then',
            '        echo "[ENRICH]  Phase 1 — Field analysis done, gate pending"',
            '    elif [ -f "$PHASE1_DIR/coalesced.tsv" ]; then',
            '        echo "[PARTIAL] Phase 1 — Coalesced, validation/enrichment pending"',
            '    elif [ -f "$PHASE1_DIR/instruments.tsv" ]; then',
            '        echo "[PARTIAL] Phase 1 — Mining done, discovery/coalesce pending"',
            '    else',
            '        echo "[TODO]    Phase 1 — Not started"',
            '    fi',
        ])

    if 2 in phases:
        lines.extend([
            '',
            '    # Phase 2',
            '    if [ -f "$PHASE2_DIR/final_stripped.json" ]; then',
            '        echo "[DONE]    Phase 2 — Phrase stripping complete"',
            '    elif [ -f "$PHASE2_DIR/curated.tsv" ]; then',
            '        echo "[READY]   Phase 2 — Curated, ready for stripping/branching"',
            '    elif [ -f "$PHASE2_DIR/needs_review.tsv" ]; then',
            '        local auto_n=$(( $(wc -l < "$PHASE2_DIR/auto_resolved.tsv" 2>/dev/null || echo 1) - 1 ))',
            '        local review_n=$(( $(wc -l < "$PHASE2_DIR/needs_review.tsv") - 1 ))',
            '        echo "[CURATE]  Phase 2 — Curation gate done"',
            '        echo "          Auto-resolved: $auto_n patterns"',
            '        echo "          Needs review:  $review_n patterns"',
            '        echo "          Edit: cde-analyzer curation --edit $PHASE2_DIR/needs_review.tsv"',
            '    elif [ -f "$PHASE2_DIR/coalesced_fields.tsv" ]; then',
            '        echo "[ENRICH]  Phase 2 — Field analysis done, gate pending"',
            '    elif [ -f "$PHASE2_DIR/coalesced.tsv" ]; then',
            '        echo "[PARTIAL] Phase 2 — Coalesced, field analysis pending"',
            '    else',
            '        echo "[TODO]    Phase 2 — Not started (requires Phase 1 complete)"',
            '    fi',
        ])

    if 3 in phases:
        lines.extend([
            '',
            '    # Phase 3 (N-way)',
            '    if [ -d "$BRANCH_NWAY_DIR" ] && ls "$BRANCH_NWAY_DIR"/stripped_*.json >/dev/null 2>&1; then',
            '        local nway_count=$(ls "$BRANCH_NWAY_DIR"/stripped_*.json 2>/dev/null | wc -l)',
            '        echo "[DONE]    Phase 3 — N-way branching strip complete ($nway_count variants)"',
            '        echo ""',
            '        echo "Outputs (N-way):"',
            '        ls -lh "$BRANCH_NWAY_DIR"/stripped_*.json 2>/dev/null | awk \'{print "  " $NF " (" $5 ")"}\'',
            '        if [ -f "$BRANCH_NWAY_DIR/strip_report.md" ]; then',
            '            echo "  Report: $BRANCH_NWAY_DIR/strip_report.md"',
            '        fi',
            '    else',
            '        echo "[TODO]    Phase 3 — Not started (requires Phase 2 curated)"',
            '    fi',
        ])
        if ph3.get("include_legacy"):
            lines.extend([
                '',
                '    # Legacy branching output (if exists)',
                '    if [ -d "$BRANCH_DIR" ] && ls "$BRANCH_DIR"/stripped_*.json >/dev/null 2>&1; then',
                '        local legacy_count=$(ls "$BRANCH_DIR"/stripped_*.json 2>/dev/null | wc -l)',
                '        echo "[DONE]    Phase 3 (legacy) — $legacy_count variants in $BRANCH_DIR"',
                '    fi',
            ])

    lines.extend([
        '',
        '    # Ledger status',
        '    if [ -d "$LEDGER_DIR" ]; then',
        '        echo ""',
        '        echo "Curation ledger:"',
        '        for f in "$LEDGER_DIR"/*_decisions.tsv; do',
        '            [ -f "$f" ] && echo "  $(basename "$f"): $(( $(wc -l < "$f") - 1 )) decisions"',
        '        done',
        '    fi',
        '    echo ""',
        '}',
    ])

    return '\n'.join(lines)


def _cfg_scaffold_phase1(cfg: Dict[str, Any]) -> str:
    """Generate run_phase1() with completion guards and resume logic."""
    lines = [
        '',
        '# ── PHASE 1: Instrument Detection ───────────────────────────────────────',
        '',
        'run_phase1() {',
        '    local from_step="${1:-}"',
        '',
        '    echo "=== Phase 1: Instrument Detection ==="',
        '    echo ""',
        '',
        '    # Skip if already complete (unless restarting from a specific step)',
        '    if [ -z "$from_step" ] && [ -f "$PHASE1_DIR/inst_stripped.json" ]; then',
        '        echo "Phase 1 already complete. inst_stripped.json exists."',
        '        echo "  To re-run from a step: $0 phase1 <step_name>"',
        '        echo "  Steps: mine_instruments, discover_abbreviations, discover_verbatim,"',
        '        echo "         coalesce_patterns, validate_subsumption, enrich_fields,"',
        '        echo "         curation_gate, curator_review, finalize_curation,"',
        '        echo "         apply_substitutions, strip_instruments, sanity_check"',
        '        return 0',
        '    fi',
        '',
        '    # Check for curation resume (only when no explicit step)',
        '    if [ -z "$from_step" ] && [ -f "$PHASE1_DIR/.workflow_state.json" ]; then',
        '        if [ -f "$PHASE1_DIR/needs_review.tsv" ] && [ ! -f "$PHASE1_DIR/curated.tsv" ]; then',
        '            echo "Curation gate completed. Review needs_review.tsv, then resume."',
        '            echo "  Edit: cde-analyzer curation --edit $PHASE1_DIR/needs_review.tsv"',
        '            echo "  Resume: cde_run workflow resume --state-file $PHASE1_DIR/.workflow_state.json"',
        '            return 0',
        '        fi',
        '        if [ -f "$PHASE1_DIR/curated.tsv" ]; then',
        '            echo "Resuming Phase 1 after curation..."',
        '            cde_run workflow resume --state-file "$PHASE1_DIR/.workflow_state.json"',
        '            return $?',
        '        fi',
        '    fi',
        '',
        '    # Build run args',
        '    local run_args=(',
        '        workflow run "$WORKFLOWS/instrument_pipeline.yaml"',
        '        --set "input_json=$INPUT_JSON"',
        '        --set "output_dir=$PHASE1_DIR"',
        '        --set "curation_ledger_dir=$LEDGER_DIR"',
        '    )',
        '',
        '    if [ -n "$from_step" ]; then',
        '        echo "Re-running instrument pipeline from step: $from_step"',
        '        run_args+=(--from-step "$from_step")',
        '    else',
        '        echo "Running full instrument pipeline..."',
        '    fi',
        '',
        '    echo "  Input: $INPUT_JSON"',
        '    echo "  Output: $PHASE1_DIR"',
        '    echo "  Ledger: $LEDGER_DIR"',
        '    echo ""',
        '    cde_run "${run_args[@]}"',
        '}',
    ]
    return '\n'.join(lines)


def _cfg_scaffold_phase1_iterate(cfg: Dict[str, Any]) -> str:
    """Generate run_phase1_iterate() with convergence detection."""
    max_rounds = cfg["phase1"].get("iterate_max_rounds", 3)
    lines = [
        '',
        '# ── PHASE 1 ITERATE: Residual Harvesting ────────────────────────────────',
        '',
        'run_phase1_iterate() {',
        f'    local max_rounds="${{1:-{max_rounds}}}"',
        '    local current_patterns="$PHASE1_DIR/curated.tsv"',
        '',
        '    echo "=== Phase 1 Iterative Stripping (max $max_rounds rounds) ==="',
        '    echo ""',
        '',
        '    if [ ! -f "$current_patterns" ]; then',
        '        echo "ERROR: Curated patterns not found: $current_patterns"',
        '        echo "  Run phase1 and curate first."',
        '        exit 1',
        '    fi',
        '',
        '    # Dynamic min-count threshold: k = max(round(N * 0.0005), 5)',
        '    local num_cdes',
        '    num_cdes=$(python3 -c "import json; print(len(json.load(open(\'$INPUT_JSON\'))))")',
        '    local min_count',
        '    min_count=$(python3 -c "print(max(round($num_cdes * 0.0005), 5))")',
        '    echo "  Corpus size: $num_cdes CDEs"',
        '    echo "  Dynamic min-count threshold: $min_count"',
        '    echo ""',
        '',
        '    for round in $(seq 1 "$max_rounds"); do',
        '        echo "--- Iteration $round ---"',
        '',
        '        # Strip with current patterns',
        '        echo "  Stripping with $(wc -l < "$current_patterns") patterns..."',
        '        cde_run strip_phrases -i "$INPUT_JSON" -m CDE \\',
        '            --patterns "$current_patterns,pattern" \\',
        '            -o "$PHASE1_DIR/iter${round}_stripped.json"',
        '',
        '        # Sanity check',
        '        echo "  Running sanity check (min-count=$min_count)..."',
        '        cde_run diagnose_strip -i "$PHASE1_DIR/iter${round}_stripped.json" \\',
        '            -m CDE -o "$PHASE1_DIR/iter${round}_sanity.tsv" \\',
        '            --emit-tinyids --min-count "$min_count"',
        '',
        '        # Harvest residuals',
        '        echo "  Harvesting residuals..."',
        '        cde_run supplementary --harvest-residuals "$PHASE1_DIR/iter${round}_sanity.tsv" \\',
        '            --curated "$current_patterns" \\',
        '            -i "$INPUT_JSON" -m CDE \\',
        '            -o "$PHASE1_DIR/iter${round}_harvest.tsv"',
        '',
        '        # Check convergence',
        '        local new_count',
        '        new_count=$(tail -n +2 "$PHASE1_DIR/iter${round}_harvest.tsv" | wc -l)',
        '        if [ "$new_count" -eq 0 ]; then',
        '            echo "  Converged at round $round (no new residuals)"',
        '            cp "$PHASE1_DIR/iter${round}_stripped.json" "$PHASE1_DIR/inst_stripped.json"',
        '            break',
        '        fi',
        '        echo "  Found $new_count harvestable residuals"',
        '',
        '        # Merge harvested into patterns for next round',
        '        cde_run pattern_util --merge-patterns "$current_patterns" \\',
        '            "$PHASE1_DIR/iter${round}_harvest.tsv" \\',
        '            -o "$PHASE1_DIR/iter${round}_merged.tsv"',
        '',
        '        # Update ledger',
        '        cde_run supplementary --update-ledger "$PHASE1_DIR/iter${round}_harvest.tsv" \\',
        '            --ledger "$PHASE1_DIR/pattern_ledger.tsv" \\',
        '            --source harvested --round "$round" \\',
        '            -o "$PHASE1_DIR/pattern_ledger.tsv"',
        '',
        '        current_patterns="$PHASE1_DIR/iter${round}_merged.tsv"',
        '',
        '        # If last round, copy the final stripped output',
        '        if [ "$round" -eq "$max_rounds" ]; then',
        '            echo "  Max rounds reached. Using round $round output."',
        '            cp "$PHASE1_DIR/iter${round}_stripped.json" "$PHASE1_DIR/inst_stripped.json"',
        '        fi',
        '    done',
        '',
        '    echo ""',
        '    echo "=== Iterative stripping complete ==="',
        '    echo "  Final output: $PHASE1_DIR/inst_stripped.json"',
        '    if [ -f "$PHASE1_DIR/pattern_ledger.tsv" ]; then',
        '        echo "  Ledger: $PHASE1_DIR/pattern_ledger.tsv"',
        '    fi',
        '}',
    ]
    return '\n'.join(lines)


def _cfg_scaffold_phase2(cfg: Dict[str, Any]) -> str:
    """Generate run_phase2() with completion guards and resume logic."""
    ph2 = cfg["phase2"]
    config_file = ph2.get("config_file", "")

    lines = [
        '',
        '# ── PHASE 2: Phrase Mining ──────────────────────────────────────────────',
        '',
        'run_phase2() {',
        '    echo "=== Phase 2: Phrase Mining ==="',
        '    echo ""',
        '',
        '    if [ ! -f "$PHASE1_DIR/inst_stripped.json" ]; then',
        '        echo "ERROR: Phase 1 not complete. Run \'phase1\' first."',
        '        exit 1',
        '    fi',
        '',
        '    # Check for curation resume',
        '    if [ -f "$PHASE2_DIR/.workflow_state.json" ]; then',
        '        if [ -f "$PHASE2_DIR/needs_review.tsv" ] && [ ! -f "$PHASE2_DIR/curated.tsv" ]; then',
        '            echo "Curation gate completed. Review needs_review.tsv, then resume."',
        '            echo "  Edit: cde-analyzer curation --edit $PHASE2_DIR/needs_review.tsv"',
        '            echo "  Resume: cde_run workflow resume --state-file $PHASE2_DIR/.workflow_state.json"',
        '            return 0',
        '        fi',
        '        if [ -f "$PHASE2_DIR/curated.tsv" ] && [ ! -f "$PHASE2_DIR/final_stripped.json" ]; then',
        '            echo "Resuming Phase 2 after curation..."',
        '            cde_run workflow resume --state-file "$PHASE2_DIR/.workflow_state.json"',
        '            return $?',
        '        fi',
        '    fi',
        '',
        '    if [ -f "$PHASE2_DIR/final_stripped.json" ]; then',
        '        echo "Phase 2 already complete. final_stripped.json exists."',
        '        return 0',
        '    fi',
        '',
    ]

    if config_file:
        lines.extend([
            f'    # Parameters managed in {config_file}',
            f'    # (auto-loaded from output_dir by workflow engine)',
        ])

    lines.extend([
        '    echo "Running phrase pipeline..."',
        '    echo "  Input: $PHASE1_DIR/inst_stripped.json"',
        '    echo "  Output: $PHASE2_DIR"',
        '    echo "  Ledger: $LEDGER_DIR"',
        '    echo ""',
        '    cde_run workflow run "$WORKFLOWS/phrase_pipeline.yaml" \\',
        '        --set "input_json=$PHASE1_DIR/inst_stripped.json" \\',
        '        --set "output_dir=$PHASE2_DIR" \\',
        '        --set "curation_ledger_dir=$LEDGER_DIR"',
        '}',
    ])

    return '\n'.join(lines)


def _cfg_scaffold_prepare_strip(cfg: Dict[str, Any]) -> str:
    """Generate _prepare_strip_patterns() and _prepare_branching_input()."""
    lines = [
        '',
        '# ── INTER-PHASE: Prepare Strip Patterns ─────────────────────────────────',
        '',
        '_prepare_strip_patterns() {',
        '    STRIP_BASE="$PHASE1_DIR/inst_patterns"',
        '    if [ ! -f "${STRIP_BASE}_full.tsv" ]; then',
        '        HIERARCHY_TSV="$PHASE1_DIR/hierarchy.tsv"',
        '        echo "Assigning group hierarchy to instrument patterns..."',
        '        cde_run instrument_util --group-hierarchy "$PHASE1_DIR/curated.tsv" \\',
        '            -o "$HIERARCHY_TSV"',
        '',
        '        echo "Generating instrument strip pattern files..."',
        '        cde_run instrument_util --generate-strip-patterns "$HIERARCHY_TSV" \\',
        '            -o "$STRIP_BASE"',
        '    fi',
        '}',
        '',
        '_prepare_branching_input() {',
        '    local branching_input="$BRANCH_NWAY_DIR/branching_input.json"',
        '    if [ -f "$branching_input" ]; then',
        '        echo "  Branching input already exists: $branching_input"',
        '        echo "$branching_input"',
        '        return',
        '    fi',
        '',
        '    mkdir -p "$BRANCH_NWAY_DIR"',
        '',
        '    # Apply Phase 2 substitutions (if any) to original input JSON',
        '    local sub_patterns="$PHASE2_DIR/substitute_patterns.tsv"',
        '    if [ -f "$sub_patterns" ] && [ "$(wc -l < "$sub_patterns")" -gt 1 ]; then',
        '        echo "  Applying Phase 2 substitutions to input JSON..."',
        '        cde_run strip_phrases \\',
        '            -i "$INPUT_JSON" \\',
        '            -o "$branching_input" \\',
        '            --patterns "$sub_patterns,pattern" \\',
        '            --no-expand-anchors',
        '    else',
        '        echo "  No substitutions to apply — copying input JSON"',
        '        cp "$INPUT_JSON" "$branching_input"',
        '    fi',
        '    echo "$branching_input"',
        '}',
    ]
    return '\n'.join(lines)


def _cfg_scaffold_phase3(cfg: Dict[str, Any]) -> str:
    """Generate run_phase3() for N-way branching strip."""
    lines = [
        '',
        '# ── PHASE 3: Branching Strip (N-way) ───────────────────────────────────',
        '',
        'run_phase3() {',
        '    echo "=== Phase 3: 7-Way Branching Strip (N-way) ==="',
        '    echo ""',
        '',
        '    if [ ! -f "$PHASE1_DIR/curated.tsv" ]; then',
        '        echo "ERROR: Instrument curation not done ($PHASE1_DIR/curated.tsv missing)"',
        '        exit 1',
        '    fi',
        '    if [ ! -f "$PHASE2_DIR/curated.tsv" ]; then',
        '        echo "ERROR: Phrase curation not done ($PHASE2_DIR/curated.tsv missing)"',
        '        exit 1',
        '    fi',
        '',
        '    _prepare_strip_patterns',
        '    STRIP_BASE="$PHASE1_DIR/inst_patterns"',
        '',
        '    local strip_input',
        '    strip_input=$(_prepare_branching_input)',
        '',
        '    echo "Running 7-way N-way branching strip..."',
        '    echo "  Input:    $strip_input"',
        '    echo "  Output:   $BRANCH_NWAY_DIR"',
        '    echo "  Patterns: inst=${STRIP_BASE}_{full,sub}.tsv"',
        '    echo "            phrase=$PHASE2_DIR/curated.tsv"',
        '    echo ""',
        '    cde_run workflow run "$WORKFLOWS/branching_strip_nway.yaml" \\',
        '        --set "input_json=$strip_input" \\',
        '        --set "output_dir=$BRANCH_NWAY_DIR" \\',
        '        --set "inst_patterns_base=$STRIP_BASE" \\',
        '        --set "phrase_patterns=$PHASE2_DIR/curated.tsv"',
        '',
        '    echo ""',
        '    echo "=== Branching strip complete ==="',
        '    echo "Outputs:"',
        '    ls -lh "$BRANCH_NWAY_DIR"/stripped_*.json 2>/dev/null',
        '}',
    ]
    return '\n'.join(lines)


def _cfg_scaffold_phase3_legacy(cfg: Dict[str, Any]) -> str:
    """Generate run_phase3_legacy() for legacy branching strip."""
    lines = [
        '',
        '# ── PHASE 3: Branching Strip (Legacy) ──────────────────────────────────',
        '',
        'run_phase3_legacy() {',
        '    echo "=== Phase 3: Branching Strip (Legacy 10-step) ==="',
        '    echo ""',
        '',
        '    if [ ! -f "$PHASE1_DIR/curated.tsv" ]; then',
        '        echo "ERROR: Instrument curation not done ($PHASE1_DIR/curated.tsv missing)"',
        '        exit 1',
        '    fi',
        '    if [ ! -f "$PHASE2_DIR/curated.tsv" ]; then',
        '        echo "ERROR: Phrase curation not done ($PHASE2_DIR/curated.tsv missing)"',
        '        exit 1',
        '    fi',
        '',
        '    _prepare_strip_patterns',
        '    STRIP_BASE="$PHASE1_DIR/inst_patterns"',
        '',
        '    echo "Running legacy branching strip..."',
        '    cde_run workflow run "$WORKFLOWS/branching_strip.yaml" \\',
        '        --set "input_json=$INPUT_JSON" \\',
        '        --set "output_dir=$BRANCH_DIR" \\',
        '        --set "inst_patterns_base=$STRIP_BASE" \\',
        '        --set "phrase_patterns=$PHASE2_DIR/curated.tsv"',
        '',
        '    echo ""',
        '    echo "=== Legacy branching strip complete ==="',
        '    echo "Outputs:"',
        '    ls -lh "$BRANCH_DIR"/stripped_*.json 2>/dev/null',
        '}',
    ]
    return '\n'.join(lines)


def _cfg_scaffold_dispatch(cfg: Dict[str, Any]) -> str:
    """Generate case dispatch block."""
    phases = set(cfg["phases"])
    ph1 = cfg["phase1"]
    ph3 = cfg["phase3"]

    lines = [
        '',
        '# ── DISPATCH ────────────────────────────────────────────────────────────',
        '',
        'case "${1:-status}" in',
    ]
    if 1 in phases:
        lines.append('    phase1)          run_phase1 "${2:-}" ;;')
        if ph1.get("with_iterate"):
            lines.append('    phase1_iterate)  run_phase1_iterate "${2:-3}" ;;')
    if 2 in phases:
        lines.append('    phase2)          run_phase2 ;;')
    if 3 in phases:
        lines.append('    phase3)          run_phase3 ;;')
        if ph3.get("include_legacy"):
            lines.append('    phase3_legacy)   run_phase3_legacy ;;')
    lines.append('    status)          show_status ;;')

    # Build usage line
    targets = []
    if 1 in phases:
        targets.append('phase1')
        if ph1.get("with_iterate"):
            targets.append('phase1_iterate')
    if 2 in phases:
        targets.append('phase2')
    if 3 in phases:
        targets.append('phase3')
        if ph3.get("include_legacy"):
            targets.append('phase3_legacy')
    targets.append('status')
    targets_str = '|'.join(targets)

    lines.extend([
        '    *)',
        f'        echo "Usage: $0 {{{targets_str}}}"',
    ])

    # Add per-target help
    if 1 in phases:
        lines.append('        echo "  phase1 [step]          Run/resume instrument detection"')
        if ph1.get("with_iterate"):
            lines.append('        echo "  phase1_iterate [N]     Iterative strip-harvest loop (default: 3 rounds)"')
    if 2 in phases:
        lines.append('        echo "  phase2                 Run phrase mining"')
    if 3 in phases:
        lines.append('        echo "  phase3                 Run N-way branching strip"')
        if ph3.get("include_legacy"):
            lines.append('        echo "  phase3_legacy          Run legacy branching strip"')
    lines.append('        echo "  status                 Show pipeline state"')

    lines.extend([
        '        exit 1',
        '        ;;',
        'esac',
    ])

    return '\n'.join(lines)


def _scaffold_from_config(config_path: str, output_path: Optional[str],
                          force: bool) -> int:
    """Generate full-featured pipeline script from a YAML config file."""
    cfg = _load_pipeline_config(config_path)
    phases = set(cfg["phases"])
    is_windows = sys.platform == "win32"

    # Determine output path
    if output_path:
        script_path = Path(os.path.abspath(output_path))
    else:
        # Default: same directory as config file
        script_path = Path(config_path).parent / "run_pipeline.sh"

    if script_path.exists() and not force:
        print(f"Error: Script already exists: {script_path}")
        print("Use --force to overwrite.")
        return 1

    # Build sections
    sections = [
        _cfg_scaffold_header(cfg),
        _cfg_scaffold_parameters(cfg, is_windows),
        _cfg_scaffold_cde_run(cfg),
    ]

    if cfg["features"].get("status_dashboard", True):
        sections.append(_cfg_scaffold_status(cfg))

    if 1 in phases:
        sections.append(_cfg_scaffold_phase1(cfg))
        if cfg["phase1"].get("with_iterate"):
            sections.append(_cfg_scaffold_phase1_iterate(cfg))

    if 3 in phases and 1 in phases:
        sections.append(_cfg_scaffold_prepare_strip(cfg))

    if 2 in phases:
        sections.append(_cfg_scaffold_phase2(cfg))

    if 3 in phases:
        sections.append(_cfg_scaffold_phase3(cfg))
        if cfg["phase3"].get("include_legacy"):
            sections.append(_cfg_scaffold_phase3_legacy(cfg))

    sections.append(_cfg_scaffold_dispatch(cfg))
    sections.append('')  # trailing newline

    # Write with Unix line endings
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write('\n'.join(sections))

    try:
        script_path.chmod(script_path.stat().st_mode | 0o755)
    except OSError:
        pass

    print(f"Generated pipeline script: {script_path}")
    print(f"  Project: {cfg['project']}")
    print(f"  Phases: {sorted(phases)}")
    print(f"  Config: {config_path}")
    features = []
    if cfg["features"].get("status_dashboard"):
        features.append("status dashboard")
    if cfg["features"].get("completion_guards"):
        features.append("completion guards")
    if cfg["features"].get("curation_resume"):
        features.append("curation resume")
    if cfg["phase1"].get("with_iterate"):
        features.append("iterative harvesting")
    if cfg["phase3"].get("include_legacy"):
        features.append("legacy branching")
    if features:
        print(f"  Features: {', '.join(features)}")

    print(f"\nNext steps:")
    if is_windows:
        wsl_script = _win_to_wsl_path(str(script_path))
        print(f"  1. In WSL: bash {wsl_script} status")
    else:
        print(f"  1. Run: ./{script_path.name} status")

    return 0


def cmd_scaffold(args) -> int:
    """Handle 'workflow scaffold' command — generate pipeline orchestration script."""
    # Config-driven mode
    from_config = getattr(args, "from_config", None)
    if from_config:
        return _scaffold_from_config(
            from_config,
            getattr(args, "output", None),
            getattr(args, "force", False),
        )

    # Legacy CLI-arg mode
    project_name = args.project_name
    if not project_name:
        print("Error: project_name is required (or use --from-config)")
        return 1

    if not args.input_json:
        print("Error: --input-json is required (or use --from-config)")
        return 1

    input_json = os.path.abspath(args.input_json)
    output_dir = os.path.abspath(args.output_dir)
    cde_command = args.cde_command
    phases = {int(p.strip()) for p in args.phases.split(",")}
    with_iterate = args.with_iterate
    force = args.force
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Validate phases
    valid_phases = {1, 2, 3}
    invalid = phases - valid_phases
    if invalid:
        print(f"Error: Invalid phase numbers: {invalid}. Valid: 1, 2, 3")
        return 1

    # Determine output path
    if args.output:
        script_path = Path(os.path.abspath(args.output))
    else:
        script_path = Path(output_dir) / "run_pipeline.sh"

    if script_path.exists() and not force:
        print(f"Error: Script already exists: {script_path}")
        print("Use --force to overwrite.")
        return 1

    # Resolve workflows directory
    workflows_dir = str(get_builtin_workflows_dir())

    # Windows → WSL path conversion
    is_windows = sys.platform == "win32"
    if is_windows:
        input_json = _win_to_wsl_path(input_json)
        output_dir = _win_to_wsl_path(output_dir)
        workflows_dir = _win_to_wsl_path(workflows_dir)

    # Build script sections
    sections = [
        _scaffold_header(project_name, timestamp, is_windows, phases, with_iterate),
        _scaffold_parameters(project_name, cde_command, workflows_dir,
                             input_json, output_dir, phases),
        _scaffold_derived_paths(phases),
        _scaffold_helpers(),
    ]

    if 1 in phases:
        sections.append(_scaffold_phase1(with_iterate))
        if with_iterate:
            sections.append(_scaffold_phase1_iterate())

    if 3 in phases and 1 in phases:
        sections.append(_scaffold_prepare_strip())

    if 2 in phases:
        sections.append(_scaffold_phase2())

    if 3 in phases:
        sections.append(_scaffold_phase3())

    sections.append(_scaffold_dispatch(phases, with_iterate))
    sections.append('')  # trailing newline

    # Write script with Unix line endings
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write('\n'.join(sections))

    # Set executable permission (no-op on Windows, useful if file is on WSL mount)
    try:
        script_path.chmod(script_path.stat().st_mode | 0o755)
    except OSError:
        pass  # Windows may not support chmod

    # Summary
    print(f"Generated pipeline script: {script_path}")
    print(f"  Project: {project_name}")
    print(f"  Phases: {sorted(phases)}")
    if with_iterate:
        print(f"  Includes: iterative residual harvesting")
    print(f"\nNext steps:")
    print(f"  1. Review and customize parameters in {script_path.name}")

    if is_windows:
        wsl_script = _win_to_wsl_path(str(script_path))
        print(f"  2. In WSL: bash {wsl_script} phase1")
    else:
        print(f"  2. Run: ./{script_path.name} phase1")

    return 0


def run_action(args) -> int:
    """Main entry point for workflow action."""
    command = getattr(args, "workflow_command", None)

    if not command:
        print("Usage: cde-analyzer workflow <command>")
        print("\nCommands:")
        print("  list      List available workflow templates")
        print("  copy      Copy a template to current directory for customization")
        print("  scaffold  Generate project-specific pipeline orchestration script")
        print("  configure Generate workflow for specific strip variants")
        print("  run       Execute a workflow from YAML file")
        print("  resume    Resume workflow after checkpoint")
        print("  status    Show workflow execution status")
        print("\nRecommended workflow:")
        print("  1. List templates:    workflow list")
        print("  2. Copy to work dir:  workflow copy <name>")
        print("  3. Edit as needed")
        print("  4. Run:               workflow run ./<name>.yaml")
        print("\nRun 'cde-analyzer workflow <command> --help' for details.")
        return 1

    if command == "run":
        return cmd_run(args)
    elif command == "resume":
        return cmd_resume(args)
    elif command == "status":
        return cmd_status(args)
    elif command == "list":
        return cmd_list(args)
    elif command == "copy":
        return cmd_copy(args)
    elif command == "scaffold":
        return cmd_scaffold(args)
    elif command == "configure":
        return cmd_configure(args)
    else:
        print(f"Unknown command: {command}")
        return 1
