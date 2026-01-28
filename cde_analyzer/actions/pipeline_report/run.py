#
# File: actions/pipeline_report/run.py
#
"""
Pipeline Report - Generate markdown summary reports for workflow execution.
"""
import json
import logging
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.file_utils import graceful_interrupt
from utils.pattern_tsv_utils import find_column_index

logger = logging.getLogger(__name__)

# Phase definitions for instrument detection pipeline
PHASES = {
    1: {
        "name": "Initial Mining",
        "steps": ["mine_instruments", "expand_abbreviations", "discover_abbreviations", "expansion_review"],
        "outputs": ["instruments.tsv", "instruments_verbatim.tsv", "instrument_families.tsv", "abbrev_patterns.tsv"],
        "description": "Extract instrument patterns from 'as part of' phrases and discover abbreviation-based designations."
    },
    2: {
        "name": "Discovery & Coalesce",
        "steps": ["discover_verbatim", "coalesce_patterns", "recall_phase2", "initial_review"],
        "outputs": ["discovered_instruments.tsv", "coalesced_instruments.tsv", "subsumption_report.tsv", "recall_phase2.tsv"],
        "description": "Discover verbatim pattern occurrences and reduce via subsumption analysis."
    },
    3: {
        "name": "Family Analysis & Final Coalesce",
        "steps": ["family_discovery", "discover_abbreviations_final", "final_discover", "final_coalesce", "recall_phase3", "final_review"],
        "outputs": ["final_discovered.tsv", "final_coalesced.tsv", "final_subsumption.tsv", "recall_phase3.tsv", "recall_report.md"],
        "description": "Group patterns into families and perform final discovery with curated patterns."
    },
    4: {
        "name": "Stripping & Verification",
        "steps": ["strip_instruments", "sanity_check", "pipeline_complete"],
        "outputs": ["no_instruments.json", "strip_trace.tsv", "sanity_check.tsv"],
        "description": "Strip detected instruments from CDE text and verify completeness."
    },
}


def load_workflow_state(state_file: str) -> Optional[Dict]:
    """Load workflow state from JSON file."""
    path = Path(state_file)
    if not path.exists():
        logger.error(f"State file not found: {state_file}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in state file: {e}")
        return None


def count_tsv_rows(tsv_path: str, skip_comments: bool = True) -> Tuple[int, int]:
    """
    Count rows in TSV file.

    Returns (data_rows, total_rows).
    """
    path = Path(tsv_path)
    if not path.exists():
        return 0, 0

    total = 0
    data = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                total += 1
                stripped = line.strip()
                if stripped and not (skip_comments and stripped.startswith("#")):
                    if total > 1:  # Skip header
                        data += 1
    except Exception as e:
        logger.warning(f"Error reading {tsv_path}: {e}")
        return 0, 0

    return data, total


def count_unique_tinyids(tsv_path: str, column_name: str = "tinyIds") -> int:
    """Count unique tinyIds in a TSV file column."""
    path = Path(tsv_path)
    if not path.exists():
        return 0

    unique_ids: Set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            try:
                col_idx = find_column_index(header, column_name)
            except ValueError:
                return 0

            for line in f:
                parts = line.strip().split("\t")
                if len(parts) > col_idx:
                    # Handle space or pipe separated IDs
                    ids_str = parts[col_idx]
                    for sep in [" ", "|", ","]:
                        if sep in ids_str:
                            unique_ids.update(id.strip() for id in ids_str.split(sep) if id.strip())
                            break
                    else:
                        if ids_str.strip():
                            unique_ids.add(ids_str.strip())
    except Exception as e:
        logger.warning(f"Error counting tinyIds in {tsv_path}: {e}")
        return 0

    return len(unique_ids)


def get_file_metrics(output_dir: str, filename: str) -> Dict[str, Any]:
    """Get metrics for a specific output file."""
    path = Path(output_dir) / filename
    if not path.exists():
        return {"exists": False, "path": str(path)}

    metrics: Dict[str, Any] = {
        "exists": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
    }

    if filename.endswith(".tsv"):
        data_rows, total_rows = count_tsv_rows(str(path))
        metrics["data_rows"] = data_rows
        metrics["total_rows"] = total_rows
        metrics["unique_tinyids"] = count_unique_tinyids(str(path))
    elif filename.endswith(".json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    metrics["record_count"] = len(data)
                elif isinstance(data, dict) and "data" in data:
                    metrics["record_count"] = len(data["data"])
        except Exception:
            pass

    return metrics


def determine_phase_from_steps(completed_steps: List[str]) -> int:
    """Determine current phase based on completed steps."""
    step_names = set(completed_steps)

    for phase_num in [4, 3, 2, 1]:
        phase_steps = set(PHASES[phase_num]["steps"])
        if phase_steps & step_names:
            return phase_num

    return 1


def generate_phase_section(
    phase_num: int,
    state: Optional[Dict],
    output_dir: str,
) -> List[str]:
    """Generate markdown section for a single phase."""
    lines = []
    phase = PHASES[phase_num]

    lines.append(f"### Phase {phase_num}: {phase['name']}")
    lines.append("")
    lines.append(f"*{phase['description']}*")
    lines.append("")

    # Steps status
    completed_steps = set()
    if state:
        completed_steps = {s["name"] for s in state.get("completed_steps", [])}

    lines.append("**Steps:**")
    lines.append("")
    for step in phase["steps"]:
        if step in completed_steps:
            status = "Completed"
            icon = "- [x]"
        else:
            status = "Pending"
            icon = "- [ ]"
        lines.append(f"{icon} `{step}` ({status})")
    lines.append("")

    # Output files with metrics
    lines.append("**Outputs:**")
    lines.append("")
    lines.append("| File | Status | Rows | Unique tinyIds |")
    lines.append("|------|--------|-----:|---------------:|")

    for filename in phase["outputs"]:
        metrics = get_file_metrics(output_dir, filename)
        if metrics["exists"]:
            rows = metrics.get("data_rows", metrics.get("record_count", "-"))
            tinyids = metrics.get("unique_tinyids", "-")
            status = "Found"
        else:
            rows = "-"
            tinyids = "-"
            status = "Missing"

        lines.append(f"| `{filename}` | {status} | {rows} | {tinyids} |")
    lines.append("")

    return lines


def generate_executive_summary(
    state: Optional[Dict],
    output_dir: str,
    current_phase: int,
) -> List[str]:
    """Generate executive summary section."""
    lines = []

    lines.append("## Executive Summary")
    lines.append("")

    # Pipeline status
    if state:
        status = state.get("status", "unknown")
        status_display = {
            "not_started": "Not Started",
            "running": "Running",
            "paused": "Paused at Checkpoint",
            "completed": "Completed",
            "failed": "Failed",
        }.get(status, status.title())

        lines.append(f"**Pipeline Status**: {status_display}")
        lines.append(f"**Current Phase**: Phase {current_phase} - {PHASES[current_phase]['name']}")

        completed_count = len(state.get("completed_steps", []))
        total_steps = sum(len(p["steps"]) for p in PHASES.values())
        lines.append(f"**Progress**: {completed_count}/{total_steps} steps completed")
        lines.append("")
    else:
        lines.append("**Status**: Generated from output directory scan")
        lines.append("")

    # Key metrics
    final_coalesced = get_file_metrics(output_dir, "final_coalesced.tsv")
    stripped_json = get_file_metrics(output_dir, "no_instruments.json")
    sanity_check = get_file_metrics(output_dir, "sanity_check.tsv")

    lines.append("### Key Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")

    if final_coalesced["exists"]:
        lines.append(f"| Final Patterns | {final_coalesced.get('data_rows', '-')} |")
        lines.append(f"| Unique tinyIds Covered | {final_coalesced.get('unique_tinyids', '-')} |")

    if stripped_json["exists"]:
        lines.append(f"| CDEs Processed | {stripped_json.get('record_count', '-')} |")

    if sanity_check["exists"]:
        remaining = sanity_check.get("data_rows", 0)
        status = "Clean" if remaining == 0 else f"{remaining} remaining"
        lines.append(f"| Sanity Check | {status} |")

    lines.append("")

    return lines


def generate_version_history(
    existing_content: Optional[str],
    version: str,
    current_phase: int,
    key_metric: str = "",
) -> List[str]:
    """Generate or update version history section."""
    lines = []
    date_str = datetime.now().strftime("%Y-%m-%d")

    lines.append("## Version History")
    lines.append("")
    lines.append("| Version | Date | Phase | Notes |")
    lines.append("|---------|------|-------|-------|")

    # Parse existing version history if present
    if existing_content and "## Version History" in existing_content:
        # Extract existing rows
        in_history = False
        for line in existing_content.split("\n"):
            if "## Version History" in line:
                in_history = True
                continue
            if in_history and line.startswith("|") and not line.startswith("|--") and "Version" not in line:
                lines.append(line)
            elif in_history and line.startswith("##"):
                break

    # Add current version
    phase_name = PHASES[current_phase]["name"]
    notes = key_metric or "Report generated"
    lines.append(f"| {version or 'current'} | {date_str} | {phase_name} | {notes} |")
    lines.append("")

    return lines


def generate_markdown_report(
    state: Optional[Dict],
    output_dir: str,
    title: str,
    version: Optional[str] = None,
    phase_filter: Optional[int] = None,
    existing_content: Optional[str] = None,
) -> str:
    """Generate complete markdown report."""
    lines = []
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Determine current phase
    if state:
        completed_steps = [s["name"] for s in state.get("completed_steps", [])]
        current_phase = determine_phase_from_steps(completed_steps)
    else:
        current_phase = 1  # Default

    # Title and metadata
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Generated**: {date_str}")
    if version:
        lines.append(f"**Version**: {version}")
    lines.append(f"**Output Directory**: `{output_dir}`")
    lines.append("")

    # Executive summary
    lines.extend(generate_executive_summary(state, output_dir, current_phase))

    # Phase sections
    lines.append("---")
    lines.append("")
    lines.append("## Phase Details")
    lines.append("")

    phases_to_show = [phase_filter] if phase_filter else [1, 2, 3, 4]
    for phase_num in phases_to_show:
        lines.extend(generate_phase_section(phase_num, state, output_dir))

    # Version history
    lines.append("---")
    lines.append("")
    key_metric = ""
    final_coalesced = get_file_metrics(output_dir, "final_coalesced.tsv")
    if final_coalesced["exists"]:
        key_metric = f"{final_coalesced.get('data_rows', 0)} patterns, {final_coalesced.get('unique_tinyids', 0)} tinyIds"

    lines.extend(generate_version_history(existing_content, version, current_phase, key_metric))

    return "\n".join(lines)


@graceful_interrupt
def run_action(args: Namespace):
    """Generate pipeline execution report."""
    # Validate input
    state_file = getattr(args, "state_file", None)
    output_dir = getattr(args, "output_dir", None)

    if not state_file and not output_dir:
        raise ValueError("Either --state-file or --output-dir is required")

    # Load state if provided
    state = None
    if state_file:
        state = load_workflow_state(state_file)
        if state:
            # Get output_dir from state if not provided
            variables = state.get("variables", {})
            if not output_dir:
                output_dir = variables.get("output_dir", ".")
            logger.info(f"Loaded workflow state: {state.get('workflow_name', 'unknown')}")
        else:
            logger.warning("Could not load workflow state, generating report from output directory")

    if not output_dir:
        output_dir = "."

    # Resolve output_dir path
    output_dir = str(Path(output_dir).resolve())
    logger.info(f"Scanning output directory: {output_dir}")

    # Load existing report for version history
    existing_content = None
    output_path = args.output
    if Path(output_path).exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception:
            pass

    # Generate report
    report_content = generate_markdown_report(
        state=state,
        output_dir=output_dir,
        title=getattr(args, "title", "Pipeline Execution Report"),
        version=getattr(args, "version", None),
        phase_filter=getattr(args, "phase", None),
        existing_content=existing_content,
    )

    # Write report
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"Wrote pipeline report to {output_path}")
    print(f"Pipeline report generated: {output_path}")

    return 0
