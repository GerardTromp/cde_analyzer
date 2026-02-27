#
# File: actions/discovery_report/run.py
#
"""
Discovery Report - Generate markdown summary reports for discovery pipelines.
"""
import json
import logging
from argparse import Namespace
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.file_utils import graceful_interrupt
from utils.pattern_tsv_utils import find_column_index

logger = logging.getLogger(__name__)

# Step definitions: (label, relative_path, tinyid_column_name_or_None)
INSTRUMENT_STEPS = [
    ("Mine instruments", "instruments.tsv", "tinyids"),
    ("Instrument verbatim", "instruments_verbatim.tsv", "tinyids"),
    ("Abbreviation expansions", "abbreviation_expansions/expanded_phrases.tsv", "tinyids"),
    ("Abbreviation patterns", "abbrev_patterns.tsv", "tinyids"),
    ("Discover verbatim", "discovered_instruments.tsv", "tinyIds"),
    ("Coalesce patterns", "coalesced_instruments.tsv", "tinyIds"),
    ("Curated patterns", "curated_instruments.tsv", "tinyIds"),
    ("Final discovered", "final_discovered.tsv", "tinyIds"),
    ("Final coalesced (tier-1)", "final_coalesced.tsv", "tinyIds"),
    ("Final coalesced (tier-2)", "final_coalesced_short.tsv", "tinyIds"),
    ("Tier-1 stripped JSON", "tier1_stripped.json", None),
    ("Final stripped JSON", "no_instruments.json", None),
    ("Sanity check", "sanity_check.tsv", "tinyids"),
]

INSTRUMENT_SUBSUMPTION_FILES = [
    "subsumption_report.tsv",
    "final_subsumption.tsv",
]

PHRASE_STEPS = [
    ("Mine phrases", "verbatim_phrases.tsv", "tinyids"),
    ("Discover verbatim", "discovered.tsv", "tinyIds"),
    ("Coalesce patterns", "coalesced.tsv", "tinyIds"),
    ("Coalesce report", "coalesce_report.tsv", None),
    ("Field analysis", "coalesced_fields.tsv", "tinyIds"),
    ("Curated patterns", "curated.tsv", "tinyIds"),
    ("Stripped JSON", "final_stripped.json", None),
    ("Strip trace", "strip_trace.tsv", None),
]

PHRASE_SUBSUMPTION_FILES = [
    "coalesce_report.tsv",
]

# Remnant report files to look for (label, relative_path)
REMNANT_FILES = [
    ("Naive (length-first)", "remnants_naive.tsv"),
    ("Smart (graph-ordered)", "remnants_smart.tsv"),
    ("Strip", "remnants.tsv"),  # single-mode fallback
]


# ---------------------------------------------------------------------------
# File metrics (adapted from pipeline_report)
# ---------------------------------------------------------------------------

def _count_tsv_rows(tsv_path: str) -> int:
    """Count data rows in TSV file (excluding header)."""
    path = Path(tsv_path)
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)
        return max(0, total - 1)  # subtract header
    except Exception:
        return 0


def _count_unique_tinyids(tsv_path: str, column_name: str) -> int:
    """Count unique tinyIds in a TSV column."""
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
                    ids_str = parts[col_idx]
                    for sep in [" ", "|", ","]:
                        if sep in ids_str:
                            unique_ids.update(
                                tid.strip() for tid in ids_str.split(sep) if tid.strip()
                            )
                            break
                    else:
                        if ids_str.strip():
                            unique_ids.add(ids_str.strip())
    except Exception:
        return 0
    return len(unique_ids)


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


def _get_step_metrics(output_dir: str, rel_path: str, tinyid_col: Optional[str]) -> Dict[str, Any]:
    """Get metrics for a pipeline step output file."""
    full_path = str(Path(output_dir) / rel_path)
    exists = Path(full_path).exists()
    metrics: Dict[str, Any] = {"exists": exists, "path": full_path}
    if not exists:
        return metrics

    if rel_path.endswith(".tsv"):
        metrics["rows"] = _count_tsv_rows(full_path)
        if tinyid_col:
            metrics["tinyids"] = _count_unique_tinyids(full_path, tinyid_col)
    elif rel_path.endswith(".json"):
        metrics["records"] = _json_record_count(full_path)

    return metrics


# ---------------------------------------------------------------------------
# Subsumption summary
# ---------------------------------------------------------------------------

def _parse_remnant_report(tsv_path: str) -> Dict[str, int]:
    """Parse a remnants TSV and return counts by remnant_type."""
    counts: Counter = Counter()
    path = Path(tsv_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            try:
                type_idx = find_column_index(header, "remnant_type")
            except ValueError:
                return {}
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) > type_idx and parts[type_idx].strip():
                    counts[parts[type_idx].strip()] += 1
    except Exception:
        return {}
    return dict(counts.most_common())


def _parse_subsumption_report(tsv_path: str) -> Counter:
    """Count subsumption actions by type from a coalesce report TSV."""
    counts: Counter = Counter()
    path = Path(tsv_path)
    if not path.exists():
        return counts
    try:
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            try:
                type_idx = find_column_index(header, "type")
            except ValueError:
                return counts
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) > type_idx and parts[type_idx].strip():
                    counts[parts[type_idx].strip()] += 1
    except Exception:
        pass
    return counts


# ---------------------------------------------------------------------------
# Sanity check summary
# ---------------------------------------------------------------------------

def _parse_sanity_check(tsv_path: str, max_rows: int = 10) -> List[Dict[str, str]]:
    """Read top rows from sanity_check.tsv."""
    rows: List[Dict[str, str]] = []
    path = Path(tsv_path)
    if not path.exists():
        return rows
    try:
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            for line in f:
                if len(rows) >= max_rows:
                    break
                parts = line.strip().split("\t")
                row = {}
                for i, h in enumerate(header):
                    row[h] = parts[i] if i < len(parts) else ""
                rows.append(row)
    except Exception:
        pass
    return rows


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
# Markdown generation
# ---------------------------------------------------------------------------

def _generate_report(
    output_dir: str,
    pipeline: str,
    version: Optional[str],
    input_json: Optional[str],
    output_path: str,
) -> str:
    """Generate the full markdown report."""
    lines: List[str] = []
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    steps = INSTRUMENT_STEPS if pipeline == "instrument" else PHRASE_STEPS
    sub_files = INSTRUMENT_SUBSUMPTION_FILES if pipeline == "instrument" else PHRASE_SUBSUMPTION_FILES
    title = "Instrument Discovery Report" if pipeline == "instrument" else "Phrase Discovery Report"

    # -- Header --
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Generated**: {date_str}")
    if version:
        lines.append(f"**Version**: {version}")
    lines.append(f"**Output Directory**: `{output_dir}`")
    if input_json:
        lines.append(f"**Input JSON**: `{input_json}`")
    lines.append("")

    # -- Summary table --
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")

    if input_json:
        count = _json_record_count(input_json)
        if count:
            lines.append(f"| Input CDEs | {count:,} |")

    # Collect step metrics for summary and detail table
    step_metrics: List[Tuple[str, str, Optional[str], Dict]] = []
    for label, rel_path, tid_col in steps:
        m = _get_step_metrics(output_dir, rel_path, tid_col)
        step_metrics.append((label, rel_path, tid_col, m))

    # Key summary rows from specific steps
    for label, rel_path, tid_col, m in step_metrics:
        if not m["exists"]:
            continue
        rows = m.get("rows")
        tids = m.get("tinyids")
        records = m.get("records")
        if rows is not None:
            lines.append(f"| {label} | {rows:,} patterns |")
        elif records is not None:
            lines.append(f"| {label} | {records:,} records |")

    lines.append("")

    # -- Pipeline Steps table --
    lines.append("## Pipeline Steps")
    lines.append("")
    lines.append("| Step | File | Status | Rows | tinyIds |")
    lines.append("|------|------|:------:|-----:|--------:|")

    for label, rel_path, tid_col, m in step_metrics:
        status = "\u2713" if m["exists"] else "\u2014"
        rows_str = str(m.get("rows", m.get("records", "\u2014")))
        tids_str = str(m.get("tinyids", "\u2014"))
        lines.append(f"| {label} | `{rel_path}` | {status} | {rows_str} | {tids_str} |")

    lines.append("")

    # -- Subsumption summary --
    all_sub_counts: Counter = Counter()
    for sub_file in sub_files:
        counts = _parse_subsumption_report(str(Path(output_dir) / sub_file))
        if counts:
            all_sub_counts.update(counts)

    if all_sub_counts:
        lines.append("## Subsumption Summary")
        lines.append("")
        lines.append("| Action | Count |")
        lines.append("|--------|------:|")
        for action, count in all_sub_counts.most_common():
            lines.append(f"| {action} | {count} |")
        lines.append(f"| **Total** | **{sum(all_sub_counts.values())}** |")
        lines.append("")

    # -- Sanity check (instrument only) --
    if pipeline == "instrument":
        sanity_path = str(Path(output_dir) / "sanity_check.tsv")
        survivors = _parse_sanity_check(sanity_path)
        if survivors:
            lines.append("## Sanity Check Survivors")
            lines.append("")
            # Use whatever columns exist
            cols = list(survivors[0].keys())
            lines.append("| " + " | ".join(cols) + " |")
            lines.append("|" + "|".join("---" for _ in cols) + "|")
            for row in survivors:
                vals = [row.get(c, "") for c in cols]
                # Truncate long values
                vals = [v[:80] + ("..." if len(v) > 80 else "") for v in vals]
                lines.append("| " + " | ".join(vals) + " |")
            total_rows = _count_tsv_rows(sanity_path)
            if total_rows > len(survivors):
                lines.append(f"\n*Showing {len(survivors)} of {total_rows} survivors.*")
            lines.append("")

    # -- Remnant summary --
    remnant_data: List[Tuple[str, Dict[str, int]]] = []
    for label, rel_path in REMNANT_FILES:
        full = str(Path(output_dir) / rel_path)
        counts = _parse_remnant_report(full)
        if counts:
            remnant_data.append((label, counts))
    # Also check compare/ subdirectory
    for label, rel_path in REMNANT_FILES[:2]:  # naive and smart only
        full = str(Path(output_dir) / "compare" / rel_path)
        counts = _parse_remnant_report(full)
        if counts and (label, counts) not in remnant_data:
            remnant_data.append((f"{label} (compare)", counts))

    if remnant_data:
        lines.append("## Remnant Analysis")
        lines.append("")
        if len(remnant_data) == 1:
            label, counts = remnant_data[0]
            total = sum(counts.values())
            lines.append(f"**{label}**: {total:,} remnants detected")
            lines.append("")
            lines.append("| Remnant Type | Count |")
            lines.append("|-------------|------:|")
            for rtype, count in counts.items():
                lines.append(f"| {rtype} | {count:,} |")
            lines.append(f"| **Total** | **{total:,}** |")
        else:
            # Collect all remnant types across all runs
            all_types: List[str] = []
            for _, counts in remnant_data:
                for t in counts:
                    if t not in all_types:
                        all_types.append(t)

            header_cols = ["Remnant Type"] + [label for label, _ in remnant_data]
            lines.append("| " + " | ".join(header_cols) + " |")
            lines.append("|" + "|".join("------:" for _ in header_cols) + "|")
            for rtype in all_types:
                vals = [str(counts.get(rtype, 0)) for _, counts in remnant_data]
                lines.append(f"| {rtype} | " + " | ".join(vals) + " |")
            totals = [str(sum(counts.values())) for _, counts in remnant_data]
            lines.append(f"| **Total** | " + " | ".join(f"**{t}**" for t in totals) + " |")

        lines.append("")

    # -- Version history --
    lines.append("---")
    lines.append("")
    lines.append("## Version History")
    lines.append("")
    lines.append("| Version | Date | Patterns | tinyIds | Notes |")
    lines.append("|---------|------|----------|---------|-------|")

    prev_rows = _load_version_history(output_path)
    for row in prev_rows:
        lines.append(row)

    # Current version row
    date_short = datetime.now().strftime("%Y-%m-%d")
    # Find the "main" pattern count and tinyId count
    pattern_count = "\u2014"
    tinyid_count = "\u2014"
    # For instrument: final_coalesced; for phrase: coalesced_fields or curated
    main_files = {
        "instrument": [("final_coalesced.tsv", "tinyIds"), ("coalesced_instruments.tsv", "tinyIds")],
        "phrase": [("curated.tsv", "tinyIds"), ("coalesced_fields.tsv", "tinyIds"), ("coalesced.tsv", "tinyIds")],
    }
    for fname, tcol in main_files.get(pipeline, []):
        m = _get_step_metrics(output_dir, fname, tcol)
        if m["exists"] and "rows" in m:
            pattern_count = str(m["rows"])
            tinyid_count = str(m.get("tinyids", "\u2014"))
            break

    ver_label = version or "current"
    lines.append(f"| {ver_label} | {date_short} | {pattern_count} | {tinyid_count} | Report generated |")
    lines.append("")

    return "\n".join(lines)


@graceful_interrupt
def run_action(args: Namespace):
    """Generate discovery pipeline report."""
    output_dir = str(Path(args.output_dir).resolve())
    pipeline = args.pipeline
    version = getattr(args, "version", None)
    input_json = getattr(args, "input_json", None)
    output_path = args.output

    logger.info(f"Generating {pipeline} discovery report for: {output_dir}")

    report = _generate_report(
        output_dir=output_dir,
        pipeline=pipeline,
        version=version,
        input_json=input_json,
        output_path=output_path,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Discovery report generated: {output_path}")
    return 0
