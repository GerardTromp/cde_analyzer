#
# File: actions/strip_report/run.py
#
"""
Strip Report - Generate markdown quality reports for stripped JSON outputs.

Scans output directory for stripped JSON files, runs remnant detection on each,
optionally scans for remaining temporal phrases, and produces a per-branch
quality matrix with version history.
"""
import json
import logging
import os
import re
from argparse import Namespace
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Temporal phrase scanning
# ---------------------------------------------------------------------------

_TEMPORAL_RE = re.compile(
    r'\b(in|over|during|for|within)\s+the\s+(past|last)\s+(\d+|[a-z]+)\s+'
    r'(days?|weeks?|months?|years?)',
    re.IGNORECASE,
)


def _scan_temporal_phrases(
    data: List[dict],
    field_paths: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    Scan JSON records for remaining temporal phrases.

    Returns dict mapping phrase text (lowercased) -> list of tinyIds.
    """
    if field_paths is None:
        field_paths = [
            "definitions.*.definition",
            "designations.*.designation",
        ]

    phrases: Dict[str, List[str]] = {}

    for record in data:
        tiny_id = record.get("tinyId", "?")
        for field_path in field_paths:
            for text in _extract_texts(record, field_path.split(".")):
                for m in _TEMPORAL_RE.finditer(text):
                    phrase = m.group(0).lower()
                    if phrase not in phrases:
                        phrases[phrase] = []
                    if tiny_id not in phrases[phrase]:
                        phrases[phrase].append(tiny_id)

    return phrases


def _extract_texts(obj: Any, parts: List[str]) -> List[str]:
    """Extract text values at a dotted path with wildcard support."""
    if not parts:
        return [obj] if isinstance(obj, str) else []

    key = parts[0]
    rest = parts[1:]

    if key == "*":
        if isinstance(obj, list):
            results = []
            for item in obj:
                results.extend(_extract_texts(item, rest))
            return results
    elif isinstance(obj, dict) and key in obj:
        return _extract_texts(obj[key], rest)

    return []


# ---------------------------------------------------------------------------
# File metrics
# ---------------------------------------------------------------------------

def _json_record_count(json_path: str) -> int:
    """Count records in a JSON array file."""
    path = Path(json_path)
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict) and "data" in data:
            return len(data["data"])
    except Exception:
        pass
    return 0


def _load_json(json_path: str) -> List[dict]:
    """Load JSON array from file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
    except Exception as e:
        logger.warning(f"Failed to load {json_path}: {e}")
    return []


def _file_size_str(path: str) -> str:
    """Human-readable file size."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "—"
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def _count_csv_rows(csv_path: str) -> int:
    """Count data rows in a CSV file (excluding header)."""
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)
        return max(0, total - 1)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

def _load_version_history(markdown_path: str) -> List[str]:
    """Extract existing version history rows from a markdown report."""
    rows: List[str] = []
    path = Path(markdown_path)
    if not path.exists():
        return rows
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return rows

    in_history = False
    for line in content.split("\n"):
        if "## Version History" in line:
            in_history = True
            continue
        if in_history:
            if line.startswith("##"):
                break
            if line.startswith("|") and not line.startswith("|--") and "Version" not in line:
                rows.append(line)
    return rows


# ---------------------------------------------------------------------------
# Branch name extraction
# ---------------------------------------------------------------------------

def _branch_name(filename: str) -> str:
    """Extract branch label from filename (e.g., 'both_full_stripped.json' -> 'both_full')."""
    stem = Path(filename).stem
    if stem.endswith("_stripped"):
        return stem[: -len("_stripped")]
    return stem


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _generate_report(
    output_dir: str,
    json_pattern: str,
    version: Optional[str],
    input_json: Optional[str],
    embed_dir: Optional[str],
    temporal_scan: bool,
    output_path: str,
) -> str:
    """Generate the full markdown report."""
    from logic.remnant_detector import (
        detect_remnants_from_json,
        summarize_remnants,
        affected_records,
    )

    lines: List[str] = []
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Find stripped JSON files
    pattern_path = str(Path(output_dir) / json_pattern)
    json_files = sorted(glob(pattern_path))

    if not json_files:
        logger.warning(f"No files matching '{json_pattern}' found in {output_dir}")

    # -- Header --
    lines.append("# Branching Strip Quality Report")
    lines.append("")
    lines.append(f"**Generated**: {date_str}")
    if version:
        lines.append(f"**Version**: {version}")
    lines.append(f"**Output Directory**: `{output_dir}`")

    input_count = 0
    if input_json:
        input_count = _json_record_count(input_json)
        count_str = f" ({input_count:,} records)" if input_count else ""
        lines.append(f"**Input JSON**: `{Path(input_json).name}`{count_str}")
    lines.append("")

    # -- Branch Summary --
    lines.append("## Branch Summary")
    lines.append("")
    lines.append("| Branch | File | Records | Size |")
    lines.append("|--------|------|--------:|-----:|")

    branch_data: List[Tuple[str, str, List[dict]]] = []
    for json_path in json_files:
        fname = Path(json_path).name
        branch = _branch_name(fname)
        data = _load_json(json_path)
        branch_data.append((branch, json_path, data))
        count = len(data)
        size = _file_size_str(json_path)
        lines.append(f"| {branch} | {fname} | {count:,} | {size} |")

    lines.append("")

    # -- Quality Checks --
    lines.append("## Quality Checks")
    lines.append("")

    if not branch_data:
        lines.append("*No stripped JSON files found.*")
        lines.append("")
    else:
        # Run remnant detection on each branch
        branch_remnants: Dict[str, Dict[str, int]] = {}
        branch_affected: Dict[str, int] = {}
        all_remnant_types: List[str] = []

        for branch, json_path, data in branch_data:
            logger.info(f"Scanning {branch} ({len(data)} records)...")
            remnants = detect_remnants_from_json(data)
            summary = summarize_remnants(remnants)
            branch_remnants[branch] = summary
            branch_affected[branch] = affected_records(remnants)
            for rtype in summary:
                if rtype not in all_remnant_types:
                    all_remnant_types.append(rtype)

        branch_names = [b for b, _, _ in branch_data]

        if not all_remnant_types:
            lines.append("**All branches CLEAN** — no remnant artifacts detected.")
            lines.append("")
        else:
            # Build matrix table
            header = "| Check | " + " | ".join(branch_names) + " |"
            sep = "|-------|" + "|".join(":--------:" for _ in branch_names) + "|"
            lines.append(header)
            lines.append(sep)

            for rtype in all_remnant_types:
                cells = []
                for branch in branch_names:
                    count = branch_remnants.get(branch, {}).get(rtype, 0)
                    cells.append("\u2713" if count == 0 else str(count))
                lines.append(f"| {rtype} | " + " | ".join(cells) + " |")

            # Status row
            status_cells = []
            for branch in branch_names:
                total = sum(branch_remnants.get(branch, {}).values())
                affected = branch_affected.get(branch, 0)
                if total == 0:
                    status_cells.append("**CLEAN**")
                else:
                    status_cells.append(f"**{total} in {affected} records**")
            lines.append(f"| **Status** | " + " | ".join(status_cells) + " |")
            lines.append("")

        # Per-branch summary (always shown, even if all clean)
        total_all = sum(sum(v.values()) for v in branch_remnants.values())
        total_affected = sum(branch_affected.values())
        if total_all == 0:
            lines.append(f"*Scanned {len(branch_data)} branches — zero remnants across all.*")
        else:
            lines.append(
                f"*Scanned {len(branch_data)} branches — "
                f"{total_all} remnants in {total_affected} affected records.*"
            )
        lines.append("")

    # -- Temporal phrases --
    if temporal_scan and branch_data:
        lines.append("## Remaining Temporal Phrases")
        lines.append("")

        # Aggregate temporal phrases across all branches
        # Use the most-stripped branch (last one, typically both_full or both_sub)
        # to represent the worst-case remaining
        all_temporal: Dict[str, Dict[str, List[str]]] = {}
        for branch, json_path, data in branch_data:
            phrases = _scan_temporal_phrases(data)
            if phrases:
                all_temporal[branch] = phrases

        if not all_temporal:
            lines.append("*No remaining temporal phrases detected across any branch.*")
            lines.append("")
        else:
            # Show per-branch summary, then detailed table for the most-stripped branch
            for branch, phrases in all_temporal.items():
                total_hits = sum(len(tids) for tids in phrases.values())
                unique_tids = set()
                for tids in phrases.values():
                    unique_tids.update(tids)

                lines.append(f"### {branch}")
                lines.append("")
                lines.append(
                    f"*{len(phrases)} unique temporal phrases "
                    f"across {len(unique_tids)} tinyIds ({total_hits} total occurrences)*"
                )
                lines.append("")
                lines.append("| Phrase | Count | Sample tinyIds |")
                lines.append("|--------|------:|----------------|")

                for phrase, tids in sorted(phrases.items(), key=lambda x: -len(x[1])):
                    sample = ", ".join(tids[:3])
                    if len(tids) > 3:
                        sample += f", ... (+{len(tids) - 3})"
                    lines.append(f"| {phrase} | {len(tids)} | {sample} |")

                lines.append("")

    # -- Embed data manifest --
    if embed_dir and os.path.isdir(embed_dir):
        lines.append("## Embed Data Manifest")
        lines.append("")

        csv_files = sorted(
            f for f in os.listdir(embed_dir) if f.endswith(".csv")
        )

        if not csv_files:
            lines.append("*No CSV files found in embed directory.*")
        else:
            lines.append("| File | Size | Rows |")
            lines.append("|------|-----:|-----:|")

            for fname in csv_files:
                fpath = os.path.join(embed_dir, fname)
                size = _file_size_str(fpath)
                rows = _count_csv_rows(fpath)
                lines.append(f"| {fname} | {size} | {rows:,} |")

        lines.append("")

    # -- Version history --
    lines.append("---")
    lines.append("")
    lines.append("## Version History")
    lines.append("")
    lines.append("| Version | Date | Branches | Status | Notes |")
    lines.append("|---------|------|----------|--------|-------|")

    prev_rows = _load_version_history(output_path)
    for row in prev_rows:
        lines.append(row)

    # Current version row
    date_short = datetime.now().strftime("%Y-%m-%d")
    ver_label = version or "current"
    n_branches = len(branch_data)

    # Determine overall status
    all_clean = all(
        sum(branch_remnants.get(b, {}).values()) == 0
        for b, _, _ in branch_data
    ) if branch_data else True

    status = "ALL CLEAN" if all_clean else "ISSUES FOUND"
    lines.append(
        f"| {ver_label} | {date_short} | {n_branches} | {status} | Report generated |"
    )
    lines.append("")

    return "\n".join(lines)


@graceful_interrupt
def run_action(args: Namespace):
    """Generate strip quality report."""
    output_dir = str(Path(args.output_dir).resolve())
    output_path = args.output
    version = getattr(args, "version", None)
    input_json = getattr(args, "input_json", None)
    embed_dir = getattr(args, "embed_dir", None)
    temporal_scan = getattr(args, "temporal_scan", True)
    json_pattern = getattr(args, "json_pattern", "*_stripped.json")

    if input_json:
        input_json = str(Path(input_json).resolve())
    if embed_dir:
        embed_dir = str(Path(embed_dir).resolve())

    logger.info(f"Generating strip quality report for: {output_dir}")

    report = _generate_report(
        output_dir=output_dir,
        json_pattern=json_pattern,
        version=version,
        input_json=input_json,
        embed_dir=embed_dir,
        temporal_scan=temporal_scan,
        output_path=output_path,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Strip quality report generated: {output_path}")
    return 0
