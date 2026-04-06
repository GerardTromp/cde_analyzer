#
# File: actions/strip_report/run.py
#
"""
Strip Report - Generate markdown quality reports for stripped JSON outputs.

Scans output directory for stripped JSON files, runs remnant detection on each,
optionally scans for remaining temporal phrases and instrument name leakage,
and produces a per-branch quality matrix with version history.
"""
import csv
import json
import logging
import os
import re
from argparse import Namespace
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
# Boilerplate leakage scanning (substring-based)
# ---------------------------------------------------------------------------

# Boilerplate signature phrases — distinctive substrings indicating
# licensing, publisher, scoring, or Working Group content in definitions.
_BOILERPLATE_SIGNATURES = [
    # Licensing / purchase
    ("licensing", "licensing agreement"),
    ("licensing", "requires a licensing agreement"),
    ("licensing", "proprietary instrument"),
    ("licensing", "may be purchased from"),
    ("licensing", "not sold separately"),
    ("licensing", "permission to use"),
    ("licensing", "copyright"),
    # Publishers
    ("publisher", "western psychological services"),
    ("publisher", "mind garden"),
    ("publisher", "psychological assessment resources"),
    ("publisher", "multi-health systems"),
    ("publisher", "pearson assessments"),
    # Working Group
    ("working_group", "working group recommends"),
    ("working_group", "working group notes"),
    ("working_group", "working group recognizes"),
    ("working_group", "working group defines"),
    # Item count
    ("item_count", r"is a \d+-item"),
    ("item_count", r"is an \d+-item"),
    ("item_count", r"consists of \d+ items"),
    ("item_count", r"contains \d+ items"),
    # Response format
    ("response_format", "likert scale"),
    ("response_format", "point ordinal response"),
    ("response_format", "point response scale"),
    # Scoring
    ("scoring", "total score is calculated"),
    ("scoring", "scores range from"),
    ("scoring", "scored by summing"),
    ("scoring", "higher scores indicate"),
    ("scoring", "lower scores indicate"),
    ("scoring", "scoring key"),
    ("scoring", "reverse scored"),
    # Developer citation
    ("citation", "developed by"),
    ("citation", "adapted from"),
    # URLs / references
    ("url_reference", "http://"),
    ("url_reference", "https://"),
    ("url_reference", "available at:"),
]

_BOILERPLATE_REGEXES: Optional[List[Tuple[str, str, re.Pattern]]] = None


def _get_boilerplate_regexes() -> List[Tuple[str, str, re.Pattern]]:
    """Compile boilerplate signature regexes (lazy, cached)."""
    global _BOILERPLATE_REGEXES
    if _BOILERPLATE_REGEXES is None:
        _BOILERPLATE_REGEXES = []
        for category, sig in _BOILERPLATE_SIGNATURES:
            try:
                rx = re.compile(sig, re.IGNORECASE)
            except re.error:
                rx = re.compile(re.escape(sig), re.IGNORECASE)
            _BOILERPLATE_REGEXES.append((category, sig, rx))
    return _BOILERPLATE_REGEXES


def _scan_boilerplate_leakage(
    data: List[dict],
    substitute_tids: Optional[Set[str]] = None,
    field_paths: Optional[List[str]] = None,
    min_def_length: int = 50,
) -> Dict[str, List[Tuple[str, int, str]]]:
    """
    Scan definitions for boilerplate signature phrases.

    Returns dict mapping tinyId -> list of (category, def_length, signature).
    Only reports CDEs NOT in substitute_tids (novel leakage).
    """
    if field_paths is None:
        field_paths = ["definitions.*.definition"]
    if substitute_tids is None:
        substitute_tids = set()

    regexes = _get_boilerplate_regexes()
    hits: Dict[str, List[Tuple[str, int, str]]] = {}

    for record in data:
        tiny_id = record.get("tinyId", "?")
        if tiny_id in substitute_tids:
            continue
        for field_path in field_paths:
            for text in _extract_texts(record, field_path.split(".")):
                if len(text) < min_def_length:
                    continue
                for category, sig_text, regex in regexes:
                    if regex.search(text):
                        if tiny_id not in hits:
                            hits[tiny_id] = []
                        hits[tiny_id].append((category, len(text), sig_text))

    return hits


def _load_substitute_tids(
    substitute_tsv_paths: Optional[List[str]] = None,
) -> Set[str]:
    """Load tinyIds from boilerplate substitute TSV files."""
    tids: Set[str] = set()
    if not substitute_tsv_paths:
        return tids
    for path in substitute_tsv_paths:
        if not Path(path).exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    for t in row.get("tinyIds", "").split(";"):
                        t = t.strip()
                        if t:
                            tids.add(t)
        except Exception as e:
            logger.warning(f"Failed to load substitute TSV {path}: {e}")
    return tids


# ---------------------------------------------------------------------------
# Instrument leakage scanning
# ---------------------------------------------------------------------------

def _build_instrument_names() -> List[Tuple[str, re.Pattern]]:
    """
    Build regex patterns for known instrument family names.

    Uses FAMILY_PATTERNS from instrument_family_patterns.py to detect
    instrument names that should have been stripped but remain in text.

    Returns list of (display_name, compiled_regex) tuples.
    """
    from utils.instrument_family_patterns import FAMILY_PATTERNS

    names: List[Tuple[str, re.Pattern]] = []
    for fp in FAMILY_PATTERNS:
        # Use each family's detection patterns directly
        for pat in fp.patterns:
            names.append((fp.display_name, pat))
        for pat in fp.acronym_patterns:
            names.append((fp.display_name, pat))
    return names


def _load_instrument_patterns_from_tsv(
    tsv_path: str,
) -> List[Tuple[str, re.Pattern]]:
    """
    Load instrument pattern texts from a curated TSV file.

    Reads the 'pattern' column and builds word-boundary regexes for each.
    Returns list of (pattern_text, compiled_regex) tuples.
    """
    patterns: List[Tuple[str, re.Pattern]] = []
    path = Path(tsv_path)
    if not path.exists():
        logger.warning(f"Instrument pattern TSV not found: {tsv_path}")
        return patterns

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                text = row.get("pattern", "").strip()
                if not text:
                    continue
                # Skip regex patterns (start with common regex metacharacters)
                if text.startswith(("REGEX:", "(?", "^", "\\b")):
                    continue
                try:
                    escaped = re.escape(text)
                    pat = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
                    patterns.append((text, pat))
                except re.error:
                    continue
    except Exception as e:
        logger.warning(f"Failed to load instrument patterns from {tsv_path}: {e}")

    return patterns


def _scan_instrument_leakage(
    data: List[dict],
    instrument_patterns: List[Tuple[str, re.Pattern]],
    field_paths: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    Scan JSON records for instrument names that should have been stripped.

    Returns dict mapping instrument_name -> list of tinyIds where it was found.
    """
    if field_paths is None:
        field_paths = [
            "definitions.*.definition",
            "designations.*.designation",
        ]

    hits: Dict[str, List[str]] = {}

    for record in data:
        tiny_id = record.get("tinyId", "?")
        for field_path in field_paths:
            for text in _extract_texts(record, field_path.split(".")):
                for name, pattern in instrument_patterns:
                    if pattern.search(text):
                        if name not in hits:
                            hits[name] = []
                        if tiny_id not in hits[name]:
                            hits[name].append(tiny_id)

    return hits


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
    """Extract branch label from filename.

    Handles both naming conventions:
      New-style: 'stripped_MTSFPT.json' -> 'MTSFPT'
      Old-style: 'both_full_stripped.json' -> 'both_full'
    """
    stem = Path(filename).stem
    if stem.startswith("stripped_"):
        return stem[len("stripped_"):]
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
    instrument_scan: bool = True,
    inst_pattern_tsvs: Optional[List[str]] = None,
    boilerplate_scan: bool = True,
    substitute_tsvs: Optional[List[str]] = None,
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

    # -- Instrument leakage --
    if instrument_scan and branch_data:
        lines.append("## Instrument Name Leakage")
        lines.append("")

        # Build instrument name patterns: known families + curated TSVs
        inst_patterns = _build_instrument_names()
        if inst_pattern_tsvs:
            for tsv_path in inst_pattern_tsvs:
                tsv_pats = _load_instrument_patterns_from_tsv(tsv_path)
                inst_patterns.extend(tsv_pats)
                logger.info(
                    f"Loaded {len(tsv_pats)} patterns from {Path(tsv_path).name}"
                )

        # Only scan branches that include instrument stripping (M=T or S=T)
        # Branches like MFSFPT (phrase-only) are expected to still contain instruments
        inst_stripped_branches = []
        for branch, json_path, data in branch_data:
            # Parse branch code: positions 0-1=M, 2-3=S
            code = branch.upper()
            m_stripped = len(code) >= 2 and code[1] == "T"
            s_stripped = len(code) >= 4 and code[3] == "T"
            if m_stripped or s_stripped:
                inst_stripped_branches.append((branch, json_path, data))

        if not inst_stripped_branches:
            lines.append(
                "*No instrument-stripped branches found — skipping leakage scan.*"
            )
            lines.append("")
        else:
            all_leaks: Dict[str, Dict[str, List[str]]] = {}
            for branch, json_path, data in inst_stripped_branches:
                logger.info(f"Scanning {branch} for instrument leakage...")
                leaks = _scan_instrument_leakage(data, inst_patterns)
                if leaks:
                    all_leaks[branch] = leaks

            if not all_leaks:
                lines.append(
                    "*No instrument name leakage detected in stripped branches.*"
                )
                lines.append("")
            else:
                for branch, leaks in all_leaks.items():
                    total_hits = sum(len(tids) for tids in leaks.values())
                    unique_tids: Set[str] = set()
                    for tids in leaks.values():
                        unique_tids.update(tids)

                    lines.append(f"### {branch}")
                    lines.append("")
                    lines.append(
                        f"*{len(leaks)} instrument names "
                        f"across {len(unique_tids)} tinyIds "
                        f"({total_hits} total occurrences)*"
                    )
                    lines.append("")
                    lines.append("| Instrument | Count | Sample tinyIds |")
                    lines.append("|------------|------:|----------------|")

                    for name, tids in sorted(
                        leaks.items(), key=lambda x: -len(x[1])
                    ):
                        sample = ", ".join(tids[:3])
                        if len(tids) > 3:
                            sample += f", ... (+{len(tids) - 3})"
                        lines.append(f"| {name} | {len(tids)} | {sample} |")

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

    # -- Boilerplate leakage --
    if boilerplate_scan and branch_data:
        lines.append("## Boilerplate Leakage (Substring Scan)")
        lines.append("")

        sub_tids = _load_substitute_tids(substitute_tsvs)
        if sub_tids:
            lines.append(
                f"*Excluded {len(sub_tids)} already-substituted tinyIds from scan.*"
            )
            lines.append("")

        # Scan the most-stripped branch (MTSTPT preferred)
        scan_branch = None
        for branch, json_path, data in branch_data:
            if "MTSTPT" in branch.upper():
                scan_branch = (branch, data)
                break
        if scan_branch is None:
            scan_branch = (branch_data[-1][0], branch_data[-1][2])

        bp_branch, bp_data = scan_branch
        bp_hits = _scan_boilerplate_leakage(bp_data, substitute_tids=sub_tids)

        if not bp_hits:
            lines.append(
                f"**No boilerplate leakage detected** in {bp_branch} "
                f"({len(_get_boilerplate_regexes())} signatures checked)."
            )
        else:
            # Summarize by category
            cat_counter: Dict[str, int] = {}
            for tid, sig_list in bp_hits.items():
                for cat, dlen, sig in sig_list:
                    cat_counter[cat] = cat_counter.get(cat, 0) + 1

            lines.append(f"Scanned {bp_branch}: **{len(bp_hits)} CDEs** with "
                         f"boilerplate signatures ({len(_get_boilerplate_regexes())} "
                         f"signatures checked).")
            lines.append("")
            lines.append("| Category | Hits | Example Signature |")
            lines.append("|----------|-----:|-------------------|")
            for cat in sorted(cat_counter.keys(), key=lambda c: -cat_counter[c]):
                # Find an example signature for this category
                example = ""
                for tid, sig_list in bp_hits.items():
                    for c, _, sig in sig_list:
                        if c == cat:
                            example = sig
                            break
                    if example:
                        break
                lines.append(f"| {cat} | {cat_counter[cat]} | `{example}` |")

            lines.append("")

            # High-priority: 2+ signatures AND >300 chars
            high_pri = [
                (tid, sigs) for tid, sigs in bp_hits.items()
                if len(sigs) >= 2 and any(dlen > 300 for _, dlen, _ in sigs)
            ]
            if high_pri:
                lines.append(f"### High-Priority ({len(high_pri)} CDEs: 2+ signatures, >300 chars)")
                lines.append("")
                lines.append("| tinyId | Def Length | Signatures |")
                lines.append("|--------|----------:|------------|")
                for tid, sigs in sorted(high_pri, key=lambda x: -max(d for _, d, _ in x[1])):
                    dlen = max(d for _, d, _ in sigs)
                    sig_names = ", ".join(sorted(set(s for _, _, s in sigs)))
                    lines.append(f"| {tid} | {dlen} | {sig_names[:60]} |")
                lines.append("")

            # Detail: top 20 by number of signatures
            ranked = sorted(bp_hits.items(),
                            key=lambda x: (-len(x[1]), -max(d for _, d, _ in x[1])))
            lines.append(f"### All Leakage ({len(bp_hits)} CDEs)")
            lines.append("")
            lines.append("| tinyId | Def Length | # Sigs | Categories |")
            lines.append("|--------|----------:|-------:|------------|")
            for tid, sigs in ranked[:30]:
                dlen = max(d for _, d, _ in sigs)
                cats = ", ".join(sorted(set(c for c, _, _ in sigs)))
                lines.append(f"| {tid} | {dlen} | {len(sigs)} | {cats} |")
            if len(ranked) > 30:
                lines.append(f"| *...{len(ranked)-30} more* | | | |")
            lines.append("")

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
    instrument_scan = getattr(args, "instrument_scan", True)
    boilerplate_scan = getattr(args, "boilerplate_scan", True)
    json_pattern = getattr(args, "json_pattern", "*_stripped.json")

    # Collect instrument pattern TSV paths
    inst_pattern_tsvs: List[str] = []
    for attr in ("inst_patterns_full", "inst_patterns_sub"):
        val = getattr(args, attr, None)
        if val:
            resolved = str(Path(val).resolve())
            if Path(resolved).exists():
                inst_pattern_tsvs.append(resolved)

    # Collect substitute TSV paths
    substitute_tsvs: List[str] = []
    raw_sub = getattr(args, "substitute_tsv", None)
    if raw_sub:
        for val in raw_sub:
            resolved = str(Path(val).resolve())
            if Path(resolved).exists():
                substitute_tsvs.append(resolved)

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
        instrument_scan=instrument_scan,
        inst_pattern_tsvs=inst_pattern_tsvs or None,
        boilerplate_scan=boilerplate_scan,
        substitute_tsvs=substitute_tsvs or None,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Strip quality report generated: {output_path}")
    return 0
