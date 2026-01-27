#
# File: actions/workflow/run.py
#
"""
Workflow runner implementation.

Executes YAML-defined workflows with:
- Sequential step execution
- Variable resolution (env → yaml → CLI)
- Checkpoint/resume capability
- State persistence
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


def resolve_variables(text: str, variables: Dict[str, Any]) -> str:
    """
    Resolve variable references in text.

    Supports:
    - ${VAR} - simple variable reference
    - ${VAR:-default} - variable with default value
    - Environment variable fallback
    """
    if not isinstance(text, str):
        return text

    def replace_var(match):
        var_expr = match.group(1)

        # Check for default value syntax: ${VAR:-default}
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
        else:
            var_name = var_expr
            default = None

        # Resolution order: variables dict → environment → default
        if var_name in variables:
            return str(variables[var_name])
        elif var_name in os.environ:
            return os.environ[var_name]
        elif default is not None:
            return default
        else:
            logger.warning(f"Unresolved variable: ${{{var_name}}}")
            return match.group(0)  # Keep original if unresolved

    # Match ${...} patterns
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, text)


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

        if isinstance(value, bool):
            if value:
                cli_args.append(f"--{cli_key}")
        elif isinstance(value, list):
            for item in value:
                cli_args.append(f"--{cli_key}")
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
    print(f"Command: cde_analyzer {action} {' '.join(cli_args)}")
    print(f"{'='*70}")

    if dry_run:
        print("[DRY RUN] Would execute above command")
        return {"status": "skipped", "dry_run": True}

    # Import and execute the action
    try:
        # Dynamic import of action module
        action_module = __import__(
            f"actions.{action}.run",
            fromlist=["run_action"]
        )
        run_action = action_module.run_action

        # Build args namespace
        import argparse
        args_ns = argparse.Namespace(**resolved_args)

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
    from_step: Optional[str] = None
) -> int:
    """
    Execute workflow steps sequentially.

    Returns 0 on success/checkpoint, non-zero on failure.
    """
    steps = workflow.get("steps", [])

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
            message = step.get("message", "Workflow paused for human review")
            message = resolve_variables(message, variables)

            print(f"\n{'#'*70}")
            print(f"# CHECKPOINT: {step_name}")
            print(f"#")
            for line in message.strip().split("\n"):
                print(f"#   {line}")
            print(f"#")
            print(f"# Resume with: cde_analyzer workflow resume")
            print(f"{'#'*70}")

            # Save state (skip in dry-run mode)
            if not dry_run:
                state.current_step_index = i + 1  # Next step after checkpoint
                state.status = "paused"
                state.paused_at = datetime.now().isoformat()
                state.checkpoint_message = message
                state.save()

            return 0  # Success - checkpoint reached

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

    # Build variables: workflow defaults + CLI overrides
    variables = dict(workflow.get("variables", {}))

    # Apply CLI overrides
    if args.overrides:
        for override in args.overrides:
            if "=" not in override:
                print(f"Error: Invalid override format '{override}', expected KEY=VALUE")
                return 1
            key, value = override.split("=", 1)
            variables[key] = value

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

    # Run workflow
    return run_workflow(
        workflow,
        workflow_path,
        variables,
        state,
        dry_run=args.dry_run,
        from_step=getattr(args, "from_step", None)
    )


def cmd_resume(args) -> int:
    """Handle 'workflow resume' command."""
    state = WorkflowState(args.state_file)

    if not state.load():
        print(f"Error: No workflow state found at {args.state_file}")
        print("Run a workflow first with: cde_analyzer workflow run <workflow.yaml>")
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


def cmd_list(args) -> int:
    """Handle 'workflow list' command."""
    search_dir = Path(args.dir)

    if not search_dir.exists():
        print(f"Directory not found: {search_dir}")
        print(f"Create {search_dir}/ and add workflow YAML files.")
        return 1

    yaml_files = list(search_dir.glob("*.yaml")) + list(search_dir.glob("*.yml"))

    if not yaml_files:
        print(f"No workflow files found in {search_dir}/")
        return 0

    print(f"Available workflows in {search_dir}/:\n")
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

    return 0


def run_action(args) -> int:
    """Main entry point for workflow action."""
    command = getattr(args, "workflow_command", None)

    if not command:
        print("Usage: cde_analyzer workflow <command>")
        print("\nCommands:")
        print("  run      Execute a workflow from YAML file")
        print("  resume   Resume workflow after checkpoint")
        print("  status   Show workflow execution status")
        print("  list     List available workflow files")
        print("\nRun 'cde_analyzer workflow <command> --help' for details.")
        return 1

    if command == "run":
        return cmd_run(args)
    elif command == "resume":
        return cmd_resume(args)
    elif command == "status":
        return cmd_status(args)
    elif command == "list":
        return cmd_list(args)
    else:
        print(f"Unknown command: {command}")
        return 1
