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
    # List available workflow templates
    cde-analyzer workflow list

    # Copy a template to current directory for customization
    cde-analyzer workflow copy instrument_detection
    cde-analyzer workflow copy instrument_detection --as my_pipeline.yaml

    # Run workflow (after customizing if needed)
    cde-analyzer workflow run ./instrument_detection.yaml [--set key=value]
    cde-analyzer workflow resume [--state-file FILE]
    cde-analyzer workflow status [--state-file FILE]

Recommended workflow:
    1. List available templates:     workflow list
    2. Copy template to work dir:    workflow copy <name>
    3. Edit workflow variables/args as needed
    4. Run your customized workflow: workflow run ./<name>.yaml
"""
from argparse import ArgumentParser

help_text = "YAML-based workflow orchestrator for CDE analysis pipelines"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Inherit formatter (ArgumentDefaultsHelpFormatter) from parent parser
    _fmt = subparser.formatter_class

    # Create subcommands
    workflow_subparsers = subparser.add_subparsers(
        dest="workflow_command",
        title="workflow commands",
        description="Available workflow commands"
    )

    # ===== RUN command =====
    run_parser = workflow_subparsers.add_parser(
        "run",
        help="Execute a workflow from YAML file",
        formatter_class=_fmt,
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
        help="Directory to store workflow state (auto: workflow's output_dir or current dir)"
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
        help="Resume workflow after checkpoint",
        formatter_class=_fmt,
    )
    resume_parser.add_argument(
        "--state-file",
        type=str,
        default=".workflow_state.json",
        help="Path to workflow state file"
    )
    resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview remaining steps without executing"
    )

    # ===== STATUS command =====
    status_parser = workflow_subparsers.add_parser(
        "status",
        help="Show workflow execution status",
        formatter_class=_fmt,
    )
    status_parser.add_argument(
        "--state-file",
        type=str,
        default=".workflow_state.json",
        help="Path to workflow state file"
    )
    status_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed step information"
    )

    # ===== LIST command =====
    list_parser = workflow_subparsers.add_parser(
        "list",
        help="List available workflow templates",
        formatter_class=_fmt,
    )
    list_parser.add_argument(
        "--dir",
        type=str,
        default="workflows",
        help="Directory to search for workflow files"
    )

    # ===== COPY command =====
    copy_parser = workflow_subparsers.add_parser(
        "copy",
        help="Copy a workflow template to current directory for customization",
        formatter_class=_fmt,
    )
    copy_parser.add_argument(
        "workflow_name",
        help="Name of workflow to copy (e.g., 'instrument_detection' or 'instrument_detection.yaml')"
    )
    copy_parser.add_argument(
        "--as", "-a",
        dest="output_name",
        type=str,
        help="Output filename (auto: same as source)"
    )
    copy_parser.add_argument(
        "--dest", "-d",
        type=str,
        default=".",
        help="Destination directory"
    )
    copy_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing file without prompting"
    )

    # ===== SCAFFOLD command =====
    scaffold_parser = workflow_subparsers.add_parser(
        "scaffold",
        help="Generate a project-specific pipeline orchestration script",
        formatter_class=_fmt,
    )
    scaffold_parser.add_argument(
        "project_name",
        help="Short project name for header/directories (e.g., 'allcde01')"
    )
    scaffold_parser.add_argument(
        "--input-json", "-i",
        required=True,
        help="Path to raw CDE JSON input file"
    )
    scaffold_parser.add_argument(
        "--output-dir", "-d",
        default=".",
        help="Base output directory for all phases"
    )
    scaffold_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Script output path (auto: {output_dir}/run_pipeline.sh)"
    )
    scaffold_parser.add_argument(
        "--cde-command",
        default="cde-analyzer",
        help="How to invoke cde-analyzer"
    )
    scaffold_parser.add_argument(
        "--phases",
        default="1,2,3",
        help="Comma-separated phase numbers to include"
    )
    scaffold_parser.add_argument(
        "--with-iterate",
        action="store_true",
        help="Include iterative residual harvesting loop for Phase 1"
    )
    scaffold_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing script without prompting"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
