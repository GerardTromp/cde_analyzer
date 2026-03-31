#
# File: actions/curation/run.py
#
"""
Curation - Run module for curation lifecycle management.

Provides editor, multi-curator, incremental curation, and priority split.
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multi-curator: init
# ---------------------------------------------------------------------------

def _run_init_curation(args, init_path: str) -> int:
    """
    Create per-curator copies of a patterns TSV with curation columns.

    For each curator name, copies the source TSV and adds four columns:
        decision      — empty (curator fills: strip/skip/modify)
        modification  — empty (free-text when decision=modify)
        notes         — empty (optional commentary)
        curator       — pre-filled with curator name

    All original columns are preserved.  Output files are named
    ``{stem}.{curator_name}.tsv``.
    """
    import csv
    import re
    from pathlib import Path

    # Validate --curators
    curators_raw = getattr(args, 'curators', None)
    if not curators_raw:
        logger.error("--curators is required with --init-curation "
                      "(comma-separated list of names)")
        raise SystemExit(1)

    curators = [c.strip() for c in curators_raw.split(',') if c.strip()]
    if len(curators) < 2:
        logger.error("At least 2 curator names are required")
        raise SystemExit(1)

    # Validate curator names: alphanumeric + underscore
    name_re = re.compile(r'^[A-Za-z0-9_]+$')
    for name in curators:
        if not name_re.match(name):
            logger.error(f"Invalid curator name '{name}': "
                          "use only letters, digits, and underscores")
            raise SystemExit(1)

    if len(set(curators)) != len(curators):
        logger.error("Duplicate curator names detected")
        raise SystemExit(1)

    # Read source TSV
    init_p = Path(init_path)
    if not init_p.is_file():
        logger.error(f"Source file not found: {init_path}")
        raise SystemExit(1)

    with open(init_p, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        original_fields = list(reader.fieldnames or [])
        rows = list(reader)

    if not rows:
        logger.error("Source TSV is empty")
        raise SystemExit(1)

    # Determine output directory
    output_dir = Path(getattr(args, 'output', None) or init_p.parent)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Curation columns to add (skip if already present)
    curation_cols = ['decision', 'modification', 'notes', 'curator']
    existing_curation = [c for c in curation_cols if c in original_fields]
    new_cols = [c for c in curation_cols if c not in original_fields]
    if existing_curation:
        logger.warning(f"Source already has curation columns: {existing_curation} "
                        "(will be preserved, not duplicated)")

    output_fields = original_fields + new_cols

    # Write one copy per curator
    stem = init_p.stem
    created = []
    for curator_name in curators:
        out_path = output_dir / f"{stem}.{curator_name}.tsv"
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_fields,
                                     delimiter='\t', lineterminator='\n')
            writer.writeheader()
            for row in rows:
                out_row = dict(row)
                # Set curation columns
                if 'decision' in new_cols:
                    out_row['decision'] = ''
                if 'modification' in new_cols:
                    out_row['modification'] = ''
                if 'notes' in new_cols:
                    out_row['notes'] = ''
                if 'curator' in new_cols:
                    out_row['curator'] = curator_name
                elif 'curator' in original_fields:
                    out_row['curator'] = curator_name
                writer.writerow(out_row)
        created.append(str(out_path))
        logger.info(f"Created: {out_path}")

    print(f"\n  Init curation: {len(curators)} curator copies created")
    print(f"  Source:      {init_path} ({len(rows)} patterns)")
    print(f"  Curators:    {', '.join(curators)}")
    print(f"  Output dir:  {output_dir}")
    for p in created:
        print(f"    {p}")
    print(f"\n  Next: cde-analyzer curation --edit <curator_file>.tsv")

    return 0


# ---------------------------------------------------------------------------
# Multi-curator: merge
# ---------------------------------------------------------------------------

def _run_merge_curation(args, curation_files: list) -> int:
    """
    Merge curated files from multiple curators, generate consensus and reports.

    Reads 2+ curator TSV files, matches rows by 'pattern' column, computes
    inter-rater statistics, and writes:
        consensus.tsv           — All patterns with majority decision
        discrepancies.tsv       — Only patterns where curators disagree
        inter_rater_report.md   — Statistics report
        discrepancies.html      — Interactive visual diff
    """
    import csv
    import json
    from datetime import datetime
    from pathlib import Path

    from logic.inter_rater import compute_agreement_stats

    # Validate output directory
    output_dir_raw = getattr(args, 'output', None)
    if not output_dir_raw:
        logger.error("--output is required for --merge-curation (directory path)")
        raise SystemExit(1)
    output_dir = Path(output_dir_raw)
    output_dir.mkdir(parents=True, exist_ok=True)

    if len(curation_files) < 2:
        logger.error("At least 2 curator files are required for --merge-curation")
        raise SystemExit(1)

    # Read each curator file
    curator_data: dict = {}       # curator_name → {pattern: row_dict}
    all_patterns_ordered = []     # preserve order from first file
    pattern_set = set()
    base_fields = None            # original columns (before curation cols)

    for fpath in curation_files:
        fp = Path(fpath)
        if not fp.is_file():
            logger.error(f"Curator file not found: {fpath}")
            raise SystemExit(1)

        with open(fp, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            fields = list(reader.fieldnames or [])
            rows = list(reader)

        if not rows:
            logger.warning(f"Empty curator file: {fpath}")
            continue

        # Detect curator name: from 'curator' column or filename
        curator_name = rows[0].get('curator', '').strip()
        if not curator_name:
            # Infer from filename: stem.curator_name.tsv
            parts = fp.stem.rsplit('.', 1)
            curator_name = parts[-1] if len(parts) > 1 else fp.stem

        if curator_name in curator_data:
            logger.error(f"Duplicate curator name '{curator_name}' "
                          f"(from {fpath})")
            raise SystemExit(1)

        # Track base fields (exclude curation columns)
        curation_cols = {'decision', 'modification', 'notes', 'curator'}
        if base_fields is None:
            base_fields = [f for f in fields if f not in curation_cols]

        # Index by pattern
        pattern_rows = {}
        for row in rows:
            pat = row.get('pattern', '').strip()
            if pat:
                pattern_rows[pat] = row
                if pat not in pattern_set:
                    all_patterns_ordered.append(pat)
                    pattern_set.add(pat)

        curator_data[curator_name] = pattern_rows
        logger.info(f"Loaded curator '{curator_name}': {len(pattern_rows)} patterns "
                     f"from {fpath}")

    curators = list(curator_data.keys())
    if len(curators) < 2:
        logger.error("Need at least 2 non-empty curator files")
        raise SystemExit(1)

    # Build decisions matrix: {pattern: {curator: decision}}
    decisions: dict = {}
    full_data: dict = {}  # {pattern: {curator: full_row_dict}}

    for pattern in all_patterns_ordered:
        decisions[pattern] = {}
        full_data[pattern] = {}
        for curator_name in curators:
            row = curator_data[curator_name].get(pattern)
            if row:
                decisions[pattern][curator_name] = row.get('decision', '').strip()
                full_data[pattern][curator_name] = row
            else:
                decisions[pattern][curator_name] = ''

    # Compute statistics
    stats = compute_agreement_stats(decisions, curators)

    # ── Generate consensus.tsv ──
    consensus_path = output_dir / "consensus.tsv"
    consensus_fields = list(base_fields or [])
    consensus_fields.extend([
        'consensus_decision', 'agreement_level',
    ])
    for c in curators:
        consensus_fields.append(f"decision_{c}")

    with open(consensus_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=consensus_fields,
                                 delimiter='\t', lineterminator='\n',
                                 extrasaction='ignore')
        writer.writeheader()
        for pattern in all_patterns_ordered:
            # Use first available curator's row as base
            base_row = {}
            for c in curators:
                if pattern in curator_data[c]:
                    base_row = dict(curator_data[c][pattern])
                    break

            # Remove curation-specific columns from base
            for col in ('decision', 'modification', 'notes', 'curator'):
                base_row.pop(col, None)

            # Determine agreement level
            non_empty = {c: d for c, d in decisions[pattern].items() if d}
            if len(non_empty) < 2:
                agreement_level = "single"
            elif len(set(non_empty.values())) == 1:
                agreement_level = "unanimous"
            else:
                counts = {}
                for v in non_empty.values():
                    counts[v] = counts.get(v, 0) + 1
                max_count = max(counts.values())
                if max_count > len(non_empty) / 2:
                    agreement_level = "majority"
                else:
                    agreement_level = "split"

            consensus = stats.consensus_decisions.get(pattern, '')
            base_row['consensus_decision'] = consensus
            base_row['agreement_level'] = agreement_level
            for c in curators:
                base_row[f"decision_{c}"] = decisions[pattern].get(c, '')

            writer.writerow(base_row)

    logger.info(f"Wrote consensus: {consensus_path}")

    # ── Generate discrepancies.tsv ──
    discrepancy_path = output_dir / "discrepancies.tsv"
    disc_fields = list(consensus_fields)
    # Add modification columns for discrepancy detail
    for c in curators:
        disc_fields.append(f"modification_{c}")
        disc_fields.append(f"notes_{c}")

    with open(discrepancy_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=disc_fields,
                                 delimiter='\t', lineterminator='\n',
                                 extrasaction='ignore')
        writer.writeheader()
        for disc in stats.discrepancies:
            pattern = disc['pattern']
            base_row = {}
            for c in curators:
                if pattern in curator_data[c]:
                    base_row = dict(curator_data[c][pattern])
                    break

            for col in ('decision', 'modification', 'notes', 'curator'):
                base_row.pop(col, None)

            base_row['consensus_decision'] = disc['consensus']
            base_row['agreement_level'] = disc['agreement_level']
            for c in curators:
                base_row[f"decision_{c}"] = decisions[pattern].get(c, '')
                row = full_data[pattern].get(c, {})
                base_row[f"modification_{c}"] = row.get('modification', '')
                base_row[f"notes_{c}"] = row.get('notes', '')

            writer.writerow(base_row)

    logger.info(f"Wrote discrepancies: {discrepancy_path} "
                f"({len(stats.discrepancies)} rows)")

    # ── Generate inter_rater_report.md ──
    report_path = output_dir / "inter_rater_report.md"
    report_lines = _generate_inter_rater_report(stats, curators, str(output_dir))
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    logger.info(f"Wrote report: {report_path}")

    # ── Generate discrepancies.html ──
    html_path = output_dir / "discrepancies.html"
    _generate_discrepancy_html(stats, curators, decisions, full_data,
                                all_patterns_ordered, html_path)
    logger.info(f"Wrote HTML: {html_path}")

    # Summary
    print(f"\n  Merge curation: {len(curators)} curators, "
          f"{stats.n_patterns} patterns")
    print(f"  Reviewed:        {stats.n_reviewed} "
          f"(with 2+ decisions)")
    print(f"  Unanimous:       {stats.n_unanimous} "
          f"({stats.overall_agreement_pct}%)")
    print(f"  Majority:        {stats.n_majority}")
    print(f"  Split:           {stats.n_split}")
    if stats.krippendorff_alpha is not None:
        print(f"  Krippendorff \u03b1:  {stats.krippendorff_alpha}")
    for pk in stats.pairwise_kappas:
        print(f"  Cohen \u03ba ({pk.curator_a} vs {pk.curator_b}): "
              f"{pk.kappa}")
    print(f"\n  Output:")
    print(f"    {consensus_path}")
    print(f"    {discrepancy_path}")
    print(f"    {report_path}")
    print(f"    {html_path}")

    return 0


def _generate_inter_rater_report(
    stats,
    curators: list,
    output_dir: str,
) -> list:
    """Build inter-rater report as a list of markdown lines."""
    from datetime import datetime
    from collections import Counter

    lines = []
    lines.append("# Inter-Rater Curation Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Curators**: {', '.join(curators)}")
    lines.append(f"**Output Directory**: `{output_dir}`")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append(f"| Total patterns | {stats.n_patterns} |")
    lines.append(f"| Reviewed (2+ decisions) | {stats.n_reviewed} |")
    lines.append(f"| Unanimous agreement | {stats.n_unanimous} "
                 f"({stats.overall_agreement_pct}%) |")
    lines.append(f"| Majority agreement | {stats.n_majority} |")
    lines.append(f"| Split (no majority) | {stats.n_split} |")
    lines.append("")

    # Consensus distribution
    if stats.consensus_decisions:
        dist = Counter(stats.consensus_decisions.values())
        total = sum(dist.values())
        lines.append("## Consensus Distribution")
        lines.append("")
        lines.append("| Decision | Count | % |")
        lines.append("|----------|------:|--:|")
        for cat in ["strip", "skip", "modify"]:
            cnt = dist.get(cat, 0)
            pct = round(cnt / total * 100, 1) if total > 0 else 0
            lines.append(f"| {cat} | {cnt} | {pct}% |")
        # Any other categories
        for cat, cnt in sorted(dist.items()):
            if cat not in ("strip", "skip", "modify"):
                pct = round(cnt / total * 100, 1) if total > 0 else 0
                lines.append(f"| {cat} | {cnt} | {pct}% |")
        lines.append("")

    # Per-category agreement
    if stats.per_category_agreement:
        lines.append("## Per-Category Agreement")
        lines.append("")
        lines.append("| Category | Agreement % |")
        lines.append("|----------|------------|")
        for cat, pct in stats.per_category_agreement.items():
            lines.append(f"| {cat} | {pct}% |")
        lines.append("")

    # Pairwise Cohen's Kappa
    if stats.pairwise_kappas:
        lines.append("## Pairwise Cohen's Kappa")
        lines.append("")
        lines.append("| Curator A | Curator B | Kappa | Observed | Expected | Items |")
        lines.append("|-----------|-----------|------:|---------:|---------:|------:|")
        for pk in stats.pairwise_kappas:
            lines.append(
                f"| {pk.curator_a} | {pk.curator_b} | "
                f"{pk.kappa:.4f} | {pk.observed_agreement:.4f} | "
                f"{pk.expected_agreement:.4f} | {pk.n_items} |"
            )
        lines.append("")
        lines.append("**Interpretation**: "
                     "\u03ba > 0.80 = almost perfect; "
                     "0.60\u20130.80 = substantial; "
                     "0.40\u20130.60 = moderate; "
                     "< 0.40 = fair to poor.")
        lines.append("")

    # Krippendorff's Alpha
    if stats.krippendorff_alpha is not None:
        lines.append("## Krippendorff's Alpha")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|------:|")
        lines.append(f"| Alpha (nominal) | {stats.krippendorff_alpha:.4f} |")
        lines.append(f"| Raters | {stats.n_curators} |")
        lines.append(f"| Items rated | {stats.n_reviewed} |")
        lines.append("")
        lines.append("**Interpretation**: "
                     "\u03b1 > 0.80 = reliable; "
                     "0.67\u20130.80 = tentatively acceptable; "
                     "< 0.67 = unreliable for drawing conclusions.")
        lines.append("")

    # Top discrepancies
    if stats.discrepancies:
        max_show = min(20, len(stats.discrepancies))
        lines.append("## Top Discrepancies")
        lines.append("")
        header = "| Pattern |"
        separator = "|---------|"
        for c in curators:
            header += f" {c} |"
            separator += "------|"
        header += " Consensus |"
        separator += "-----------|"
        lines.append(header)
        lines.append(separator)

        for disc in stats.discrepancies[:max_show]:
            pat_display = disc['pattern']
            if len(pat_display) > 50:
                pat_display = pat_display[:47] + "..."
            row = f"| `{pat_display}` |"
            for c in curators:
                d = disc['decisions'].get(c, '')
                row += f" {d} |"
            row += f" {disc['consensus']} |"
            lines.append(row)

        lines.append("")
        if len(stats.discrepancies) > max_show:
            lines.append(f"*Showing top {max_show} of "
                         f"{len(stats.discrepancies)} discrepancies. "
                         f"See `discrepancies.tsv` and `discrepancies.html` "
                         f"for full details.*")
            lines.append("")

    # Files generated
    lines.append("---")
    lines.append("")
    lines.append("## Files Generated")
    lines.append("")
    lines.append("| File | Description |")
    lines.append("|------|-------------|")
    lines.append("| `consensus.tsv` | All patterns with consensus decisions |")
    lines.append("| `discrepancies.tsv` | Disagreement rows only |")
    lines.append("| `inter_rater_report.md` | This report |")
    lines.append("| `discrepancies.html` | Interactive discrepancy viewer |")
    lines.append("")

    return lines


def _generate_discrepancy_html(
    stats,
    curators: list,
    decisions: dict,
    full_data: dict,
    all_patterns_ordered: list,
    output_path,
) -> None:
    """Generate standalone discrepancy HTML viewer with embedded data."""
    import json
    from pathlib import Path

    # Build data payload
    disc_items = []
    for disc in stats.discrepancies:
        pattern = disc['pattern']
        item = {
            "pattern": pattern,
            "decisions": {},
            "consensus": disc['consensus'],
            "agreement_level": disc['agreement_level'],
        }
        for c in curators:
            row = full_data.get(pattern, {}).get(c, {})
            item["decisions"][c] = {
                "decision": decisions.get(pattern, {}).get(c, ''),
                "modification": row.get('modification', ''),
                "notes": row.get('notes', ''),
            }
        disc_items.append(item)

    payload = {
        "curators": curators,
        "categories": ["strip", "skip", "modify"],
        "stats": {
            "n_patterns": stats.n_patterns,
            "n_reviewed": stats.n_reviewed,
            "n_unanimous": stats.n_unanimous,
            "n_discrepancies": len(stats.discrepancies),
            "overall_agreement_pct": stats.overall_agreement_pct,
            "pairwise_kappas": [
                {
                    "curator_a": pk.curator_a,
                    "curator_b": pk.curator_b,
                    "kappa": pk.kappa,
                    "n_items": pk.n_items,
                }
                for pk in stats.pairwise_kappas
            ],
            "krippendorff_alpha": stats.krippendorff_alpha,
        },
        "discrepancies": disc_items,
    }

    # Read HTML template and embed data
    # Template lives in pattern_util (not copied to curation)
    template_path = Path(__file__).resolve().parent.parent / "pattern_util" / "curation_diff.html"
    if template_path.is_file():
        with open(template_path, encoding='utf-8') as f:
            html = f.read()
        data_script = f"<script>const DIFF_DATA = {json.dumps(payload, ensure_ascii=False)};</script>"
        html = html.replace("<!--DATA_PLACEHOLDER-->", data_script)
    else:
        # Fallback: generate inline HTML if template is missing
        logger.warning(f"Template not found: {template_path}, generating inline HTML")
        html = _generate_inline_discrepancy_html(payload)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def _generate_inline_discrepancy_html(payload: dict) -> str:
    """Fallback: generate a minimal inline HTML if the template is missing."""
    import json
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Curation Discrepancies</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 2em; color: #2d3748; }}
.card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 1em; margin-bottom: 1em; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.85em; font-weight: 600; margin-right: 0.5em; }}
.badge-strip {{ background: #c6f6d5; color: #22543d; }}
.badge-skip {{ background: #fed7d7; color: #9b2c2c; }}
.badge-modify {{ background: #feebc8; color: #7b341e; }}
</style>
</head>
<body>
<h1>Curation Discrepancies</h1>
<p>{payload['stats']['n_discrepancies']} discrepancies out of {payload['stats']['n_reviewed']} reviewed patterns
(agreement: {payload['stats']['overall_agreement_pct']}%)</p>
<div id="cards"></div>
<script>
const DIFF_DATA = {json.dumps(payload, ensure_ascii=False)};
const container = document.getElementById('cards');
DIFF_DATA.discrepancies.forEach(d => {{
  let html = '<div class="card"><strong style="font-family:monospace">' +
    d.pattern + '</strong> <em>(' + d.agreement_level + ')</em><br>';
  for (const [curator, info] of Object.entries(d.decisions)) {{
    const cls = 'badge-' + (info.decision || 'empty');
    html += '<span class="badge ' + cls + '">' + curator + ': ' +
      (info.decision || '\u2014') + '</span>';
    if (info.modification) html += ' \u2192 <em>' + info.modification + '</em>';
    if (info.notes) html += ' <small>(' + info.notes + ')</small>';
  }}
  html += '<br>Consensus: <strong>' + d.consensus + '</strong></div>';
  container.innerHTML += html;
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Centralized curation server
# ---------------------------------------------------------------------------

def _run_serve_curation(args, config_path: str) -> int:
    """
    Start a centralized multi-curator curation server.

    Reads a YAML config file with curator info, TLS settings, and timespan,
    then serves per-curator editor sessions via unique token URLs.
    """
    from pathlib import Path
    from actions.pattern_util.centralized_server import serve_curation

    source_path = getattr(args, 'curation_source', None)
    if not source_path:
        logger.error("--curation-source is required with --serve-curation "
                      "(path to the patterns TSV)")
        raise SystemExit(1)

    no_browser = getattr(args, 'no_browser', False)
    return serve_curation(
        config_path=Path(config_path),
        source_path=Path(source_path),
        no_browser=no_browser,
    )


def _run_curation_status(args, status_dir: str) -> int:
    """
    Show the status of a centralized curation session.

    Reads .curation_state.yaml from the given directory and prints
    curator statuses.
    """
    from pathlib import Path
    import yaml

    state_path = Path(status_dir) / ".curation_state.yaml"
    if not state_path.is_file():
        logger.error(f"No curation state found: {state_path}")
        return 1

    with open(state_path, encoding="utf-8") as fh:
        state = yaml.safe_load(fh)

    print(f"\nCuration Session Status")
    print(f"  Source:   {state.get('source_file', '?')}")
    print(f"  Started:  {state.get('started_at', '?')}")
    print(f"  Expires:  {state.get('expires_at', '?')}")
    print()

    curators = state.get("curators", {})
    if curators:
        max_name = max(len(s) for s in curators) + 2
        print(f"  {'Curator':<{max_name}} {'Status':<12} Last Access")
        print(f"  {'\u2500' * max_name} {'\u2500' * 10}   {'\u2500' * 20}")
        for slug, info in curators.items():
            status = info.get("status", "?")
            last = info.get("last_access") or "\u2014"
            print(f"  {slug:<{max_name}} {status:<12} {last}")
    else:
        print("  No curators found in state file.")

    print()
    return 0


# ---------------------------------------------------------------------------
# Incremental curation: gate + finalize
# ---------------------------------------------------------------------------

def _read_enriched_tsv(path: str):
    """Read an enriched TSV into a list of dicts, preserving all columns."""
    import csv
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(dict(row))
    return rows


def _compute_input_tinyids_hash(input_json: str, model_name: str):
    """Load JSON, extract all tinyIds, return (hash, n_cdes)."""
    import json as _json
    from logic.curation_ledger import CurationLedger

    with open(input_json, encoding="utf-8") as f:
        data = _json.load(f)

    tinyids = set()
    for obj in data:
        tid = obj.get("tinyId", "")
        if tid:
            tinyids.add(tid)

    return CurationLedger.compute_tinyids_hash(tinyids), len(data)


def _write_gate_tsv(path, rows, extra_cols):
    """Write a list of dicts as TSV, adding extra empty columns if missing."""
    import csv

    if not rows:
        # Write header-only file
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("\t".join(extra_cols) + "\n")
        return

    # Determine column order: original columns + extra
    all_keys = list(rows[0].keys())
    for col in extra_cols:
        if col not in all_keys:
            all_keys.append(col)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=all_keys,
            delimiter="\t", lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in all_keys}
            writer.writerow(out)


def _build_curated_from_auto(auto_resolved):
    """Filter auto_resolved to stripped + modified patterns for curated.tsv.

    Returns (curated_rows, substitute_rows).
    Substitute patterns go to a separate file with ``replace_with`` column.
    """
    curated = []
    substitute = []
    for row in auto_resolved:
        decision = row.get("prior_decision", "strip")
        if decision in ("strip", "keep"):  # accept legacy "keep"
            curated.append(row)
        elif decision == "modify":
            modified = dict(row)
            mod_text = row.get("modification", "").strip()
            if mod_text:
                modified["pattern"] = mod_text
            curated.append(modified)
        elif decision == "substitute":
            sub = dict(row)
            sub["replace_with"] = sub.get("modification", "")
            substitute.append(sub)
        # decision == "skip" (or legacy "remove") -> excluded
    return curated, substitute


def _write_curated_tsv(path, rows):
    """Write curated.tsv — only the columns needed by the strip step."""
    import csv

    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("pattern\ttinyIds\n")
        return

    # Preserve all original columns except gate-internal ones
    skip_cols = {"prior_decision", "resolution_source", "decision",
                 "modification", "notes"}
    all_keys = [k for k in rows[0].keys() if k not in skip_cols]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=all_keys,
            delimiter="\t", lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in all_keys}
            writer.writerow(out)


def _write_substitute_tsv(path, rows):
    """Write substitute_patterns.tsv with ``replace_with`` column.

    Writes a header-only file when *rows* is empty so the downstream
    ``strip_phrases`` step is a harmless no-op (zero patterns loaded).
    """
    import csv

    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("pattern\treplace_with\ttinyIds\n")
        return

    # Ensure replace_with is present and move it next to pattern
    skip_cols = {"prior_decision", "resolution_source", "decision",
                 "modification", "notes"}
    priority = ["pattern", "replace_with"]
    remaining = [k for k in rows[0].keys()
                 if k not in skip_cols and k not in priority]
    all_keys = priority + remaining

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=all_keys,
            delimiter="\t", lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in all_keys}
            writer.writerow(out)


def _extract_decisions_from_auto(path):
    """Convert auto_resolved.tsv rows into CurationDecision list."""
    import csv
    import re as _re
    from datetime import datetime
    from logic.curation_ledger import CurationDecision

    decisions = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pattern = row.get("pattern", "")
            if not pattern:
                continue
            prior = row.get("prior_decision", "strip")
            modification = row.get("modification", "")
            tinyids_str = row.get("tinyIds", "")
            tinyids = set(t for t in _re.split(r"[\s|]+", tinyids_str) if t)
            decisions.append(CurationDecision(
                pattern=pattern,
                decision=prior,
                modification=modification,
                tinyIds=tinyids,
                n_tinyIds=len(tinyids),
                decided_at=datetime.now().isoformat(),
                run_id="",
                notes=row.get("notes", ""),
            ))
    return decisions


def _extract_decisions_from_review(path):
    """Convert human-reviewed needs_review.tsv into CurationDecision list."""
    import csv
    import re as _re
    from datetime import datetime
    from logic.curation_ledger import CurationDecision

    # Normalize legacy decision values
    _compat = {"keep": "strip", "remove": "skip"}

    decisions = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pattern = row.get("pattern", "")
            if not pattern:
                continue
            decision = row.get("decision", "").strip().lower()
            if not decision:
                decision = "strip"
            decision = _compat.get(decision, decision)
            modification = row.get("modification", "")
            tinyids_str = row.get("tinyIds", "")
            tinyids = set(t for t in _re.split(r"[\s|]+", tinyids_str) if t)
            decisions.append(CurationDecision(
                pattern=pattern,
                decision=decision,
                modification=modification,
                tinyIds=tinyids,
                n_tinyIds=len(tinyids),
                decided_at=datetime.now().isoformat(),
                run_id="",
                notes=row.get("notes", ""),
            ))
    return decisions


def _run_curation_gate(args, enriched_tsv_path: str) -> int:
    """
    Compare current enriched patterns against the curation ledger.

    Outputs (all in --output directory):
        gate_result.json    — Classification summary + paths
        auto_resolved.tsv   — Patterns auto-resolved from ledger
        needs_review.tsv    — Patterns requiring human curation
        curated.tsv         — Written ONLY when needs_review is empty
    """
    import json as _json
    from datetime import datetime
    from pathlib import Path
    from logic.curation_ledger import CurationLedger, classify_patterns
    from utils.file_utils import exit_if_missing

    output_dir = Path(getattr(args, 'output', None) or '.')
    ledger_dir = getattr(args, 'ledger_dir', None)
    if not ledger_dir:
        ledger_dir = str(output_dir.parent / '.curation_ledger')
    phase = getattr(args, 'phase', None)
    input_json = getattr(args, 'input', None)
    model_name = getattr(args, 'model', 'CDE')

    if not phase:
        logger.error("--phase is required for --curation-gate")
        raise SystemExit(1)
    exit_if_missing(enriched_tsv_path, "Enriched patterns TSV")

    phase_key = "phase1" if phase == "instrument" else "phase2"

    # Load curation ledger
    ledger = CurationLedger(ledger_dir)
    ledger_exists = ledger.load()

    # Read current enriched patterns
    current_patterns = _read_enriched_tsv(enriched_tsv_path)
    logger.info(f"Loaded {len(current_patterns)} patterns from {enriched_tsv_path}")

    # Compute tinyIds hash from input JSON
    tinyids_hash = ""
    n_cdes = 0
    if input_json:
        exit_if_missing(input_json, "Input JSON")
        tinyids_hash, n_cdes = _compute_input_tinyids_hash(input_json, model_name)
        logger.info(f"Input: {n_cdes} CDEs, tinyIds hash: {tinyids_hash[:16]}...")

    # Fast path: identical tinyId set → use prior curation as-is
    if ledger_exists and tinyids_hash and ledger.has_same_tinyids(tinyids_hash):
        prior = ledger.get_decisions(phase_key)
        if prior:
            logger.info("Fast path: tinyIds hash matches prior run")

    # Generate run_id
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Classify patterns
    prior_decisions = ledger.get_decisions(phase_key) if ledger_exists else {}
    auto_resolved, needs_review, summary = classify_patterns(
        current_patterns, prior_decisions
    )

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_gate_tsv(
        output_dir / "auto_resolved.tsv", auto_resolved,
        extra_cols=["prior_decision", "resolution_source", "modification"],
    )

    if needs_review:
        _write_gate_tsv(
            output_dir / "needs_review.tsv", needs_review,
            extra_cols=["decision", "modification", "notes"],
        )
    else:
        # All auto-resolved — write curated.tsv directly
        curated, substitute = _build_curated_from_auto(auto_resolved)
        _write_curated_tsv(output_dir / "curated.tsv", curated)
        _write_substitute_tsv(output_dir / "substitute_patterns.tsv", substitute)

    # Write gate_result.json
    gate_result = {
        "run_id": run_id,
        "phase": phase,
        "phase_key": phase_key,
        "timestamp": datetime.now().isoformat(),
        "input_json": str(input_json) if input_json else "",
        "n_cdes": n_cdes,
        "tinyids_hash": tinyids_hash,
        "enriched_tsv": str(enriched_tsv_path),
        "ledger_dir": str(ledger_dir),
        "summary": summary,
        "all_auto_resolved": len(needs_review) == 0,
        "paths": {
            "auto_resolved": str(output_dir / "auto_resolved.tsv"),
            "needs_review": str(output_dir / "needs_review.tsv") if needs_review else None,
            "curated": str(output_dir / "curated.tsv") if not needs_review else None,
        },
    }
    with open(output_dir / "gate_result.json", "w", encoding="utf-8") as f:
        _json.dump(gate_result, f, indent=2)

    # Print summary
    total = len(current_patterns)
    print(f"\n  Curation gate ({phase}):")
    print(f"    Total patterns:      {total}")
    if ledger_exists:
        print(f"    Auto-strip:          {summary['auto_strip']}")
        print(f"    Auto-skip:           {summary['auto_skip']}")
        print(f"    Auto-modify:         {summary['auto_modify']}")
        if summary.get('auto_substitute', 0):
            print(f"    Auto-substitute:     {summary['auto_substitute']}")
        print(f"    New patterns:        {summary['new_pattern']}")
        n_changed = (summary['changed_tinyids_skip']
                     + summary['changed_tinyids_modify']
                     + summary.get('changed_tinyids_substitute', 0))
        if n_changed:
            print(f"    Changed (re-review): {n_changed}")
    else:
        print(f"    Ledger:              not found (first run)")
        print(f"    Needs review:        {len(needs_review)}")

    if not needs_review:
        print(f"\n    All patterns auto-resolved. Checkpoint will be skipped.")
        print(f"    Wrote: {output_dir / 'curated.tsv'}")
    else:
        print(f"\n    {len(needs_review)} pattern(s) need review.")
        print(f"    Review:        {output_dir / 'needs_review.tsv'}")
        print(f"    Auto-resolved: {output_dir / 'auto_resolved.tsv'}")

    return 0


def _run_finalize_curation(args, gate_dir: str) -> int:
    """
    Merge auto-resolved patterns with human-curated needs_review.tsv,
    then update the curation ledger.

    Runs after the checkpoint (whether skipped or resumed after human review).
    """
    import json as _json
    from pathlib import Path
    from logic.curation_ledger import CurationLedger

    gate_dir_p = Path(gate_dir)
    gate_result_path = gate_dir_p / "gate_result.json"

    if not gate_result_path.exists():
        logger.error(f"gate_result.json not found in {gate_dir}")
        raise SystemExit(1)

    with open(gate_result_path, encoding="utf-8") as f:
        gate_result = _json.load(f)

    ledger_dir = getattr(args, 'ledger_dir', None) or gate_result.get("ledger_dir", "")
    phase = getattr(args, 'phase', None) or gate_result.get("phase", "")
    input_json = getattr(args, 'input', None) or gate_result.get("input_json", "")
    phase_key = gate_result.get("phase_key", "phase1" if phase == "instrument" else "phase2")

    ledger = CurationLedger(ledger_dir)
    ledger.load()

    curated_path = gate_dir_p / "curated.tsv"
    auto_resolved_path = gate_dir_p / "auto_resolved.tsv"
    needs_review_path = gate_dir_p / "needs_review.tsv"

    substitute_path = gate_dir_p / "substitute_patterns.tsv"

    if gate_result.get("all_auto_resolved"):
        # Checkpoint was skipped. curated.tsv + substitute_patterns.tsv
        # already written by gate.
        all_decisions = _extract_decisions_from_auto(str(auto_resolved_path))
        logger.info("Finalize: checkpoint was skipped (all auto-resolved)")
    else:
        # Curator reviewed needs_review.tsv. Merge auto + human.
        if not needs_review_path.exists():
            logger.error(
                f"needs_review.tsv not found in {gate_dir}; "
                f"curation may not be complete"
            )
            raise SystemExit(1)

        auto_rows = _read_enriched_tsv(str(auto_resolved_path))
        review_rows = _read_enriched_tsv(str(needs_review_path))

        # Build curated.tsv + substitute from auto-resolved
        curated_rows, substitute_rows = _build_curated_from_auto(auto_rows)

        # Normalize legacy decision values
        _compat = {"keep": "strip", "remove": "skip"}

        for row in review_rows:
            decision = row.get("decision", "").strip().lower()
            if not decision:
                decision = "strip"
            decision = _compat.get(decision, decision)
            if decision == "strip":
                curated_rows.append(row)
            elif decision == "modify":
                modified = dict(row)
                mod_text = row.get("modification", "").strip()
                if mod_text:
                    modified["pattern"] = mod_text
                curated_rows.append(modified)
            elif decision == "substitute":
                sub_row = dict(row)
                mod_text = row.get("modification", "").strip()
                sub_row["replace_with"] = mod_text if mod_text else ""
                substitute_rows.append(sub_row)
            # decision == "skip" (or legacy "remove") -> excluded

        _write_curated_tsv(curated_path, curated_rows)
        _write_substitute_tsv(substitute_path, substitute_rows)
        logger.info(f"Merged {len(auto_rows)} auto + {len(review_rows)} reviewed "
                     f"\u2192 {len(curated_rows)} curated + "
                     f"{len(substitute_rows)} substitute patterns")

        # Collect all decisions for ledger
        all_decisions = _extract_decisions_from_auto(str(auto_resolved_path))
        all_decisions.extend(_extract_decisions_from_review(str(needs_review_path)))

    # Update ledger
    run_id = gate_result.get("run_id", "unknown")
    for d in all_decisions:
        d.run_id = run_id

    summary = gate_result.get("summary", {})
    ledger.update_decisions(phase_key, all_decisions)
    ledger.record_run(
        run_id=run_id,
        input_json=input_json,
        n_cdes=gate_result.get("n_cdes", 0),
        tinyids_hash=gate_result.get("tinyids_hash", ""),
        phase=phase,
        summary=summary,
    )
    ledger.save()

    # Count substitute patterns (from file if exists)
    n_substitute = 0
    if substitute_path.exists():
        with open(substitute_path, encoding="utf-8") as _sf:
            n_substitute = max(0, sum(1 for _ in _sf) - 1)  # minus header

    print(f"\n  Finalize curation ({phase}):")
    print(f"    Curated patterns:     {curated_path}")
    if n_substitute:
        print(f"    Substitute patterns:  {n_substitute} ({substitute_path})")
    print(f"    Ledger updated:       {ledger_dir}")
    print(f"    Decisions stored:      {len(all_decisions)}")
    print(f"    Run recorded:         {run_id}")

    return 0


# ---------------------------------------------------------------------------
# Interactive TSV editor
# ---------------------------------------------------------------------------

def _run_edit(args, edit_path: str) -> int:
    """
    Launch a local HTTP server serving the interactive TSV editor.

    Pre-loads the specified TSV file and provides REST endpoints for
    save-back. Opens the browser automatically unless --no-browser.
    """
    import json
    import threading
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from pathlib import Path
    from urllib.parse import urlparse

    # Validate input file exists (if specified)
    tsv_path = None
    if edit_path:
        from utils.file_utils import exit_if_missing
        exit_if_missing(edit_path, "TSV file to edit")
        tsv_path = Path(edit_path).resolve()

    # Locate the HTML file in pattern_util (not co-located with this module)
    template_dir = Path(__file__).resolve().parent.parent / "pattern_util"
    html_path = template_dir / "tsv_editor.html"
    if not html_path.exists():
        logger.error(f"Editor HTML not found: {html_path}")
        raise SystemExit(1)

    html_content = html_path.read_bytes()

    # Read TSV content for pre-loading
    tsv_content = ""
    if tsv_path and tsv_path.exists():
        tsv_content = tsv_path.read_text(encoding="utf-8")

    # Build request handler with closure over file state
    class EditorHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ('/', '/index.html'):
                self._serve_bytes(html_content, 'text/html; charset=utf-8')
            elif path == '/data':
                payload = json.dumps({
                    'content': tsv_content,
                    'filename': tsv_path.name if tsv_path else '',
                }).encode('utf-8')
                self._serve_bytes(payload, 'application/json')
            elif path == '/info':
                info = {
                    'path': str(tsv_path) if tsv_path else '',
                    'filename': tsv_path.name if tsv_path else '',
                    'server_mode': True,
                }
                self._serve_bytes(json.dumps(info).encode('utf-8'), 'application/json')
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/save':
                self._handle_save()
            else:
                self.send_error(404)

        def _serve_bytes(self, data, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_save(self):
            nonlocal tsv_content
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                new_content = data['content']
                if tsv_path:
                    tsv_path.write_text(new_content, encoding='utf-8')
                    tsv_content = new_content
                    logger.info(f"Saved {len(new_content)} bytes to {tsv_path}")
                    resp = json.dumps({'status': 'ok', 'path': str(tsv_path)}).encode()
                else:
                    resp = json.dumps({'status': 'error', 'message': 'No file path'}).encode()
                self._serve_bytes(resp, 'application/json')
            except Exception as e:
                logger.error(f"Save failed: {e}")
                self.send_error(500, str(e))

        def log_message(self, format, *log_args):
            pass  # suppress per-request logging

    port = getattr(args, 'port', 0)
    no_browser = getattr(args, 'no_browser', False)

    server = HTTPServer(('127.0.0.1', port), EditorHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    file_desc = f" ({tsv_path.name})" if tsv_path else ""
    print(f"\nTSV Editor{file_desc}")
    print(f"  URL:    {url}")
    if tsv_path:
        print(f"  File:   {tsv_path}")
    print(f"  Press Ctrl-C to stop.\n")

    if not no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nEditor server stopped.")

    return 0


# ---------------------------------------------------------------------------
# Priority split (Zipf-based curation triage)
# ---------------------------------------------------------------------------

def _run_split_priority(args, input_path: str) -> int:
    """Split a needs_review TSV into high-priority and low-priority files.

    Uses wordfreq Zipf frequency scores to classify patterns:
    - Low-priority: ALL word tokens have Zipf >= threshold (common English)
    - High-priority: at least one token has Zipf < threshold (domain-specific)
    """
    import csv
    import re
    from pathlib import Path

    try:
        from wordfreq import zipf_frequency
    except ImportError:
        logger.error("wordfreq package required: pip install wordfreq")
        return 1

    input_file = Path(input_path)
    if not input_file.exists():
        logger.error(f"File not found: {input_file}")
        return 1

    # Use 4.0 as default for split-priority (different from rare-word's 1.5)
    threshold = getattr(args, 'zipf_threshold', None)
    if threshold is None or threshold == 1.5:
        # If still at rare-word default, use the split-priority default
        threshold = 4.0
    auto_remove = getattr(args, 'split_auto_remove', False)

    # Output paths
    stem = input_file.stem
    parent = input_file.parent
    high_path = parent / f"{stem}_high.tsv"
    low_path = parent / f"{stem}_low.tsv"

    _WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*[A-Za-z0-9]|[A-Za-z]")

    def min_word_zipf(pattern: str) -> float:
        """Return the minimum Zipf score across word tokens in a pattern."""
        tokens = _WORD_RE.findall(pattern)
        if not tokens:
            return 0.0
        return min(zipf_frequency(t.lower(), 'en') for t in tokens)

    # Read input
    with open(input_file, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        fieldnames = reader.fieldnames
        if not fieldnames:
            logger.error(f"No columns found in {input_file}")
            return 1
        rows = list(reader)

    # Classify
    high_rows = []
    low_rows = []
    for row in rows:
        pattern = row.get('pattern', '')
        mz = min_word_zipf(pattern)
        if mz >= threshold:
            # All tokens are common English
            if auto_remove and 'decision' in row:
                row['decision'] = 'skip'
            low_rows.append(row)
        else:
            high_rows.append(row)

    # Write high-priority
    with open(high_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                                quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(high_rows)

    # Write low-priority
    with open(low_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                                quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(low_rows)

    print(f"\nPriority split (Zipf threshold={threshold}):")
    print(f"  Input:         {len(rows):>6,d}  {input_file.name}")
    print(f"  High-priority: {len(high_rows):>6,d}  {high_path.name}  (domain-specific, multi-reviewer)")
    print(f"  Low-priority:  {len(low_rows):>6,d}  {low_path.name}  (common English, fast triage)")
    if auto_remove:
        print(f"  Low-priority patterns pre-filled with decision='skip'")
    print(f"\n  Zipf threshold: {threshold} (words with Zipf >= {threshold} are 'common')")
    print(f"  Zipf reference: 3=uncommon, 4=common (~top 6K words), 5=very common")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for curation action."""

    edit_path = getattr(args, 'edit', None)
    if edit_path is not None:
        return _run_edit(args, edit_path)

    init_curation = getattr(args, 'init_curation', None)
    if init_curation:
        return _run_init_curation(args, init_curation)

    merge_curation = getattr(args, 'merge_curation', None)
    if merge_curation:
        return _run_merge_curation(args, merge_curation)

    serve_curation_cfg = getattr(args, 'serve_curation', None)
    if serve_curation_cfg:
        return _run_serve_curation(args, serve_curation_cfg)

    curation_status_dir = getattr(args, 'curation_status', None)
    if curation_status_dir:
        return _run_curation_status(args, curation_status_dir)

    curation_gate = getattr(args, 'curation_gate', None)
    if curation_gate:
        return _run_curation_gate(args, curation_gate)

    finalize_curation = getattr(args, 'finalize_curation', None)
    if finalize_curation:
        return _run_finalize_curation(args, finalize_curation)

    split_priority = getattr(args, 'split_priority', None)
    if split_priority:
        return _run_split_priority(args, split_priority)

    logger.error("No curation mode specified. Use --help for available options.")
    raise SystemExit(1)
