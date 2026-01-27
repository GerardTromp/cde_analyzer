#
# File: actions/workflow/cli.py
#
"""
Workflow - YAML-based workflow orchestrator for CDE analysis pipelines.

Executes sequential workflows defined in YAML files with:
- Variable substitution (environment → YAML defaults → CLI overrides)
- Human checkpoints for curator review
- Resume capability after checkpoints
- Dry-run mode for preview

Usage:
    cde_analyzer workflow run <workflow.yaml> [--set key=value]
    cde_analyzer workflow resume [--state-file FILE]
    cde_analyzer workflow status [--state-file FILE]

Example workflow.yaml:
    name: instrument_stripping
    variables:
      input_json: "${CDE_INPUT:-cdes.json}"
      output_dir: "./phase1_output"
    steps:
      - name: mine_instruments
        action: instrument_miner
        args:
          input: "${input_json}"
          output: "${output_dir}/"
          detect_families: true
      - name: curator_review
        checkpoint: true
        message: "Review output, then run: cde_analyzer workflow resume"
"""
from argparse import ArgumentParser

help_text = "YAML-based workflow orchestrator for CDE analysis pipelines"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Create subcommands
    workflow_subparsers = subparser.add_subparsers(
        dest="workflow_command",
        title="workflow commands",
        description="Available workflow commands"
    )

    # ===== RUN command =====
    run_parser = workflow_subparsers.add_parser(
        "run",
        help="Execute a workflow from YAML file"
    )
    run_parser.add_argument(
        "workflow_file",
        help="Path to workflow YAML file"
    )
    run_parser.add_argument(
        "--set", "-s",
        action="append",
        dest="overrides",
        metavar="KEY=VALUE",
        help="Override workflow variable (can be specified multiple times)"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview workflow without executing (show resolved commands)"
    )
    run_parser.add_argument(
        "--state-dir",
        type=str,
        help="Directory to store workflow state (default: workflow's output_dir or current dir)"
    )
    run_parser.add_argument(
        "--from-step",
        type=str,
        metavar="STEP_NAME",
        help="Start execution from specific step (skip earlier steps)"
    )

    # ===== RESUME command =====
    resume_parser = workflow_subparsers.add_parser(
        "resume",
        help="Resume workflow after checkpoint"
    )
    resume_parser.add_argument(
        "--state-file",
        type=str,
        default=".workflow_state.json",
        help="Path to workflow state file (default: .workflow_state.json)"
    )
    resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview remaining steps without executing"
    )

    # ===== STATUS command =====
    status_parser = workflow_subparsers.add_parser(
        "status",
        help="Show workflow execution status"
    )
    status_parser.add_argument(
        "--state-file",
        type=str,
        default=".workflow_state.json",
        help="Path to workflow state file (default: .workflow_state.json)"
    )
    status_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed step information"
    )

    # ===== LIST command =====
    list_parser = workflow_subparsers.add_parser(
        "list",
        help="List available workflow files"
    )
    list_parser.add_argument(
        "--dir",
        type=str,
        default="workflows",
        help="Directory to search for workflow files (default: workflows/)"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
