#
# File: actions/pattern_util/run.py
#
"""
Pattern Util - Run module for TSV pattern manipulation.

Provides merge, coalesce, and supplementary import utilities.
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


def add_patterns_to_supplementary(
    curated_tsv_path: str,
    section_name: str = "added_patterns",
    delete_after: bool = True
) -> int:
    """
    Add patterns from curated TSV to supplementary_patterns.yaml.

    Args:
        curated_tsv_path: Path to curated TSV file with 'pattern', 'name' columns
        section_name: YAML section name for imported patterns
        delete_after: If True, delete the TSV file after successful import

    Returns:
        Number of patterns added
    """
    from utils.config_loader import get_config_dir

    config_path = get_config_dir() / "supplementary_patterns.yaml"
    if not config_path.exists():
        logger.error(f"supplementary_patterns.yaml not found at {config_path}")
        raise SystemExit(1)

    # Load existing YAML
    import yaml
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Parse curated TSV - only include rows where 'include' column is 'yes'
    patterns_to_add = []
    with open(curated_tsv_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = [h.lower() for h in header_line.split('\t')]

        # Find required columns
        try:
            pattern_idx = headers.index('pattern')
            name_idx = headers.index('suggested_name') if 'suggested_name' in headers else headers.index('name')
        except ValueError as e:
            logger.error(f"Required column not found: {e}")
            raise SystemExit(1)

        # Find optional columns
        acronym_idx = headers.index('acronym') if 'acronym' in headers else -1
        include_idx = headers.index('include') if 'include' in headers else -1

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')

            # Check include flag if present
            # Strip Excel's auto-added quotes around fields containing commas
            if include_idx >= 0 and include_idx < len(fields):
                include_val = fields[include_idx].strip().strip('"').lower()
                if include_val not in ('yes', 'y', 'true', '1'):
                    continue

            if pattern_idx >= len(fields) or name_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip().strip('"')
            name = fields[name_idx].strip().strip('"')

            if not pattern or not name:
                continue

            entry = {'pattern': pattern, 'name': name}

            if acronym_idx >= 0 and acronym_idx < len(fields):
                acronym = fields[acronym_idx].strip().strip('"')
                if acronym:
                    entry['acronym'] = acronym

            patterns_to_add.append(entry)

    if not patterns_to_add:
        logger.warning("No patterns marked for inclusion (set 'include' column to 'yes')")
        return 0

    # Add to config
    if section_name not in config:
        config[section_name] = []

    # Check for duplicates
    existing_patterns = set()
    for section in config.values():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and 'pattern' in item:
                    existing_patterns.add(item['pattern'])

    added_count = 0
    for entry in patterns_to_add:
        if entry['pattern'] not in existing_patterns:
            config[section_name].append(entry)
            existing_patterns.add(entry['pattern'])
            added_count += 1
        else:
            logger.warning(f"Skipping duplicate pattern: {entry['pattern']}")

    # Write updated YAML
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Added {added_count} patterns to {section_name} section")

    # Delete input file if requested
    if delete_after and added_count > 0:
        os.remove(curated_tsv_path)
        logger.info(f"Deleted curated file: {curated_tsv_path}")

    return added_count


def _extract_acronym(pattern: str):
    """Extract acronym from parenthetical in pattern text, e.g. '(BBS)' → 'BBS'."""
    import re
    m = re.search(r'\(([A-Z][A-Z0-9-]{1,10})\)', pattern)
    return m.group(1) if m else None


def _auto_name(pattern: str) -> str:
    """Generate a display name from pattern text."""
    import re
    # Strip leading articles
    name = re.sub(r'^(?:the|a|an)\s+', '', pattern, flags=re.IGNORECASE)
    # Strip trailing dash/punctuation
    name = re.sub(r'\s*-\s*$', '', name)
    # Title case, but preserve known all-caps (NIH, PROMIS, Neuro-QOL, etc.)
    words = name.split()
    result = []
    preserve = {'NIH', 'PROMIS', 'EEG', 'TMS', 'SPECT', 'ASCOD', 'PBBI', 'ABS',
                'BBS', 'DHI', 'DSQ', 'NSS', 'MNA', 'BQ', 'FPI', 'SCS-PD', 'FLACC',
                'NHANES-PAQ', 'SF-36', 'T25FW', 'VOMS', 'BW', 'ST', 'RFQ-U', 'STOP',
                'PIMS', 'QOL', 'US', 'CDE'}
    for w in words:
        # Preserve parenthetical acronyms
        if re.match(r'^\([A-Z]', w):
            result.append(w)
        elif w.upper() in preserve or w in preserve:
            result.append(w.upper() if w.upper() in preserve else w)
        elif w.startswith('Neuro-') or w.startswith('neuro-'):
            result.append('Neuro-' + w.split('-', 1)[1].upper() if '-' in w else w.title())
        else:
            result.append(w.title() if not w.isupper() or len(w) <= 2 else w)
    return ' '.join(result)


def _categorize_for_section(pattern: str) -> str:
    """Classify a pattern into a supplementary YAML section name."""
    lower = pattern.lower()
    if any(kw in lower for kw in ['questionnaire', 'survey', 'form', 'module']):
        return 'questionnaires'
    elif any(kw in lower for kw in [' test', 'test ']):
        return 'animal_behavioral_tests'
    elif 'model' in lower:
        return 'injury_models'
    elif any(kw in lower for kw in ['scale', 'score', 'index', 'inventory']):
        return 'specific_assessments'
    elif lower.startswith('neuro-qol'):
        return 'neuroqol_subscales'
    elif lower.startswith('promis'):
        return 'questionnaires'
    else:
        return 'specific_assessments'


def _run_harvest_to_supplementary(args, harvest_path: str) -> int:
    """
    Convert harvest/sanity TSV patterns to supplementary YAML entries.

    Reads a TSV with a 'pattern' column, auto-generates name/acronym,
    deduplicates against global + local supplementary patterns, and
    appends new entries to ./supplementary_patterns.yaml (local override).
    """
    import re
    import yaml
    from pathlib import Path
    from collections import defaultdict
    from utils.file_utils import exit_if_missing

    exit_if_missing(harvest_path, "Harvest/sanity TSV")

    # Read patterns from input TSV
    input_patterns = []
    with open(harvest_path, encoding='utf-8') as f:
        header = f.readline().strip().split('\t')
        pat_idx = header.index('pattern') if 'pattern' in header else 0
        for line in f:
            line = line.rstrip('\n\r')
            if not line:
                continue
            fields = line.split('\t')
            if pat_idx < len(fields):
                pat = fields[pat_idx].strip()
                if pat:
                    input_patterns.append(pat)

    if not input_patterns:
        print("No patterns found in input TSV.")
        return 0

    # Filter out truncation artifacts (partial words at start/end)
    clean_patterns = []
    truncated = 0
    for pat in input_patterns:
        # Skip patterns starting mid-word (lowercase fragment before first space)
        if pat and re.match(r'^[a-z]{1,4}\s', pat):
            first_word = pat.split()[0]
            # Allow common articles/prepositions/conjunctions
            if first_word not in {'a', 'an', 'the', 'and', 'or', 'but', 'for',
                                  'in', 'on', 'of', 'to', 'by', 'at', 'as',
                                  'is', 'it', 'be', 'if', 'so', 'no', 'up',
                                  'we', 'he', 'do', 'my', 'me', 'us'}:
                truncated += 1
                logger.info(f"Skipping truncated-start pattern: {pat[:50]}...")
                continue
        # Skip patterns ending with a single letter (truncation artifact)
        if pat and re.search(r'\s[A-Za-z]$', pat):
            truncated += 1
            logger.info(f"Skipping truncated-end pattern: ...{pat[-50:]}")
            continue
        clean_patterns.append(pat)
    if truncated:
        logger.info(f"Filtered {truncated} truncation artifacts from {len(input_patterns)} patterns")
    input_patterns = clean_patterns

    if not input_patterns:
        print(f"No patterns remaining after filtering ({truncated} truncation artifacts removed).")
        return 0

    # Load existing patterns from global + local to deduplicate
    from utils.config_loader import load_supplementary_patterns
    existing = load_supplementary_patterns()
    existing_texts = {p[0].lower() for p in existing}

    # Also load local YAML directly to merge into it
    local_path = Path.cwd() / 'supplementary_patterns.yaml'
    local_config = {}
    if local_path.exists():
        with open(local_path, encoding='utf-8') as f:
            local_config = yaml.safe_load(f) or {}
        # Also add local patterns to dedup set
        for section_items in local_config.values():
            if isinstance(section_items, list):
                for item in section_items:
                    if isinstance(item, dict) and 'pattern' in item:
                        existing_texts.add(item['pattern'].lower())

    # Build new entries, skipping duplicates
    new_by_section = defaultdict(list)
    skipped = 0
    for pat in input_patterns:
        if pat.lower() in existing_texts:
            skipped += 1
            continue
        existing_texts.add(pat.lower())

        entry = {'pattern': pat, 'name': _auto_name(pat)}
        acronym = _extract_acronym(pat)
        if acronym:
            entry['acronym'] = acronym
        section = _categorize_for_section(pat)
        new_by_section[section].append(entry)

    if not new_by_section:
        total_new = 0
        print(f"No new patterns to add ({skipped} already in supplementary).")
        return 0

    # Merge into local config
    for section, entries in new_by_section.items():
        if section not in local_config:
            local_config[section] = []
        local_config[section].extend(entries)

    # Write local supplementary YAML (formatted, not yaml.dump)
    total_new = sum(len(v) for v in new_by_section.values())
    _write_supplementary_yaml(local_path, local_config)

    print(f"Harvest → local supplementary:")
    print(f"  Input:    {len(input_patterns)} patterns from {harvest_path}")
    print(f"  New:      {total_new}")
    print(f"  Skipped:  {skipped} (already in global/local)")
    for section, entries in sorted(new_by_section.items()):
        print(f"    {section}: +{len(entries)}")
    print(f"  Wrote:    {local_path}")
    return 0


def _run_promote_supplementary(args) -> int:
    """
    Promote patterns from local ./supplementary_patterns.yaml into the
    global config/supplementary_patterns.yaml (codebase).

    Appends new entries as formatted YAML text to preserve the global
    file's comments and structure. Patterns already in global are skipped.
    """
    import yaml
    from pathlib import Path
    from utils.config_loader import get_config_dir

    local_path = Path.cwd() / 'supplementary_patterns.yaml'
    if not local_path.exists():
        print(f"No local supplementary file found: {local_path}")
        return 1

    global_path = get_config_dir() / 'supplementary_patterns.yaml'
    if not global_path.exists():
        print(f"Global supplementary file not found: {global_path}")
        return 1

    # Load both configs
    with open(local_path, encoding='utf-8') as f:
        local_config = yaml.safe_load(f) or {}
    with open(global_path, encoding='utf-8') as f:
        global_config = yaml.safe_load(f) or {}

    # Collect existing global patterns for dedup
    global_patterns = set()
    for section_items in global_config.values():
        if isinstance(section_items, list):
            for item in section_items:
                if isinstance(item, dict) and 'pattern' in item:
                    global_patterns.add(item['pattern'].lower())

    # Find new patterns in local, grouped by section
    new_entries = {}  # section → list of entry dicts
    skipped = 0
    for section, items in local_config.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or 'pattern' not in item:
                continue
            if item['pattern'].lower() in global_patterns:
                skipped += 1
                continue
            global_patterns.add(item['pattern'].lower())
            if section not in new_entries:
                new_entries[section] = []
            new_entries[section].append(item)

    if not new_entries:
        total = 0
        print(f"No new patterns to promote ({skipped} already in global).")
        return 0

    # Append to global file as formatted text (preserves existing comments)
    total = sum(len(v) for v in new_entries.values())
    with open(global_path, 'a', encoding='utf-8') as f:
        f.write("\n# =============================================================================\n")
        f.write("# Promoted from local override\n")
        f.write("# =============================================================================\n")
        for section, entries in sorted(new_entries.items()):
            # Check if section already exists in global — if so, we need a
            # distinct section name to avoid YAML key collision
            actual_section = section
            if section in global_config:
                actual_section = f"{section}_promoted"
            f.write(f"{actual_section}:\n")
            for entry in entries:
                f.write(f'  - pattern: "{entry["pattern"]}"\n')
                f.write(f'    name: "{entry.get("name", entry["pattern"])}"\n')
                if 'acronym' in entry:
                    f.write(f'    acronym: "{entry["acronym"]}"\n')
                f.write("\n")

    # Clean local file: remove promoted patterns
    clean = getattr(args, 'clean_local', False)
    if clean:
        remaining = {}
        for section, items in local_config.items():
            if not isinstance(items, list):
                remaining[section] = items
                continue
            kept = [i for i in items if isinstance(i, dict) and
                    i.get('pattern', '').lower() not in global_patterns]
            if kept:
                remaining[section] = kept
        if remaining:
            _write_supplementary_yaml(local_path, remaining)
        else:
            local_path.unlink()
            print(f"  Removed empty local file: {local_path}")

    print(f"Promote local → global:")
    print(f"  Promoted: {total}")
    print(f"  Skipped:  {skipped} (already in global)")
    for section, entries in sorted(new_entries.items()):
        print(f"    {section}: +{len(entries)}")
    print(f"  Global:   {global_path}")
    return 0


def _write_supplementary_yaml(path, config: dict):
    """Write supplementary_patterns.yaml with human-friendly formatting."""
    from pathlib import Path
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# Supplementary instrument patterns (local override)\n")
        f.write("#\n")
        f.write("# Auto-managed by: pattern_util --harvest-to-supplementary\n")
        f.write("# Promote to codebase: pattern_util --promote-supplementary\n\n")
        for section, items in config.items():
            if not isinstance(items, list):
                continue
            f.write(f"{section}:\n")
            for item in items:
                if not isinstance(item, dict) or 'pattern' not in item:
                    continue
                f.write(f'  - pattern: "{item["pattern"]}"\n')
                f.write(f'    name: "{item.get("name", item["pattern"])}"\n')
                if 'acronym' in item:
                    f.write(f'    acronym: "{item["acronym"]}"\n')
                f.write("\n")


# ──────────────────────────────────────────────────────────────
# Multi-curator curation workflow
# ──────────────────────────────────────────────────────────────

def _run_init_curation(args, init_path: str) -> int:
    """
    Create per-curator copies of a patterns TSV with curation columns.

    For each curator name, copies the source TSV and adds four columns:
        decision      — empty (curator fills: keep/remove/modify)
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
    print(f"\n  Next: cde-analyzer pattern_util --edit <curator_file>.tsv")

    return 0


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
        print(f"  Krippendorff α:  {stats.krippendorff_alpha}")
    for pk in stats.pairwise_kappas:
        print(f"  Cohen κ ({pk.curator_a} vs {pk.curator_b}): "
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
        for cat in ["keep", "remove", "modify"]:
            cnt = dist.get(cat, 0)
            pct = round(cnt / total * 100, 1) if total > 0 else 0
            lines.append(f"| {cat} | {cnt} | {pct}% |")
        # Any other categories
        for cat, cnt in sorted(dist.items()):
            if cat not in ("keep", "remove", "modify"):
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
                     "\u03BA > 0.80 = almost perfect; "
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
                     "\u03B1 > 0.80 = reliable; "
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
        "categories": ["keep", "remove", "modify"],
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
    template_path = Path(__file__).resolve().parent / "curation_diff.html"
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
.badge-keep {{ background: #c6f6d5; color: #22543d; }}
.badge-remove {{ background: #fed7d7; color: #9b2c2c; }}
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


def _run_serve_curation(args, config_path: str) -> int:
    """
    Start a centralized multi-curator curation server.

    Reads a YAML config file with curator info, TLS settings, and timespan,
    then serves per-curator editor sessions via unique token URLs.
    """
    from pathlib import Path
    from .centralized_server import serve_curation

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
        print(f"  {'─' * max_name} {'─' * 10}   {'─' * 20}")
        for slug, info in curators.items():
            status = info.get("status", "?")
            last = info.get("last_access") or "—"
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
    """Filter auto_resolved to kept + modified patterns for curated.tsv.

    Returns (curated_rows, substitute_rows).
    Substitute patterns go to a separate file with ``replace_with`` column.
    """
    curated = []
    substitute = []
    for row in auto_resolved:
        decision = row.get("prior_decision", "keep")
        if decision == "keep":
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
        # decision == "remove" -> excluded
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
            prior = row.get("prior_decision", "keep")
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

    decisions = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pattern = row.get("pattern", "")
            if not pattern:
                continue
            decision = row.get("decision", "").strip().lower()
            if not decision:
                decision = "keep"
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
        print(f"    Auto-keep:           {summary['auto_keep']}")
        print(f"    Auto-remove:         {summary['auto_remove']}")
        print(f"    Auto-modify:         {summary['auto_modify']}")
        if summary.get('auto_substitute', 0):
            print(f"    Auto-substitute:     {summary['auto_substitute']}")
        print(f"    New patterns:        {summary['new_pattern']}")
        n_changed = (summary['changed_tinyids_remove']
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

        for row in review_rows:
            decision = row.get("decision", "").strip().lower()
            if not decision:
                decision = "keep"
            if decision == "keep":
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
            # decision == "remove" -> excluded

        _write_curated_tsv(curated_path, curated_rows)
        _write_substitute_tsv(substitute_path, substitute_rows)
        logger.info(f"Merged {len(auto_rows)} auto + {len(review_rows)} reviewed "
                     f"→ {len(curated_rows)} curated + "
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


def _run_to_minimal(args, input_path: str) -> int:
    """
    Normalize any pattern TSV to minimal 2-column format: pattern<TAB>tinyIds

    Auto-detects column names and normalizes tinyId separator to pipe (|).
    """
    import re
    from utils.file_utils import exit_if_missing
    from utils.pattern_tsv_utils import find_column_index

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --to-minimal")
        raise SystemExit(1)

    exit_if_missing(input_path, "Patterns TSV")

    rows = []  # (pattern, tinyids_normalized)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        # Auto-detect pattern column
        pattern_idx = find_column_index(headers, 'pattern')

        # Auto-detect tinyIds column (try multiple variations)
        tinyids_idx = None
        for name in ['tinyIds', 'tinyids', 'tinyId', 'tinyid']:
            try:
                tinyids_idx = find_column_index(headers, name)
                break
            except ValueError:
                continue
        if tinyids_idx is None:
            logger.error("Could not find tinyIds column (tried: tinyIds, tinyids, tinyId, tinyid)")
            raise SystemExit(1)

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""

            if not pattern:
                continue

            # Normalize separator: split on space or pipe, rejoin with pipe
            tinyids_list = [t for t in re.split(r'[\s|]+', tinyids_str) if t]
            tinyids_normalized = "|".join(tinyids_list)

            rows.append((pattern, tinyids_normalized))

    logger.info(f"Loaded {len(rows)} patterns from {input_path}")

    # Write minimal output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\n")
        for pattern, tinyids in rows:
            f.write(f"{pattern}\t{tinyids}\n")

    print(f"\nNormalized to minimal format:")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path} ({len(rows)} patterns)")
    print(f"  Format: pattern<TAB>tinyIds (pipe-separated)")

    return 0


def _load_exclusion_set(exclude_path: str) -> set:
    """Load exclusion patterns from a file (one per line, or TSV with 'pattern' column)."""
    exclusions = set()
    with open(exclude_path, encoding="utf-8") as f:
        first_line = f.readline().strip()
        headers = first_line.split('\t')
        if 'pattern' in [h.lower() for h in headers]:
            # TSV with header
            from utils.pattern_tsv_utils import find_column_index
            idx = find_column_index(headers, 'pattern')
            for line in f:
                line = line.strip()
                if line:
                    fields = line.split('\t')
                    if idx < len(fields):
                        exclusions.add(fields[idx].strip().strip('"'))
        else:
            # Plain text, first line is a pattern too
            if first_line:
                exclusions.add(first_line)
            for line in f:
                line = line.strip()
                if line:
                    exclusions.add(line)
    return exclusions


def _load_rare_word_whitelist(explicit_path: str = None) -> set:
    """Load rare-word whitelist from YAML config(s).

    Loading order (all merged):
      1. Global: config/rare_word_whitelist.yaml
      2. Local:  ./rare_word_whitelist.yaml (per-dataset override)
      3. Explicit: --rare-word-whitelist path (if provided)

    YAML format: top-level keys are category names mapping to lists of words.
    All categories are merged into a single set.  Words are lowercased.
    """
    import yaml
    from pathlib import Path

    words = set()

    def _read_yaml(path: Path) -> None:
        if not path.is_file():
            return
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return
        for category, word_list in data.items():
            if isinstance(word_list, list):
                for w in word_list:
                    if isinstance(w, str) and w.strip():
                        words.add(w.strip().lower())
        logger.info(f"  Whitelist loaded: {path} ({len(words)} cumulative)")

    # Global config
    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    _read_yaml(config_dir / "rare_word_whitelist.yaml")

    # Local override (extends global)
    _read_yaml(Path.cwd() / "rare_word_whitelist.yaml")

    # Explicit path (if provided via --rare-word-whitelist)
    if explicit_path:
        p = Path(explicit_path)
        if not p.is_file():
            logger.warning(f"Whitelist file not found: {explicit_path}")
        else:
            _read_yaml(p)

    return words


def _field_tag(field_type: str, index: int) -> str:
    """Generate field tag for example_context column.

    Designation labels: [des N] (name, pos 0), [des Q] (question, pos 1),
    [des 2], [des 3], etc. for higher positions.
    Definition labels: [def] (pos 0), [def 1], [def 2], etc.
    """
    if field_type == "des":
        if index == 0:
            return "[des N]"
        if index == 1:
            return "[des Q]"
        return f"[des {index}]"
    # definitions
    if index == 0:
        return "[def]"
    return f"[def {index}]"


def _run_field_analysis(args, field_analysis_path: str) -> int:
    """
    Enrich a patterns TSV with per-field tinyId counts and field_profile.

    Reads patterns + tinyIds from the input TSV, scans the source JSON to
    determine which fields each pattern appears in, and writes an enriched
    TSV with additional columns.
    """
    import json
    import re
    from pydantic import ValidationError
    from utils.constants import MODEL_REGISTRY
    from utils.file_utils import exit_if_missing
    from actions.strip_discover.run import compute_field_distribution, _field_profile

    # Validate required args
    input_json = getattr(args, 'input', None)
    output_path = getattr(args, 'output', None)
    if not input_json:
        logger.error("--input (CDE JSON) is required for --field-analysis")
        raise SystemExit(1)
    if not output_path:
        logger.error("--output is required for --field-analysis")
        raise SystemExit(1)

    exit_if_missing(field_analysis_path, "Patterns TSV")
    exit_if_missing(input_json, "Input JSON")

    model_name = getattr(args, 'model', 'CDE')
    field_paths = getattr(args, 'fields',
                          ["definitions.*.definition", "designations.*.designation"])
    min_field_count = getattr(args, 'min_field_count', 0)
    min_tokens = getattr(args, 'min_tokens', 0)
    exclude_path = getattr(args, 'exclude_patterns', None)
    dedup_phrases_path = getattr(args, 'dedup_phrases', None)

    # Load exclusion set if provided
    exclusion_set = set()
    if exclude_path:
        exit_if_missing(exclude_path, "Exclusion patterns file")
        exclusion_set = _load_exclusion_set(exclude_path)
        logger.info(f"Loaded {len(exclusion_set)} exclusion patterns")

    # Load dedup phrase texts for substring filtering
    dedup_texts = []
    if dedup_phrases_path:
        exit_if_missing(dedup_phrases_path, "Dedup phrases file")
        with open(dedup_phrases_path, encoding="utf-8") as df:
            header = df.readline().strip().split('\t')
            text_idx = 0  # verbatim_text is first column
            for i, h in enumerate(header):
                if h.lower() == 'verbatim_text':
                    text_idx = i
                    break
            for line in df:
                fields = line.strip().split('\t')
                if text_idx < len(fields) and fields[text_idx].strip():
                    dedup_texts.append(fields[text_idx].strip().lower())
        logger.info(f"Loaded {len(dedup_texts)} dedup phrases for substring filtering")

    # Read the patterns TSV (preserve all columns)
    rows = []  # list of (fields_list, pattern, tinyids_set)
    with open(field_analysis_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            rows.append((fields, pattern, tinyids))

    logger.info(f"Loaded {len(rows)} patterns from {field_analysis_path}")

    # Build verbatim_map for compute_field_distribution
    verbatim_map = {pattern: tinyids for _, pattern, tinyids in rows if pattern}

    # Load and parse CDE JSON
    model_class = MODEL_REGISTRY[model_name]
    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records from {input_json}")

    # Build CDE text lookup: tinyId -> (name, fields_list)
    # name = designations[0] (CDE identity); fields_list = [(tag, text), ...] for all fields
    MAX_EXAMPLE_LEN = 120
    cde_text_lookup = {}
    for model in parsed:
        tid = getattr(model, 'tinyId', None)
        if not tid:
            continue
        desigs = getattr(model, 'designations', None) or []
        defs = getattr(model, 'definitions', None) or []
        name = ""
        if desigs:
            name = getattr(desigs[0], 'designation', '') or ''
            if len(name) > MAX_EXAMPLE_LEN:
                name = name[:MAX_EXAMPLE_LEN] + "..."
        fields_list = []
        for i, d in enumerate(desigs):
            text = getattr(d, 'designation', '') or ''
            if text:
                fields_list.append((_field_tag("des", i), text))
        for i, d in enumerate(defs):
            text = getattr(d, 'definition', '') or ''
            if text:
                fields_list.append((_field_tag("def", i), text))
        cde_text_lookup[tid] = (name, fields_list)

    # Compute field distribution
    field_dist = compute_field_distribution(parsed, verbatim_map, field_paths)

    # Derive field column names
    field_col_names = [fp.rsplit('.', 1)[-1] for fp in field_paths]

    # Apply filters and write output
    # Strip existing field/example columns from header if re-running
    EXAMPLE_COLS = {"example_name", "example_question", "example_definition", "example_context"}
    drop_cols = set()
    for col in field_col_names:
        col_count = f"{col}_count"
        if col_count in headers:
            drop_cols.add(col_count)
    if "field_profile" in headers:
        drop_cols.add("field_profile")
    if "tinyid_count" in headers:
        drop_cols.add("tinyid_count")
    for ec in EXAMPLE_COLS:
        if ec in headers:
            drop_cols.add(ec)

    # Build clean header (remove old field/example columns if present)
    clean_header_indices = [i for i, h in enumerate(headers) if h not in drop_cols]
    clean_headers = [headers[i] for i in clean_header_indices]

    # Position to insert example columns: right after 'pattern'
    pattern_pos = clean_headers.index("pattern") if "pattern" in clean_headers else 0
    example_insert_at = pattern_pos + 1  # used when building each output row

    # Build final header: clean + example cols inserted after pattern + field cols at end
    new_headers = clean_headers[:]
    for j, ec in enumerate(["example_name", "example_context"]):
        new_headers.insert(example_insert_at + j, ec)
    for col in field_col_names:
        new_headers.append(f"{col}_count")
    new_headers.append("field_profile")
    # Insert tinyid_count right after tinyIds
    tinyid_count_pos = -1
    if "tinyIds" in new_headers:
        tinyid_count_pos = new_headers.index("tinyIds") + 1
        new_headers.insert(tinyid_count_pos, "tinyid_count")

    filtered_count = 0
    excluded_count = 0
    written_count = 0

    # Collect enriched rows for sorting before writing
    enriched_rows = []  # list of (clean_fields, group_key_val, profile, pattern)

    # Determine group_key index (if column exists in input)
    group_key_idx = headers.index("group_key") if "group_key" in headers else None

    for fields_list, pattern, tinyids in rows:
        if not pattern:
            continue

        # Exclusion filter
        if pattern in exclusion_set:
            excluded_count += 1
            continue

        # Dedup substring filter: remove patterns that are fragments of long dedup phrases
        if dedup_texts and any(pattern.lower() in dt for dt in dedup_texts):
            excluded_count += 1
            continue

        # Min-tokens filter
        if min_tokens > 0 and len(pattern.split()) < min_tokens:
            filtered_count += 1
            continue

        # Get field distribution
        dist = field_dist.get(pattern, {})
        field_counts = {col: len(dist.get(col, set())) for col in field_col_names}

        # Min-field-count filter: drop if below threshold in ALL fields
        if min_field_count > 0:
            if all(c < min_field_count for c in field_counts.values()):
                filtered_count += 1
                continue

        # Build output row from clean columns
        clean_fields = [fields_list[i] if i < len(fields_list) else ""
                        for i in clean_header_indices]

        # Look up example CDE: find a tinyId where the pattern actually appears
        ex_name = ""
        ex_context = ""
        if tinyids:
            pat_lower = pattern.lower()
            for tid in sorted(tinyids):
                entry = cde_text_lookup.get(tid)
                if not entry:
                    continue
                name, fields_list = entry
                if not ex_name and name:
                    ex_name = name
                for tag, text in fields_list:
                    if pat_lower in text.lower():
                        trunc = text if len(text) <= MAX_EXAMPLE_LEN else text[:MAX_EXAMPLE_LEN] + "..."
                        ex_context = f"{tag} {trunc}"
                        break
                if ex_context:
                    break
            # Fallback: use first tinyId's name if no match found
            if not ex_name:
                first_entry = cde_text_lookup.get(next(iter(sorted(tinyids)), None))
                if first_entry:
                    ex_name = first_entry[0]
        # Insert 2 example columns right after pattern position
        for j, val in enumerate([ex_name, ex_context]):
            clean_fields.insert(example_insert_at + j, val)
        # Insert tinyid_count after tinyIds
        if tinyid_count_pos >= 0:
            clean_fields.insert(tinyid_count_pos, str(len(tinyids)))

        # Append field columns at end
        for col in field_col_names:
            clean_fields.append(str(field_counts[col]))
        profile = _field_profile(dist) if dist else ""
        clean_fields.append(profile)

        # Extract group_key for sorting
        group_key_val = ""
        if group_key_idx is not None:
            group_key_val = fields_list[group_key_idx] if group_key_idx < len(fields_list) else ""

        enriched_rows.append((clean_fields, group_key_val, profile, pattern))

    # Sort by group_key → field_profile → pattern for curation readability
    PROFILE_ORDER = {"def-only": 0, "desig-only": 1, "both-all": 2, "mixed": 3, "": 4}
    enriched_rows.sort(key=lambda r: (
        r[1],                              # group_key
        PROFILE_ORDER.get(r[2], 4),        # field_profile
        r[3],                              # pattern
    ))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(new_headers) + "\n")
        for clean_fields, _, _, _ in enriched_rows:
            f.write("\t".join(clean_fields) + "\n")
            written_count += 1

    print(f"\nField analysis complete:")
    print(f"  Input:    {len(rows)} patterns")
    if excluded_count:
        excluded_sources = []
        if exclude_path:
            excluded_sources.append("exclusion list")
        if dedup_texts:
            excluded_sources.append("dedup substring")
        print(f"  Excluded: {excluded_count} ({', '.join(excluded_sources)})")
    if filtered_count:
        print(f"  Filtered: {filtered_count} (min-field-count={min_field_count}, min-tokens={min_tokens})")
    print(f"  Output:   {written_count} patterns (sorted: group \u2192 field \u2192 pattern)")
    print(f"  Wrote:    {output_path}")

    return 0


def _run_harvest_residuals(args, sanity_path: str) -> int:
    """
    Cross-reference sanity check residuals against curated patterns.

    Classifies each residual as:
      - should_have_matched: a curated pattern is a substring of the residual
        (stripping gap — auto-included for re-strip)
      - partial_match: the residual is a substring of a curated pattern
      - new_candidate: genuinely new pattern

    Writes harvest.tsv for iterative stripping.
    """
    import json
    import re
    from pydantic import ValidationError
    from utils.constants import MODEL_REGISTRY
    from utils.file_utils import exit_if_missing
    from actions.strip_discover.run import compute_field_distribution, _field_profile

    output_path = getattr(args, 'output', None)
    curated_path = getattr(args, 'curated', None)
    input_json = getattr(args, 'input', None)
    if not output_path:
        logger.error("--output is required for --harvest-residuals")
        raise SystemExit(1)
    if not curated_path:
        logger.error("--curated is required for --harvest-residuals")
        raise SystemExit(1)

    exit_if_missing(sanity_path, "Sanity check TSV")
    exit_if_missing(curated_path, "Curated patterns TSV")

    # Load curated patterns (just the pattern text)
    curated_patterns = set()
    with open(curated_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        curated_headers = header_line.split('\t')
        from utils.pattern_tsv_utils import find_column_index
        c_pat_idx = find_column_index(curated_headers, 'pattern')
        for line in f:
            fields = line.rstrip('\n\r').split('\t')
            if c_pat_idx < len(fields):
                pat = fields[c_pat_idx].strip().strip('"')
                if pat:
                    curated_patterns.add(pat)

    logger.info(f"Loaded {len(curated_patterns)} curated patterns from {curated_path}")

    # Load residuals from sanity TSV
    residuals = []  # list of (pattern, count, tinyids_set)
    with open(sanity_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        sanity_headers = header_line.split('\t')
        from utils.pattern_tsv_utils import find_column_index
        s_pat_idx = find_column_index(sanity_headers, 'pattern')
        s_count_idx = sanity_headers.index('count') if 'count' in sanity_headers else None
        s_tinyids_idx = sanity_headers.index('tinyIds') if 'tinyIds' in sanity_headers else None

        for line in f:
            fields = line.rstrip('\n\r').split('\t')
            if s_pat_idx >= len(fields):
                continue
            pat = fields[s_pat_idx].strip().strip('"')
            if not pat:
                continue
            count = int(fields[s_count_idx]) if s_count_idx is not None and s_count_idx < len(fields) else 0
            tinyids = set()
            if s_tinyids_idx is not None and s_tinyids_idx < len(fields):
                tinyids_str = fields[s_tinyids_idx].strip().strip('"')
                if tinyids_str:
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            residuals.append((pat, count, tinyids))

    logger.info(f"Loaded {len(residuals)} residual patterns from {sanity_path}")

    # Classify each residual
    harvest_rows = []  # (pattern, tinyids, match_type, matched_pattern)
    curated_lower = {p: p for p in curated_patterns}  # identity for case-sensitive

    for res_pat, res_count, res_tinyids in residuals:
        match_type = "new_candidate"
        matched_pattern = ""

        # Check: is a curated pattern a substring of this residual?
        for cur_pat in curated_patterns:
            if cur_pat in res_pat and cur_pat != res_pat:
                match_type = "should_have_matched"
                matched_pattern = cur_pat
                break

        # Check: is this residual a substring of a curated pattern?
        if match_type == "new_candidate":
            for cur_pat in curated_patterns:
                if res_pat in cur_pat and res_pat != cur_pat:
                    match_type = "partial_match"
                    matched_pattern = cur_pat
                    break

        harvest_rows.append((res_pat, res_tinyids, match_type, matched_pattern))

    # For new_candidate patterns without tinyIds, compute field distribution if source JSON available
    needs_field_scan = any(
        match_type in ("new_candidate", "should_have_matched") and not tinyids
        for _, tinyids, match_type, _ in harvest_rows
    )

    field_dist = {}
    if needs_field_scan and input_json:
        exit_if_missing(input_json, "Input JSON")
        model_name = getattr(args, 'model', 'CDE')
        model_class = MODEL_REGISTRY[model_name]
        field_paths = getattr(args, 'fields',
                              ["definitions.*.definition", "designations.*.designation"])

        with open(input_json, encoding="utf-8") as f:
            data = json.load(f)
        try:
            parsed = [model_class.model_validate(obj) for obj in data]
        except ValidationError as e:
            for error in e.errors():
                logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
            raise SystemExit(1)

        # Build verbatim_map for patterns needing field scan
        verbatim_map = {}
        for pat, tids, mtype, _ in harvest_rows:
            if mtype in ("new_candidate", "should_have_matched") and not tids:
                verbatim_map[pat] = set()  # empty — compute_field_distribution will find them
        # Actually need to discover tinyIds first for these patterns
        # Rescan the JSON to find which tinyIds contain each pattern
        for model in parsed:
            tid = getattr(model, 'tinyId', None)
            if not tid:
                continue
            model_dict = model.model_dump(mode="python")
            from logic.verbatim_discoverer import _extract_at_path
            for fp in field_paths:
                texts = _extract_at_path(model_dict, fp.split('.'))
                for text in texts:
                    if text and isinstance(text, str):
                        text_lower = text.lower()
                        for pat in verbatim_map:
                            if pat.lower() in text_lower:
                                verbatim_map[pat].add(tid)

        # Update harvest_rows with discovered tinyIds
        for i, (pat, tids, mtype, matched) in enumerate(harvest_rows):
            if pat in verbatim_map and not tids:
                harvest_rows[i] = (pat, verbatim_map[pat], mtype, matched)

        # Now compute field distribution
        field_dist = compute_field_distribution(parsed, verbatim_map, field_paths)
    elif input_json:
        # Compute field distribution for patterns that already have tinyIds
        model_name = getattr(args, 'model', 'CDE')
        model_class = MODEL_REGISTRY[model_name]
        field_paths = getattr(args, 'fields',
                              ["definitions.*.definition", "designations.*.designation"])

        verbatim_map = {pat: tids for pat, tids, mtype, _ in harvest_rows
                        if mtype in ("new_candidate", "should_have_matched") and tids}
        if verbatim_map:
            exit_if_missing(input_json, "Input JSON")
            with open(input_json, encoding="utf-8") as f:
                data = json.load(f)
            try:
                parsed = [model_class.model_validate(obj) for obj in data]
            except ValidationError as e:
                for error in e.errors():
                    logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
                raise SystemExit(1)
            field_dist = compute_field_distribution(parsed, verbatim_map, field_paths)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\tmatch_type\tmatched_pattern\tdefinition_count\tdesignation_count\tfield_profile\n")
        for pat, tinyids, match_type, matched_pattern in harvest_rows:
            tinyids_str = " ".join(sorted(tinyids)) if tinyids else ""
            dist = field_dist.get(pat, {})
            def_count = len(dist.get("definition", set()))
            desig_count = len(dist.get("designation", set()))
            profile = _field_profile(dist) if dist else ""
            f.write(f"{pat}\t{tinyids_str}\t{match_type}\t{matched_pattern}\t{def_count}\t{desig_count}\t{profile}\n")

    # Summary
    type_counts = {}
    for _, _, mtype, _ in harvest_rows:
        type_counts[mtype] = type_counts.get(mtype, 0) + 1

    print(f"\nHarvest complete:")
    print(f"  Residuals:           {len(residuals)}")
    for mtype, count in sorted(type_counts.items()):
        print(f"  {mtype:23s}{count}")
    print(f"  Wrote:               {output_path}")

    return 0


def _run_update_ledger(args, new_patterns_path: str) -> int:
    """
    Update a cumulative pattern ledger with new patterns.

    The ledger tracks all patterns seen across iterations, with source,
    round, and status metadata. New patterns are added; existing patterns
    get their tinyIds unioned and notes updated.

    Schema: pattern | tinyIds | source | round | field_profile | status | notes
    """
    import re
    from utils.file_utils import exit_if_missing

    ledger_path = getattr(args, 'ledger', None)
    output_path = getattr(args, 'output', None)
    source = getattr(args, 'source', 'unknown')
    round_num = getattr(args, 'round', 1)

    if not ledger_path:
        logger.error("--ledger is required for --update-ledger")
        raise SystemExit(1)
    if not output_path:
        logger.error("--output is required for --update-ledger")
        raise SystemExit(1)

    exit_if_missing(new_patterns_path, "New patterns TSV")

    LEDGER_HEADERS = ["pattern", "tinyIds", "source", "round", "field_profile", "status", "notes"]

    # Load existing ledger (or start empty)
    ledger = {}  # pattern -> {tinyIds: set, source: str, round: int, field_profile: str, status: str, notes: str}
    if os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as f:
            header_line = f.readline().strip()
            headers = header_line.split('\t')
            idx = {h: i for i, h in enumerate(headers)}
            for line in f:
                fields = line.rstrip('\n\r').split('\t')
                pat = fields[idx.get('pattern', 0)].strip().strip('"') if idx.get('pattern', 0) < len(fields) else ""
                if not pat:
                    continue
                tinyids_str = fields[idx['tinyIds']].strip().strip('"') if 'tinyIds' in idx and idx['tinyIds'] < len(fields) else ""
                tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
                ledger[pat] = {
                    'tinyIds': tinyids,
                    'source': fields[idx['source']] if 'source' in idx and idx['source'] < len(fields) else "",
                    'round': fields[idx['round']] if 'round' in idx and idx['round'] < len(fields) else "",
                    'field_profile': fields[idx['field_profile']] if 'field_profile' in idx and idx['field_profile'] < len(fields) else "",
                    'status': fields[idx['status']] if 'status' in idx and idx['status'] < len(fields) else "active",
                    'notes': fields[idx['notes']] if 'notes' in idx and idx['notes'] < len(fields) else "",
                }
        logger.info(f"Loaded {len(ledger)} existing ledger entries from {ledger_path}")
    else:
        logger.info(f"No existing ledger at {ledger_path}; creating new")

    # Load new patterns
    new_count = 0
    updated_count = 0
    with open(new_patterns_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        new_headers = header_line.split('\t')
        from utils.pattern_tsv_utils import find_column_index
        pat_idx = find_column_index(new_headers, 'pattern')
        tid_idx = new_headers.index('tinyIds') if 'tinyIds' in new_headers else None
        fp_idx = new_headers.index('field_profile') if 'field_profile' in new_headers else None

        for line in f:
            fields = line.rstrip('\n\r').split('\t')
            if pat_idx >= len(fields):
                continue
            pat = fields[pat_idx].strip().strip('"')
            if not pat:
                continue

            tinyids = set()
            if tid_idx is not None and tid_idx < len(fields):
                tinyids_str = fields[tid_idx].strip().strip('"')
                if tinyids_str:
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)

            field_profile = ""
            if fp_idx is not None and fp_idx < len(fields):
                field_profile = fields[fp_idx].strip()

            if pat in ledger:
                # Update existing entry
                ledger[pat]['tinyIds'].update(tinyids)
                if field_profile:
                    ledger[pat]['field_profile'] = field_profile
                existing_notes = ledger[pat].get('notes', '')
                re_seen = f"re-seen round {round_num}"
                if re_seen not in existing_notes:
                    ledger[pat]['notes'] = f"{existing_notes}; {re_seen}" if existing_notes else re_seen
                updated_count += 1
            else:
                # New entry
                ledger[pat] = {
                    'tinyIds': tinyids,
                    'source': source,
                    'round': str(round_num),
                    'field_profile': field_profile,
                    'status': 'active',
                    'notes': '',
                }
                new_count += 1

    # Write updated ledger
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(LEDGER_HEADERS) + "\n")
        for pat, entry in sorted(ledger.items()):
            tinyids_str = " ".join(sorted(entry['tinyIds']))
            f.write(f"{pat}\t{tinyids_str}\t{entry['source']}\t{entry['round']}\t"
                    f"{entry['field_profile']}\t{entry['status']}\t{entry['notes']}\n")

    active_count = sum(1 for e in ledger.values() if e.get('status', 'active') == 'active')

    print(f"\nLedger update complete:")
    print(f"  New:      {new_count}")
    print(f"  Updated:  {updated_count}")
    print(f"  Active:   {active_count}")
    print(f"  Total:    {len(ledger)}")
    print(f"  Wrote:    {output_path}")

    return 0


# ---------------------------------------------------------------------------
# Empirical subsumption validation — worker functions (module-level for pickling)
# ---------------------------------------------------------------------------

_validate_field_index = None  # Set by worker initializer


def _validate_worker_init(field_index):
    """Initialize shared read-only field index in each worker process."""
    global _validate_field_index
    _validate_field_index = field_index


def _validate_group(group_key, patterns_with_tinyids, field_index):
    """Determine which patterns in a group are empirically needed.

    A pattern is "needed" if there exists at least one (tinyId, field) where
    it matches in the source text but no LONGER group member (that contains
    it as a substring) also matches.

    Returns list of (group_key, pattern, tinyIds, validation_reason) tuples.
    """
    if len(patterns_with_tinyids) <= 1:
        return [(group_key, p, t, "only_in_group") for p, t in patterns_with_tinyids]

    # Sort longest first
    sorted_pats = sorted(patterns_with_tinyids, key=lambda x: len(x[0]), reverse=True)

    # Step 1: Build match matrix — which (tinyId, field) each pattern matches
    pattern_matches = {}
    for pattern, tinyids in sorted_pats:
        matches = set()
        pat_lower = pattern.lower()
        for tid in tinyids:
            if tid not in field_index:
                continue
            for field_path, texts in field_index[tid].items():
                for text in texts:
                    if pat_lower in text.lower():
                        matches.add((tid, field_path))
                        break
        pattern_matches[pattern] = matches

    # Step 2: Determine which patterns are needed
    kept = []
    for i, (pattern, tinyids) in enumerate(sorted_pats):
        # Find longer patterns in this group that contain this pattern as substring
        longer_containing = [
            p for p, _ in sorted_pats[:i]
            if pattern.lower() in p.lower() and p != pattern
        ]

        if not longer_containing:
            # Longest in its substring chain — always needed
            kept.append((group_key, pattern, tinyids, "longest_in_chain"))
            continue

        # Union of all (tinyId, field) matched by longer patterns
        longer_match_union = set()
        for lp in longer_containing:
            longer_match_union.update(pattern_matches.get(lp, set()))

        # Pattern is needed if it matches somewhere the longer ones don't
        unique_matches = pattern_matches[pattern] - longer_match_union
        if unique_matches:
            kept.append((group_key, pattern, tinyids, "independent_matches"))
        # else: pattern is redundant — every occurrence is covered by a longer form

    return kept


def _validate_worker_process(groups_chunk):
    """Worker: validate a chunk of groups using the shared field index."""
    results = []
    for group_key, patterns_with_tinyids in groups_chunk:
        kept = _validate_group(group_key, patterns_with_tinyids, _validate_field_index)
        results.extend(kept)
    return results


def _run_validate_subsumption(args, coalesced_path: str) -> int:
    """Empirical subsumption validation for coalesced pattern groups.

    For each coalesced group, checks source text per-tinyId per-field to
    determine which patterns are actually needed. Drops shorter patterns
    whose occurrences are always covered by longer group members.
    """
    import json
    import re
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from utils.file_utils import exit_if_missing
    from utils.constants import MODEL_REGISTRY
    from pydantic import ValidationError

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --validate-subsumption")
        raise SystemExit(1)

    input_path = getattr(args, 'input', None)
    model_name = getattr(args, 'model', None)
    if not input_path or not model_name:
        logger.error("--input and --model are required for --validate-subsumption")
        raise SystemExit(1)

    n_workers = getattr(args, 'workers', 0)
    field_paths = getattr(args, 'fields', None) or [
        "definitions.*.definition", "designations.*.designation"
    ]

    # --- Load coalesced groups ---
    coalesced_path = exit_if_missing(coalesced_path, "Coalesced TSV")
    groups = {}  # group_key -> [(pattern, tinyIds_set)]
    total_patterns = 0

    with open(coalesced_path, encoding='utf-8') as f:
        header = f.readline().strip().split('\t')
        gk_idx = header.index('group_key')
        pat_idx = header.index('pattern')
        tid_idx = header.index('tinyIds')

        for line in f:
            cols = line.strip().split('\t')
            if len(cols) <= max(gk_idx, pat_idx, tid_idx):
                continue
            gk = cols[gk_idx]
            pat = cols[pat_idx]
            tids = set(re.split(r'[\s|]+', cols[tid_idx])) if cols[tid_idx].strip() else set()
            groups.setdefault(gk, []).append((pat, tids))
            total_patterns += 1

    multi_groups = {gk: pats for gk, pats in groups.items() if len(pats) > 1}
    single_groups = {gk: pats for gk, pats in groups.items() if len(pats) == 1}

    logger.info(
        f"Loaded {total_patterns} patterns in {len(groups)} groups "
        f"({len(multi_groups)} multi-pattern, {len(single_groups)} single-pattern)"
    )

    # --- Load source JSON and build field text index ---
    input_path = exit_if_missing(input_path, "Input JSON")
    model_class = MODEL_REGISTRY[model_name]

    with open(input_path, encoding='utf-8') as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"{error['type']}: {error['msg']}")
        raise SystemExit(1)

    # Collect all tinyIds referenced by coalesced patterns
    all_tinyids = set()
    for pats in groups.values():
        for _, tids in pats:
            all_tinyids.update(tids)

    logger.info(f"Building field text index for {len(all_tinyids)} tinyIds...")
    from actions.strip_discover.run import build_field_text_index
    field_index = build_field_text_index(parsed, field_paths, all_tinyids)
    logger.info(f"Indexed {len(field_index)} tinyIds across {len(field_paths)} fields")

    # Free parsed models (no longer needed, save memory before fork)
    del parsed, data

    # --- Validate groups ---
    # Single-pattern groups pass through directly
    results = []
    for gk, pats in single_groups.items():
        for pat, tids in pats:
            results.append((gk, pat, tids, "only_in_group"))

    if not multi_groups:
        logger.info("No multi-pattern groups to validate")
    elif n_workers <= 0 or len(multi_groups) < 4:
        # Sequential
        logger.info(f"Validating {len(multi_groups)} multi-pattern groups (sequential)...")
        for gk, pats in multi_groups.items():
            kept = _validate_group(gk, pats, field_index)
            results.extend(kept)
    else:
        # Parallel — greedy bin packing by tinyId count
        logger.info(
            f"Validating {len(multi_groups)} multi-pattern groups "
            f"({n_workers} workers)..."
        )

        group_loads = {}
        for gk, pats in multi_groups.items():
            group_loads[gk] = sum(len(tids) for _, tids in pats)

        sorted_groups = sorted(
            multi_groups.items(), key=lambda g: group_loads[g[0]], reverse=True
        )

        worker_loads = [0] * n_workers
        worker_chunks = [[] for _ in range(n_workers)]
        for gk, pats in sorted_groups:
            lightest = min(range(n_workers), key=lambda i: worker_loads[i])
            worker_chunks[lightest].append((gk, pats))
            worker_loads[lightest] += group_loads[gk]

        # Log load distribution
        for i, (chunk, load) in enumerate(zip(worker_chunks, worker_loads)):
            logger.debug(f"  Worker {i}: {len(chunk)} groups, ~{load} tinyId-checks")

        with ProcessPoolExecutor(
            max_workers=n_workers,
            initializer=_validate_worker_init,
            initargs=(field_index,),
        ) as executor:
            futures = {
                executor.submit(_validate_worker_process, chunk): i
                for i, chunk in enumerate(worker_chunks)
                if chunk  # skip empty chunks
            }
            for future in as_completed(futures):
                worker_results = future.result()
                results.extend(worker_results)

    # --- Write output ---
    # Sort by group_key, then longest pattern first within group
    results.sort(key=lambda r: (r[0], -len(r[1])))

    kept_count = len(results)
    dropped_count = total_patterns - kept_count

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("group_key\tpattern\ttinyIds\tvalidation\n")
        for gk, pat, tids, reason in results:
            tids_str = " ".join(sorted(tids))
            f.write(f"{gk}\t{pat}\t{tids_str}\t{reason}\n")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("EMPIRICAL SUBSUMPTION VALIDATION")
    print('=' * 60)
    print(f"\n  Input:    {coalesced_path}")
    print(f"  Groups:   {len(groups)} ({len(multi_groups)} multi-pattern)")
    print(f"  Input:    {total_patterns} patterns")
    print(f"  Kept:     {kept_count} patterns")
    print(f"  Dropped:  {dropped_count} patterns (redundant shorter forms)")
    print(f"  Output:   {output_path}")

    # Per-group drop details (only for groups that lost patterns)
    dropped_groups = []
    result_by_group = {}
    for gk, pat, tids, reason in results:
        result_by_group.setdefault(gk, []).append(pat)

    for gk, pats in multi_groups.items():
        input_pats = {p for p, _ in pats}
        output_pats = set(result_by_group.get(gk, []))
        dropped = input_pats - output_pats
        if dropped:
            dropped_groups.append((gk, dropped, output_pats))

    if dropped_groups:
        print(f"\n  Groups with drops ({len(dropped_groups)}):")
        for gk, dropped, kept_pats in sorted(dropped_groups, key=lambda x: -len(x[1])):
            print(f"    {gk}:")
            for d in sorted(dropped, key=len):
                print(f"      - dropped: {d[:70]}")
            for k in sorted(kept_pats, key=len):
                print(f"      + kept:    {k[:70]}")

    return 0


def _run_group_hierarchy(args, input_path: str) -> int:
    """
    Assign group/sub-group hierarchy labels to patterns.

    Reads a patterns TSV, groups by shared prefix, strips trailing delimiters
    to get clean group names, and writes enriched output with group/sub_group columns.
    """
    import re
    from utils.file_utils import exit_if_missing

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --group-hierarchy")
        raise SystemExit(1)

    exit_if_missing(input_path, "Patterns TSV")

    min_group_size = getattr(args, 'min_group_size', 2)
    min_prefix_words = getattr(args, 'min_prefix_words', 2)
    min_tinyids_base = getattr(args, 'min_tinyids', 0)
    min_tinyids_scale = getattr(args, 'min_tinyids_scale', 0.0)

    # Read TSV — preserve all columns
    rows = []  # list of (fields_list, pattern, tinyids_set)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            rows.append((fields, pattern, tinyids))

    logger.info(f"Loaded {len(rows)} patterns from {input_path}")

    # Compute adaptive min-tinyids threshold
    # effective_min = base + floor(scale * sqrt(corpus_size))
    # where corpus_size = total unique tinyIds across all patterns
    import math
    all_tinyids = set()
    for _, _, tids in rows:
        all_tinyids.update(tids)
    corpus_size = len(all_tinyids)

    min_tinyids = min_tinyids_base
    if min_tinyids_scale > 0:
        scaled_increment = int(math.floor(min_tinyids_scale * math.sqrt(corpus_size)))
        min_tinyids = min_tinyids_base + scaled_increment
        logger.info(
            f"Adaptive threshold: base={min_tinyids_base} + "
            f"floor({min_tinyids_scale} * sqrt({corpus_size})) = "
            f"{min_tinyids_base} + {scaled_increment} = {min_tinyids}"
        )

    # Filter by min tinyIds count
    filtered_count = 0
    if min_tinyids > 0:
        filtered_rows = []
        for fields_list, pattern, tinyids in rows:
            if pattern and len(tinyids) < min_tinyids:
                filtered_count += 1
            else:
                filtered_rows.append((fields_list, pattern, tinyids))
        rows = filtered_rows
        if filtered_count:
            logger.info(f"Filtered {filtered_count} patterns with < {min_tinyids} tinyIds")

    # Build pattern->tinyids map
    patterns_with_tinyids = {pat: tids for _, pat, tids in rows if pat}

    # Run hierarchy assignment
    from logic.group_hierarchy import build_group_hierarchy

    assignments, stats = build_group_hierarchy(
        patterns_with_tinyids,
        min_group_size=min_group_size,
        min_prefix_words=min_prefix_words,
    )

    # Build pattern -> assignment lookup
    pattern_to_assignment = {}
    for a in assignments:
        pattern_to_assignment[a.sub_group] = a

    # Strip existing hierarchy columns if re-running
    hierarchy_cols = {"group", "sub_group", "suffix", "group_size", "group_tinyid_count"}
    clean_header_indices = [i for i, h in enumerate(headers) if h not in hierarchy_cols]
    clean_headers = [headers[i] for i in clean_header_indices]

    # Output headers: hierarchy columns first, then original columns, then group stats
    out_headers = ["group", "sub_group", "suffix"] + clean_headers + ["group_size", "group_tinyid_count"]

    # Build output rows sorted by group then pattern
    output_rows = []
    for fields_list, pattern, tinyids in rows:
        if not pattern:
            continue
        clean_fields = [fields_list[i] if i < len(fields_list) else ""
                        for i in clean_header_indices]
        a = pattern_to_assignment.get(pattern)
        if a and a.group:
            output_rows.append((a.group, a.sub_group, a.suffix, clean_fields,
                                str(a.group_size), str(a.group_tinyid_count)))
        else:
            output_rows.append(("", pattern, "", clean_fields, "", ""))

    # Sort: grouped first (by group, then pattern), ungrouped last
    output_rows.sort(key=lambda r: (r[0] == "", r[0], r[1]))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(out_headers) + "\n")
        for group, sub_group, suffix, clean_fields, size, tid_count in output_rows:
            row = [group, sub_group, suffix] + clean_fields + [size, tid_count]
            f.write("\t".join(row) + "\n")

    # Summary
    print(f"\nGroup hierarchy complete:")
    total_input = stats['total_patterns'] + filtered_count
    print(f"  Input:     {total_input} patterns (corpus: {corpus_size} unique tinyIds)")
    if min_tinyids_scale > 0:
        print(f"  Threshold: {min_tinyids} (base={min_tinyids_base} + floor({min_tinyids_scale} * sqrt({corpus_size})))")
    if filtered_count:
        print(f"  Filtered:  {filtered_count} patterns (< {min_tinyids} tinyIds)")
    print(f"  Groups:    {stats['groups']} groups ({stats['grouped_patterns']} patterns)")
    print(f"  Ungrouped: {stats['ungrouped_patterns']} patterns")
    print(f"  Wrote:     {output_path}")

    if stats['groups'] > 0:
        group_summary = {}
        for a in assignments:
            if a.group:
                if a.group not in group_summary:
                    group_summary[a.group] = {'count': 0, 'tinyids': a.group_tinyid_count}
                group_summary[a.group]['count'] += 1

        print(f"\nGroups (by size):")
        for name, data in sorted(group_summary.items(), key=lambda x: -x[1]['count']):
            print(f"  '{name}' — {data['count']} sub-groups, {data['tinyids']} tinyIds")

    return 0


def _run_generate_strip_patterns(args, input_path: str) -> int:
    """
    Generate two strip-ready pattern files from a group-hierarchy TSV.

    Produces:
    - {output}_full.tsv: pattern + tinyIds (full removal)
    - {output}_sub.tsv: pattern + tinyIds + replace_with (suffix retained)
    """
    from utils.file_utils import exit_if_missing

    output_base = getattr(args, 'output', None)
    if not output_base:
        logger.error("--output is required for --generate-strip-patterns")
        raise SystemExit(1)

    exit_if_missing(input_path, "Group hierarchy TSV")

    # Strip .tsv extension from output base if present
    if output_base.endswith('.tsv'):
        output_base = output_base[:-4]

    full_path = f"{output_base}_full.tsv"
    sub_path = f"{output_base}_sub.tsv"

    # Read hierarchy TSV
    rows = []
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        # Optional hierarchy columns
        suffix_idx = None
        try:
            suffix_idx = find_column_index(headers, 'suffix')
        except ValueError:
            pass

        group_idx = None
        try:
            group_idx = find_column_index(headers, 'group')
        except ValueError:
            pass

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            suffix = fields[suffix_idx].strip().strip('"') if suffix_idx is not None and suffix_idx < len(fields) else ""
            group = fields[group_idx].strip().strip('"') if group_idx is not None and group_idx < len(fields) else ""

            if pattern:
                rows.append((pattern, tinyids, suffix, group))

    # Write full-removal file
    full_count = 0
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\n")
        for pattern, tinyids, suffix, group in rows:
            f.write(f"{pattern}\t{tinyids}\n")
            full_count += 1

    # Write sub-group file (suffix retained via replace_with column)
    sub_count = 0
    replace_count = 0
    with open(sub_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\treplace_with\n")
        for pattern, tinyids, suffix, group in rows:
            # Grouped patterns with a suffix: replace with suffix
            # Ungrouped or no suffix: full removal (empty replace_with)
            replace_with = suffix if (group and suffix) else ""
            f.write(f"{pattern}\t{tinyids}\t{replace_with}\n")
            sub_count += 1
            if replace_with:
                replace_count += 1

    print(f"\nGenerated strip pattern files:")
    print(f"  Full removal: {full_path} ({full_count} patterns)")
    print(f"  Sub-group:    {sub_path} ({sub_count} patterns, {replace_count} with suffix retained)")

    return 0


def _run_group_semantic(args, input_path: str) -> int:
    """
    Group patterns by shared prefix spans with SpaCy-based boundary trimming.

    Reads a patterns TSV, groups by longest common prefix, trims trailing
    function words using SpaCy POS tagging, and writes output with group
    annotations.
    """
    import re
    from utils.file_utils import exit_if_missing

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --group-semantic")
        raise SystemExit(1)

    exit_if_missing(input_path, "Patterns TSV")

    min_group_size = getattr(args, 'min_group_size', 2)
    min_prefix_words = getattr(args, 'min_prefix_words', 2)

    # Read TSV — preserve all columns
    rows = []  # list of (fields_list, pattern, tinyids_set)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            rows.append((fields, pattern, tinyids))

    logger.info(f"Loaded {len(rows)} patterns from {input_path}")

    # Build pattern->tinyids map
    patterns_with_tinyids = {pat: tids for _, pat, tids in rows if pat}

    # Load SpaCy
    import spacy
    nlp = spacy.load("en_core_web_sm")
    logger.info("Loaded SpaCy en_core_web_sm model")

    # Run semantic grouping
    from logic.span_boundary import (
        group_patterns_semantic, normalize_temporal_prefix,
        generate_temporal_no_quantifier, _extract_temporal_frame,
    )
    generate_implied = not getattr(args, 'no_temporal_implied', False)

    groups, ungrouped = group_patterns_semantic(
        patterns_with_tinyids, nlp,
        min_group_size=min_group_size,
        min_prefix_words=min_prefix_words
    )

    # Build pattern -> group info lookup
    pattern_to_group = {}
    for group in groups:
        for pat in group.patterns:
            pattern_to_group[pat] = group

    # Build normalized temporal super-group labels
    temporal_labels = {}
    for group in groups:
        if group.super_group == "temporal":
            temporal_labels[group.trimmed_prefix] = normalize_temporal_prefix(
                group.trimmed_prefix, group.patterns
            )

    # Generate implied-ONE temporal variants (default behavior)
    implied_rows = []  # (temporal_label, prefix, pattern, empty_clean_fields, size, tid_count)
    implied_count = 0
    if generate_implied:
        seen_implied = set()
        for group in groups:
            if group.super_group != "temporal":
                continue
            # Extract unique temporal frames from all patterns in the group
            frames_in_group = set()
            for pat in group.patterns:
                frame = _extract_temporal_frame(pat)
                if frame:
                    frames_in_group.add(frame)
            # Also check the prefix itself
            prefix_frame = _extract_temporal_frame(group.trimmed_prefix)
            if prefix_frame:
                frames_in_group.add(prefix_frame)

            for frame in frames_in_group:
                no_q = generate_temporal_no_quantifier(frame)
                if no_q and no_q not in seen_implied and no_q not in patterns_with_tinyids:
                    seen_implied.add(no_q)
                    implied_count += 1

        if implied_count:
            logger.info(f"Generated {implied_count} implied-ONE temporal variants")

    # Strip existing group columns if re-running
    group_col_names = {"group_prefix", "group_size", "group_tinyid_count", "temporal_group", "implied"}
    clean_header_indices = [i for i, h in enumerate(headers) if h not in group_col_names]
    clean_headers = [headers[i] for i in clean_header_indices]

    # Output headers: group columns first, then original columns
    out_headers = ["temporal_group", "group_prefix"] + clean_headers + ["group_size", "group_tinyid_count", "implied"]

    # Build output rows, sorted by group prefix then pattern
    output_rows = []
    for fields_list, pattern, tinyids in rows:
        if not pattern:
            continue
        clean_fields = [fields_list[i] if i < len(fields_list) else ""
                        for i in clean_header_indices]
        group = pattern_to_group.get(pattern)
        if group:
            prefix = group.trimmed_prefix
            size = str(len(group.patterns))
            tid_count = str(len(group.merged_tinyids))
            temporal = temporal_labels.get(prefix, "")
        else:
            prefix = ""
            size = ""
            tid_count = ""
            temporal = ""
        output_rows.append((temporal, prefix, pattern, clean_fields, size, tid_count, ""))

    # Add implied-ONE temporal rows
    if generate_implied and implied_count > 0:
        seen_implied = set()
        empty_clean = [""] * len(clean_headers)
        for group in groups:
            if group.super_group != "temporal":
                continue
            frames_in_group = set()
            for pat in group.patterns:
                frame = _extract_temporal_frame(pat)
                if frame:
                    frames_in_group.add(frame)
            prefix_frame = _extract_temporal_frame(group.trimmed_prefix)
            if prefix_frame:
                frames_in_group.add(prefix_frame)
            for frame in frames_in_group:
                no_q = generate_temporal_no_quantifier(frame)
                if no_q and no_q not in seen_implied and no_q not in patterns_with_tinyids:
                    seen_implied.add(no_q)
                    temporal = temporal_labels.get(group.trimmed_prefix, "")
                    # Put the no_q pattern in the pattern column
                    impl_fields = list(empty_clean)
                    try:
                        clean_pat_pos = clean_headers.index("pattern")
                        impl_fields[clean_pat_pos] = no_q
                    except ValueError:
                        pass
                    output_rows.append((
                        temporal, group.trimmed_prefix, no_q,
                        impl_fields, str(len(group.patterns)), str(len(group.merged_tinyids)),
                        "yes"
                    ))

    # Sort: temporal groups first (by temporal label, then prefix, then pattern),
    # then other groups, then ungrouped last
    output_rows.sort(key=lambda r: (
        r[0] == "" and r[1] == "",  # ungrouped last
        r[0] == "",                  # non-temporal after temporal
        r[0], r[1], r[2]            # then by label, prefix, pattern
    ))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(out_headers) + "\n")
        for temporal, prefix, _pat, clean_fields, size, tid_count, implied in output_rows:
            row = [temporal, prefix] + clean_fields + [size, tid_count, implied]
            f.write("\t".join(row) + "\n")

    # Summary
    grouped_count = sum(len(g.patterns) for g in groups)
    temporal_groups = [g for g in groups if g.super_group == "temporal"]
    temporal_pattern_count = sum(len(g.patterns) for g in temporal_groups)
    print(f"\nSemantic grouping complete:")
    print(f"  Input:     {len(rows)} patterns")
    print(f"  Groups:    {len(groups)} semantic groups ({grouped_count} patterns)")
    if temporal_groups:
        unique_labels = set(temporal_labels.values())
        print(f"  Temporal:  {len(temporal_groups)} sub-groups in {len(unique_labels)} "
              f"super-groups ({temporal_pattern_count} patterns)")
    print(f"  Ungrouped: {len(ungrouped)} patterns")
    if implied_count:
        print(f"  Implied:   {implied_count} no-quantifier temporal variants added")
    print(f"  Wrote:     {output_path}")

    if temporal_groups:
        print(f"\nTemporal super-groups:")
        by_label = {}
        for g in temporal_groups:
            label = temporal_labels[g.trimmed_prefix]
            by_label.setdefault(label, []).append(g)
        for label, label_groups in sorted(by_label.items()):
            sub_count = len(label_groups)
            pat_count = sum(len(g.patterns) for g in label_groups)
            print(f"  '{label}' — {sub_count} sub-groups, {pat_count} patterns")

    if groups:
        non_temporal = [g for g in groups if g.super_group != "temporal"]
        if non_temporal:
            print(f"\nTop non-temporal groups (by size):")
            for g in sorted(non_temporal, key=lambda g: len(g.patterns), reverse=True)[:10]:
                print(f"  '{g.trimmed_prefix}' — {len(g.patterns)} patterns, "
                      f"{len(g.merged_tinyids)} tinyIds")

    return 0


def _run_generate_proxies(args, input_path: str) -> int:
    """
    Generate semantic proxies for patterns using an LLM.

    Reads a patterns TSV, looks up sample CDE contexts from the source JSON,
    queries an LLM for a 1-3 word semantic proxy per pattern, and writes an
    enriched TSV with replace_with and proxy_reasoning columns.

    This is a wireframe for evaluating whether semantic substitution
    produces meaningful proxies before building a full pipeline.
    """
    import asyncio
    import json
    import re
    from pathlib import Path
    from utils.file_utils import exit_if_missing
    from utils.constants import MODEL_REGISTRY
    from pydantic import ValidationError

    output_path = getattr(args, 'output', None)
    input_json = getattr(args, 'input', None)
    if not output_path:
        logger.error("--output is required for --generate-proxies")
        raise SystemExit(1)
    if not input_json:
        logger.error("--input (CDE JSON) is required for --generate-proxies")
        raise SystemExit(1)

    exit_if_missing(input_path, "Patterns TSV")
    exit_if_missing(input_json, "Input JSON")

    provider_name = getattr(args, 'provider', 'claude')
    llm_model = getattr(args, 'llm_model', None)
    config_file = getattr(args, 'config_file', None)
    api_keys = getattr(args, 'api_keys', None)
    context_window = getattr(args, 'context_window', 150)
    max_contexts = getattr(args, 'max_contexts', 3)
    dry_run = getattr(args, 'dry_run', False)
    model_name = getattr(args, 'model', 'CDE')
    field_paths = getattr(args, 'fields',
                          ["definitions.*.definition", "designations.*.designation"])

    # --- Load patterns TSV ---
    rows = []  # (fields_list, pattern, tinyids_set)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            rows.append((fields, pattern, tinyids))

    logger.info(f"Loaded {len(rows)} patterns from {input_path}")

    # --- Load CDE JSON for context ---
    model_class = MODEL_REGISTRY[model_name]
    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records from {input_json}")

    # Build tinyId -> record lookup
    tid_to_record = {}
    for rec in parsed:
        if hasattr(rec, 'tinyId') and rec.tinyId:
            tid_to_record[rec.tinyId] = rec

    # --- Extract contexts per pattern ---
    from logic.verbatim_discoverer import _extract_at_path

    def _get_contexts(pattern: str, tinyids: set) -> str:
        """Find sample CDE texts containing this pattern."""
        contexts = []
        # Search in tinyId-restricted records first, fall back to all records
        search_records = [tid_to_record[t] for t in tinyids if t in tid_to_record] if tinyids else parsed
        for rec in search_records[:20]:  # limit search scope
            rec_dict = rec.model_dump(mode="json")
            for fp in field_paths:
                parts = fp.split('.')
                texts = _extract_at_path(rec_dict, parts)
                for text in texts:
                    idx = text.lower().find(pattern.lower())
                    if idx >= 0:
                        start = max(0, idx - context_window)
                        end = min(len(text), idx + len(pattern) + context_window)
                        snippet = text[start:end]
                        # Mark the pattern in context
                        field_label = fp.rsplit('.', 1)[-1]
                        contexts.append(f"  [{field_label}] ...{snippet}...")
                        if len(contexts) >= max_contexts:
                            break
                if len(contexts) >= max_contexts:
                    break
            if len(contexts) >= max_contexts:
                break
        return "\n".join(contexts) if contexts else "(no context found)"

    # --- Build query module and LLM provider ---
    from utils.query_modules import get_module
    module = get_module("semantic_proxy")
    system_prompt = module.build_system_prompt()
    user_template = module.build_user_prompt_template()

    if dry_run:
        # Show prompts for first 3 patterns without calling LLM
        print("\n=== DRY RUN: Showing prompts (no LLM calls) ===\n")
        print(f"System prompt ({len(system_prompt)} chars):")
        print(system_prompt[:500] + "...\n")
        for i, (fields_list, pattern, tinyids) in enumerate(rows[:3]):
            context_text = _get_contexts(pattern, tinyids)
            user_prompt = user_template.format(
                phrase_text=pattern,
                context_section=f"Sample CDE contexts:\n{context_text}",
            )
            print(f"--- Pattern {i+1}: '{pattern[:60]}' ---")
            print(user_prompt)
            print()
        print(f"(Showing 3 of {len(rows)} patterns)")
        return 0

    # --- Resolve LLM config and create provider ---
    from utils.llm import resolve_config, create_provider

    config_file_path = Path(config_file) if config_file else None
    llm_config = resolve_config(
        requested_providers=[provider_name],
        config_file_path=config_file_path,
        cli_api_keys=api_keys,
    )

    provider_config = llm_config.get_providers()[0]
    if llm_model:
        provider_config.model = llm_model

    provider = create_provider(provider_config)
    logger.info(f"Using {provider.provider_name} (model: {provider.model_id})")

    # --- Query LLM for each pattern ---
    from CDE_Schema.LLM_Classification import PhraseContext

    results = []  # list of (proxy, confidence, reasoning)

    async def _query_one(pattern: str, tinyids: set) -> tuple:
        context_text = _get_contexts(pattern, tinyids)
        phrase = PhraseContext(
            phrase_text=pattern,
            verbatim_forms=[pattern],
            field_contexts=[],
            frequency=len(tinyids),
            n_tinyids=len(tinyids),
        )

        responses = await provider.classify_batch(
            phrases=[phrase],
            system_prompt=system_prompt,
            user_prompt_template=user_template.replace(
                "{context_section}",
                f"Sample CDE contexts:\n{context_text}",
            ),
            categories=module.output_categories,
        )
        if responses:
            resp = responses[0]
            # The "category" field holds the raw LLM text for proxy modules
            proxy, confidence, reasoning = module.parse_response(
                resp.raw_response if hasattr(resp, 'raw_response') and resp.raw_response
                else f'{{"proxy": "{resp.category}", "confidence": {resp.confidence}, "reasoning": "{resp.reasoning}"}}'
            )
            return proxy, confidence, reasoning
        return "", 0.0, "No response from LLM"

    async def _run_all():
        for i, (fields_list, pattern, tinyids) in enumerate(rows):
            if not pattern:
                results.append(("", 0.0, ""))
                continue
            print(f"  [{i+1}/{len(rows)}] {pattern[:60]}...", end="", flush=True)
            try:
                proxy, confidence, reasoning = await _query_one(pattern, tinyids)
                results.append((proxy, confidence, reasoning))
                print(f" -> '{proxy}' ({confidence:.2f})")
            except Exception as e:
                logger.warning(f"LLM error for pattern '{pattern[:40]}': {e}")
                results.append(("", 0.0, f"ERROR: {e}"))
                print(f" -> ERROR: {e}")

    print(f"\nGenerating proxies for {len(rows)} patterns...")
    asyncio.run(_run_all())

    # --- Write output TSV ---
    # Remove existing replace_with/proxy_reasoning columns if re-running
    proxy_cols = {"replace_with", "proxy_reasoning", "proxy_confidence"}
    clean_header_indices = [i for i, h in enumerate(headers) if h not in proxy_cols]
    clean_headers = [headers[i] for i in clean_header_indices]
    out_headers = clean_headers + ["replace_with", "proxy_confidence", "proxy_reasoning"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(out_headers) + "\n")
        for idx, (fields_list, pattern, tinyids) in enumerate(rows):
            clean_fields = [fields_list[i] if i < len(fields_list) else ""
                            for i in clean_header_indices]
            proxy, confidence, reasoning = results[idx] if idx < len(results) else ("", 0.0, "")
            # Escape tabs in reasoning
            reasoning_clean = reasoning.replace('\t', ' ').replace('\n', ' ')
            row = clean_fields + [proxy, f"{confidence:.2f}", reasoning_clean]
            f.write("\t".join(row) + "\n")

    # Summary
    successful = sum(1 for p, c, r in results if p)
    high_conf = sum(1 for p, c, r in results if p and c >= 0.7)
    print(f"\nProxy generation complete:")
    print(f"  Input:      {len(rows)} patterns")
    print(f"  Proxied:    {successful} ({successful*100//max(len(rows),1)}%)")
    print(f"  High-conf:  {high_conf} (>= 0.7)")
    print(f"  Wrote:      {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Review {output_path} — edit replace_with column as needed")
    print(f"  2. Apply: cde-analyzer strip_phrases -i INPUT.json --patterns {output_path} --clean-remnants --diff -o OUTPUT.json")

    return 0


def _run_yaml_to_tsv(args, yaml_path: str) -> int:
    """
    Convert a supplementary_patterns.yaml to TSV for editing.

    Output TSV has columns: section, pattern, name, acronym.
    """
    import csv
    import yaml
    from utils.file_utils import exit_if_missing

    exit_if_missing(yaml_path, "YAML file")
    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --yaml-to-tsv")
        raise SystemExit(1)

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    rows = []
    for section_name, entries in config.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or 'pattern' not in entry:
                continue
            rows.append({
                'section': section_name,
                'pattern': entry.get('pattern', ''),
                'name': entry.get('name', ''),
                'acronym': entry.get('acronym', ''),
            })

    fieldnames = ['section', 'pattern', 'name', 'acronym']
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                                lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Converted {len(rows)} patterns from {yaml_path}")
    print(f"  Sections: {len(set(r['section'] for r in rows))}")
    print(f"  Output:   {output_path}")
    print(f"\nEdit with: cde-analyzer pattern_util --edit {output_path}")
    print(f"Convert back: cde-analyzer pattern_util --tsv-to-yaml {output_path} -o {yaml_path}")

    return 0


def _run_tsv_to_yaml(args, tsv_path: str) -> int:
    """
    Convert an edited TSV back to supplementary_patterns.yaml format.

    TSV must have columns: section, pattern, name (acronym optional).
    Rows are grouped by section value.
    """
    import csv
    import yaml
    from collections import OrderedDict
    from utils.file_utils import exit_if_missing

    exit_if_missing(tsv_path, "TSV file")
    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --tsv-to-yaml")
        raise SystemExit(1)

    # Read TSV
    sections = OrderedDict()
    total = 0
    with open(tsv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            section = row.get('section', '').strip()
            pattern = row.get('pattern', '').strip()
            name = row.get('name', '').strip()
            acronym = row.get('acronym', '').strip()

            if not section or not pattern:
                continue

            entry = {'pattern': pattern, 'name': name or pattern}
            if acronym:
                entry['acronym'] = acronym

            if section not in sections:
                sections[section] = []
            sections[section].append(entry)
            total += 1

    # Write YAML preserving section order
    with open(output_path, 'w', encoding='utf-8') as f:
        for section_name, entries in sections.items():
            f.write(f"{section_name}:\n")
            for entry in entries:
                f.write(f'  - pattern: "{entry["pattern"]}"\n')
                f.write(f'    name: "{entry["name"]}"\n')
                if 'acronym' in entry:
                    f.write(f'    acronym: "{entry["acronym"]}"\n')
                f.write('\n')

    print(f"Converted {total} patterns from {tsv_path}")
    print(f"  Sections: {len(sections)}")
    print(f"  Output:   {output_path}")

    return 0


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

    # Locate the HTML file co-located with this module
    html_path = Path(__file__).parent / "tsv_editor.html"
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


def _run_expand_verbatim(args, expand_verbatim_path: str) -> int:
    """
    Expand curated patterns with temporal preposition, case, number, and plural variants.

    Generates a narrow set of verbatim variants from curated patterns
    so the strip engine can use exact matching without runtime magic.
    """
    import re
    from utils.file_utils import exit_if_missing
    from utils.pattern_tsv_utils import load_pattern_list_with_tinyids
    from utils.pattern_variant_generator import (
        generate_case_variants, generate_number_variants,
        generate_plural_variants, generate_temporal_preposition_variants
    )

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --expand-verbatim")
        raise SystemExit(1)

    exit_if_missing(expand_verbatim_path, "Curated patterns TSV")

    do_temporal = getattr(args, 'temporal_variants', True)
    do_case = getattr(args, 'case_variants', True)
    do_number = getattr(args, 'number_variants', True)
    do_plural = getattr(args, 'plural_variants', True)
    do_rescan = getattr(args, 'rescan', False)

    # Load curated patterns with tinyIds
    patterns, pattern_to_tinyids = load_pattern_list_with_tinyids(expand_verbatim_path)
    logger.info(f"Loaded {len(patterns)} curated patterns from {expand_verbatim_path}")

    # Generate variants for each pattern
    # Track: variant -> (source_pattern, tinyids)
    # Use list to preserve ordering, dict for dedup/merge
    variant_to_sources = {}  # variant -> set of source patterns
    variant_to_tinyids = {}  # variant -> set of tinyIds

    stats = {'temporal': 0, 'case': 0, 'number': 0, 'plural': 0}

    for source_pattern in patterns:
        source_tinyids = pattern_to_tinyids.get(source_pattern, set())

        # Build variant set incrementally
        variants = {source_pattern}

        # Stage 1: Temporal preposition variants (FIRST — so downstream
        # stages apply to all preposition/tense combinations)
        if do_temporal:
            temporal_expanded = set()
            for v in variants:
                temporal_expanded.update(generate_temporal_preposition_variants(v))
            stats['temporal'] += len(temporal_expanded) - len(variants)
            variants = temporal_expanded

        if do_plural:
            plural_expanded = set()
            for v in variants:
                plural_expanded.update(generate_plural_variants(v))
            stats['plural'] += len(plural_expanded) - len(variants)
            variants = plural_expanded

        if do_number:
            number_expanded = set()
            for v in variants:
                number_expanded.update(generate_number_variants(v))
            stats['number'] += len(number_expanded) - len(variants)
            variants = number_expanded

        if do_case:
            case_expanded = set()
            for v in variants:
                case_expanded.update(generate_case_variants(v))
            stats['case'] += len(case_expanded) - len(variants)
            variants = case_expanded

        # Register each variant
        for variant in variants:
            if variant not in variant_to_sources:
                variant_to_sources[variant] = set()
                variant_to_tinyids[variant] = set()
            variant_to_sources[variant].add(source_pattern)
            variant_to_tinyids[variant].update(source_tinyids)

    logger.info(
        f"Expanded {len(patterns)} patterns → {len(variant_to_sources)} variants "
        f"(temporal: +{stats['temporal']}, plural: +{stats['plural']}, "
        f"number: +{stats['number']}, case: +{stats['case']})"
    )

    # Optional re-scan: search source JSON for actual tinyIds per variant
    if do_rescan:
        input_json = getattr(args, 'input', None)
        if not input_json:
            logger.error("--input (CDE JSON) is required with --rescan")
            raise SystemExit(1)

        import json
        from pydantic import ValidationError
        from utils.constants import MODEL_REGISTRY
        from logic.verbatim_discoverer import _extract_at_path

        exit_if_missing(input_json, "Input JSON")

        model_name = getattr(args, 'model', 'CDE')
        field_paths = getattr(args, 'fields',
                              ["definitions.*.definition", "designations.*.designation"])
        model_class = MODEL_REGISTRY[model_name]

        with open(input_json, encoding="utf-8") as f:
            data = json.load(f)

        try:
            parsed = [model_class.model_validate(obj) for obj in data]
        except ValidationError as e:
            for error in e.errors():
                logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
            raise SystemExit(1)

        logger.info(f"Re-scanning {len(parsed)} records for tinyIds...")

        # Build text index: tinyId -> [texts across all fields]
        tid_texts = {}
        for item in parsed:
            item_dict = item.model_dump(mode="json")
            tid = item_dict.get("tinyId", "")
            if not tid:
                continue
            texts = []
            for fp in field_paths:
                parts = fp.split(".")
                texts.extend(_extract_at_path(item_dict, parts))
            if texts:
                tid_texts[tid] = texts

        # Search each variant in all texts
        rescan_hits = 0
        rescan_tinyids_total = 0
        for variant in variant_to_sources:
            discovered_tids = set()
            for tid, texts in tid_texts.items():
                for text in texts:
                    if variant in text:
                        discovered_tids.add(tid)
                        break
            if discovered_tids:
                rescan_hits += 1
                rescan_tinyids_total += len(discovered_tids)
            # Replace inherited tinyIds with discovered ones
            variant_to_tinyids[variant] = discovered_tids

        logger.info(
            f"Re-scan complete: {rescan_hits}/{len(variant_to_sources)} variants matched, "
            f"{rescan_tinyids_total} total tinyId hits"
        )

    # Filter out variants with no tinyIds when rescan is active
    # Empty tinyIds in strip_phrases means "apply to all records" — so unmatched
    # rescan variants would cause over-stripping
    if do_rescan:
        empty_variants = [v for v in variant_to_sources if not variant_to_tinyids[v]]
        if empty_variants:
            logger.info(
                f"Dropping {len(empty_variants)} variants with no rescan matches "
                f"(would over-strip as unrestricted)"
            )
            for v in empty_variants:
                del variant_to_sources[v]
                del variant_to_tinyids[v]

    # Write output TSV
    # Sort: by source pattern (grouped), then longest variant first
    ordered_variants = sorted(
        variant_to_sources.keys(),
        key=lambda v: (
            min(variant_to_sources[v]),  # group by source pattern
            -len(v),                     # longest first within group
            v                            # alpha tiebreaker
        )
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\tsource_pattern\ttinyIds\n")
        for variant in ordered_variants:
            sources = sorted(variant_to_sources[variant])
            source_str = sources[0]  # primary source (shortest if multiple)
            tinyids = variant_to_tinyids[variant]
            tinyids_str = " ".join(sorted(tinyids)) if tinyids else ""
            f.write(f"{variant}\t{source_str}\t{tinyids_str}\n")

    n_with_tinyids = sum(1 for v in ordered_variants if variant_to_tinyids[v])
    n_empty = len(ordered_variants) - n_with_tinyids

    print(f"Input:    {len(patterns)} curated patterns")
    print(f"Expanded: {len(ordered_variants)} variants")
    if do_rescan and empty_variants:
        print(f"  Dropped: {len(empty_variants)} unmatched variants")
    print(f"  Temporal: +{stats['temporal']}")
    print(f"  Plural:   +{stats['plural']}")
    print(f"  Number:   +{stats['number']}")
    print(f"  Case:     +{stats['case']}")
    if do_rescan:
        print(f"Re-scan:  {rescan_hits} variants matched in source JSON")
    print(f"TinyIds:  {n_with_tinyids} with, {n_empty} without")
    print(f"Wrote:    {output_path}")

    return 0


def _run_expand_temporal_seeds(args) -> int:
    """Expand temporal seed patterns from config YAML into a strip-ready TSV.

    Loads seeds from config/temporal_seed_patterns.yaml (global) and
    ./temporal_seed_patterns.yaml (local override), then generates all
    preposition/tense/case/number/plural variants.
    """
    import yaml
    from pathlib import Path
    from utils.pattern_variant_generator import (
        generate_case_variants, generate_number_variants,
        generate_plural_variants, generate_temporal_preposition_variants
    )

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --expand-temporal-seeds")
        raise SystemExit(1)

    # Locate config directory (where this package's config/ lives)
    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    global_path = config_dir / "temporal_seed_patterns.yaml"
    local_path = Path.cwd() / "temporal_seed_patterns.yaml"

    seeds = []
    for config_path in [global_path, local_path]:
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config and 'seeds' in config:
                n_before = len(seeds)
                for item in config['seeds']:
                    pattern = item.get('pattern', '').strip()
                    if pattern and pattern not in seeds:
                        seeds.append(pattern)
                logger.info(f"Loaded {len(seeds) - n_before} seeds from {config_path}")

    if not seeds:
        logger.error("No temporal seed patterns found in config")
        raise SystemExit(1)

    logger.info(f"Total seed patterns: {len(seeds)}")

    # 4-stage expansion (same order as _run_expand_verbatim)
    stats = {'temporal': 0, 'plural': 0, 'number': 0, 'case': 0}
    all_variants = set()

    for seed in seeds:
        variants = {seed}

        # Stage 1: Temporal preposition variants
        temporal_expanded = set()
        for v in variants:
            temporal_expanded.update(generate_temporal_preposition_variants(v))
        stats['temporal'] += len(temporal_expanded) - len(variants)
        variants = temporal_expanded

        # Stage 2: Plural variants
        plural_expanded = set()
        for v in variants:
            plural_expanded.update(generate_plural_variants(v))
        stats['plural'] += len(plural_expanded) - len(variants)
        variants = plural_expanded

        # Stage 3: Number variants
        number_expanded = set()
        for v in variants:
            number_expanded.update(generate_number_variants(v))
        stats['number'] += len(number_expanded) - len(variants)
        variants = number_expanded

        # Stage 4: Case variants
        case_expanded = set()
        for v in variants:
            case_expanded.update(generate_case_variants(v))
        stats['case'] += len(case_expanded) - len(variants)
        variants = case_expanded

        all_variants.update(variants)

    # Write output TSV (longest first)
    ordered = sorted(all_variants, key=lambda v: (-len(v), v))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\n")
        for variant in ordered:
            f.write(f"{variant}\t\n")  # Empty tinyIds = apply to all records

    logger.info(
        f"Expanded {len(seeds)} seeds -> {len(ordered)} temporal variants "
        f"(temporal: +{stats['temporal']}, plural: +{stats['plural']}, "
        f"number: +{stats['number']}, case: +{stats['case']})"
    )
    print(f"Seeds:    {len(seeds)}")
    print(f"Variants: {len(ordered)}")
    print(f"  Temporal: +{stats['temporal']}")
    print(f"  Plural:   +{stats['plural']}")
    print(f"  Number:   +{stats['number']}")
    print(f"  Case:     +{stats['case']}")
    print(f"Wrote:    {output_path}")

    return 0


def _run_detect_rare_words(args) -> int:
    """
    Detect rare words in CDE fields and write a curation TSV.

    Scans all CDE field texts for single words that appear across many CDEs
    but are rare in general English (low Zipf frequency).  ALL-CAPS words
    receive a configurable penalty to catch acronyms that spell common words.
    """
    import json
    from pydantic import ValidationError
    from utils.constants import MODEL_REGISTRY
    from utils.file_utils import exit_if_missing
    from logic.rare_word_detector import detect_rare_words, RareWordConfig

    # Validate required args
    input_json = getattr(args, 'input', None)
    output_path = getattr(args, 'output', None)
    if not input_json:
        logger.error("--input (CDE JSON) is required for --detect-rare-words")
        raise SystemExit(1)
    if not output_path:
        logger.error("--output is required for --detect-rare-words")
        raise SystemExit(1)

    exit_if_missing(input_json, "Input JSON")

    model_name = getattr(args, 'model', 'CDE')
    field_paths = getattr(args, 'fields',
                          ["definitions.*.definition", "designations.*.designation"])
    zipf_threshold = getattr(args, 'zipf_threshold', 1.5)
    caps_penalty = getattr(args, 'caps_penalty', 2.5)
    min_tinyids = getattr(args, 'min_tinyids', 0) or 3  # 0 = group-hierarchy sentinel → use 3
    exclude_path = getattr(args, 'exclude_patterns', None)

    # Load exclusion patterns (words already in instrument/phrase patterns)
    exclude_set = set()
    if exclude_path:
        exit_if_missing(exclude_path, "Exclusion patterns file")
        exclude_set = _load_exclusion_set(exclude_path)
        logger.info(f"Loaded {len(exclude_set)} exclusion patterns")

    # Load rare-word whitelist (legitimate domain terms to skip)
    no_whitelist = getattr(args, 'no_whitelist', False)
    whitelist_path = getattr(args, 'rare_word_whitelist', None)
    whitelist_words = set()
    if not no_whitelist:
        whitelist_words = _load_rare_word_whitelist(whitelist_path)
        if whitelist_words:
            exclude_set.update(whitelist_words)
            logger.info(f"Whitelist: {len(whitelist_words)} words excluded")

    # Load and parse CDE JSON
    model_class = MODEL_REGISTRY[model_name]
    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records from {input_json}")

    # Build config
    config = RareWordConfig(
        zipf_threshold=zipf_threshold,
        caps_penalty=caps_penalty,
        min_tinyids=min_tinyids,
        field_names=field_paths,
        exclude_patterns=exclude_set,
    )

    # Run detection
    results = detect_rare_words(parsed, config)

    # Write curation TSV
    with open(output_path, 'w', encoding='utf-8') as f:
        headers = [
            'word', 'cde_count', 'raw_zipf', 'effective_zipf',
            'is_allcaps', 'field_profile', 'tinyIds', 'example_context',
            'curate_action',
        ]
        f.write('\t'.join(headers) + '\n')

        for rw in results:
            tinyids_str = '|'.join(sorted(rw.tinyids))
            # Join example contexts with " /// " separator
            examples_str = ' /// '.join(rw.example_contexts)
            row = [
                rw.word,
                str(rw.cde_count),
                f"{rw.raw_zipf:.2f}",
                f"{rw.effective_zipf:.2f}",
                str(rw.is_allcaps),
                rw.field_profile,
                tinyids_str,
                examples_str,
                '',  # curate_action — for curator to fill in
            ]
            f.write('\t'.join(row) + '\n')

    whitelist_count = len(whitelist_words) if not no_whitelist and whitelist_words else 0
    print(f"Rare word detection complete:")
    print(f"  CDEs scanned:    {len(parsed)}")
    print(f"  Zipf threshold:  {zipf_threshold}")
    print(f"  Caps penalty:    {caps_penalty}")
    print(f"  Min tinyIds:     {min_tinyids}")
    if whitelist_count:
        print(f"  Whitelisted:     {whitelist_count}")
    print(f"  Words detected:  {len(results)}")
    if results:
        print(f"  Top 10:")
        for rw in results[:10]:
            caps_tag = " [CAPS]" if rw.is_allcaps else ""
            print(f"    {rw.word:<25s}  cde={rw.cde_count:>5d}  "
                  f"zipf={rw.raw_zipf:.1f}→{rw.effective_zipf:.1f}{caps_tag}")
    print(f"  Wrote: {output_path}")

    return 0


# ──────────────────────────────────────────────────────────────
# Priority split (Zipf-based curation triage)
# ──────────────────────────────────────────────────────────────

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
                row['decision'] = 'remove'
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
        print(f"  Low-priority patterns pre-filled with decision='remove'")
    print(f"\n  Zipf threshold: {threshold} (words with Zipf >= {threshold} are 'common')")
    print(f"  Zipf reference: 3=uncommon, 4=common (~top 6K words), 5=very common")

    return 0


def _run_recover_parent_filtered(args, report_path: str) -> int:
    """Analyze parent-filtered patterns from coalesce report for prefix recovery.

    Groups parent-filtered entries by word-level prefix and reports candidates
    with high divergence between actual tinyId count and parent_tinyid_count.

    This is a diagnostic placeholder. When --defer-parent-filter is used in the
    coalesce step, this diagnostic is rarely needed. It exists as a hook for
    future post-hoc recovery workflows.

    TODO: Add --apply-recovery mode that emits a recovery TSV for merging
    back into the coalesced output.
    """
    import re
    from collections import defaultdict

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --recover-parent-filtered")
        raise SystemExit(1)

    # Read parent-filtered entries from coalesce report
    # Parent-filtered rows have extra columns beyond the standard 5-column header:
    # type | original_pattern | tinyIds | parent_phrase | parent_count | actual_count
    filtered_entries = []
    with open(report_path, 'r', encoding='utf-8') as f:
        f.readline()  # skip header
        for line in f:
            fields = line.rstrip('\n\r').split('\t')
            if not fields or fields[0] != 'parent-filtered':
                continue
            pattern = fields[1] if len(fields) > 1 else ''
            tinyids_str = fields[2] if len(fields) > 2 else ''
            parent_count = int(fields[4]) if len(fields) > 4 and fields[4].isdigit() else 0
            actual_count = int(fields[5]) if len(fields) > 5 and fields[5].isdigit() else 0

            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            filtered_entries.append({
                'pattern': pattern,
                'tinyids': tinyids,
                'parent_count': parent_count,
                'actual_count': actual_count or len(tinyids),
            })

    if not filtered_entries:
        print(f"No parent-filtered entries found in {report_path}")
        return 0

    # Group by word-level prefixes (2+ words)
    prefix_groups: dict[str, list] = defaultdict(list)
    for entry in filtered_entries:
        words = entry['pattern'].split()
        # Generate all prefixes of length 2 to len-1
        for plen in range(2, len(words)):
            prefix = ' '.join(words[:plen])
            prefix_groups[prefix].append(entry)

    # Compute aggregate stats per prefix group
    results = []
    for prefix, members in prefix_groups.items():
        union_tinyids: set = set()
        for m in members:
            union_tinyids.update(m['tinyids'])
        max_parent = max(m['parent_count'] for m in members) or 1
        divergence = len(union_tinyids) / max_parent

        results.append({
            'prefix': prefix,
            'aggregate_tinyids': len(union_tinyids),
            'member_count': len(members),
            'max_parent_count': max_parent,
            'divergence_ratio': divergence,
            'example': members[0]['pattern'][:80],
        })

    # Sort by divergence descending
    results.sort(key=lambda x: -x['divergence_ratio'])

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("prefix\taggregate_tinyids\tmember_count\tmax_parent_count\t"
                "divergence_ratio\texample_pattern\n")
        for r in results:
            f.write(f"{r['prefix']}\t{r['aggregate_tinyids']}\t{r['member_count']}\t"
                    f"{r['max_parent_count']}\t{r['divergence_ratio']:.1f}\t"
                    f"{r['example']}\n")

    print(f"\nParent-filtered recovery analysis:")
    print(f"  Filtered entries: {len(filtered_entries)}")
    print(f"  Prefix groups:    {len(results)}")
    if results:
        print(f"\n  Top recovery candidates (by divergence ratio):")
        for r in results[:10]:
            print(f"    {r['prefix'][:50]:50s}  "
                  f"tinyIds={r['aggregate_tinyids']:>4d}  "
                  f"members={r['member_count']:>3d}  "
                  f"ratio={r['divergence_ratio']:.1f}x")
    print(f"\n  Output: {output_path}")

    return 0


def _run_remnant_analysis(args, patterns_path: str) -> int:
    """Simulate stripping and identify frequent context around pattern matches.

    For each pattern, finds occurrences in CDE texts and extracts surrounding
    context words.  Reports frequent extensions that suggest missing longer
    patterns (e.g. "The free-text field" almost always followed by "related to").
    """
    import csv
    import json
    import re
    from pathlib import Path

    patterns_file = Path(patterns_path)
    if not patterns_file.exists():
        logger.error(f"Patterns file not found: {patterns_file}")
        return 1

    input_json = getattr(args, 'input', None)
    if not input_json:
        logger.error("--input (CDE JSON) is required for --remnant-analysis")
        return 1

    output_path = getattr(args, 'output', None)
    if not output_path:
        logger.error("--output is required for --remnant-analysis")
        return 1

    context_words = getattr(args, 'context_words', 3)
    min_context_freq = getattr(args, 'min_context_freq', 5)

    # Load CDE JSON and build field text index: {tinyId: [(field_path, text)]}
    logger.info(f"Loading CDE JSON from {input_json}")
    with open(input_json, encoding='utf-8') as f:
        cdes = json.load(f)

    field_index: dict = {}  # tinyId -> list of (field_path, text)
    for cde in cdes:
        tid = cde.get('tinyId', '')
        texts = []
        for d in cde.get('definitions', []):
            txt = (d.get('definition', '') or '').strip()
            if txt:
                texts.append(('definition', txt))
        for d in cde.get('designations', []):
            txt = (d.get('designation', '') or '').strip()
            if txt:
                texts.append(('designation', txt))
        if texts:
            field_index[tid] = texts

    logger.info(f"Built field index: {len(field_index)} CDEs")

    # Load patterns TSV
    from utils.pattern_tsv_utils import find_column_index

    with open(patterns_file, encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)
        pat_col = find_column_index(header, 'pattern')
        try:
            tid_col = find_column_index(header, 'tinyIds')
        except ValueError:
            tid_col = None

        patterns = []
        for row in reader:
            if len(row) <= pat_col:
                continue
            pattern = row[pat_col]
            tinyids = None
            if tid_col is not None and len(row) > tid_col and row[tid_col].strip():
                tinyids = set(row[tid_col].split())
            patterns.append((pattern, tinyids))

    logger.info(f"Loaded {len(patterns)} patterns")

    # Word boundary regex for splitting context
    _WORD_RE = re.compile(r'\S+')

    # Analyze context around each pattern match
    # Key: (pattern, side, extension_text) -> {count, example_tid, example_text}
    extensions: dict = {}
    pattern_match_counts: dict = {}  # pattern -> total match count

    for pattern, tinyids in patterns:
        pattern_lower = pattern.lower()
        pat_len = len(pattern)
        total_matches = 0

        # Determine which tinyIds to scan
        scan_tids = tinyids if tinyids else set(field_index.keys())

        for tid in scan_tids:
            texts = field_index.get(tid)
            if not texts:
                continue
            for _field_path, text in texts:
                text_lower = text.lower()
                start_pos = 0
                while True:
                    idx = text_lower.find(pattern_lower, start_pos)
                    if idx == -1:
                        break
                    total_matches += 1
                    match_end = idx + pat_len

                    # Extract right context words
                    right_text = text[match_end:]
                    right_words = _WORD_RE.findall(right_text)
                    for width in range(1, min(context_words, len(right_words)) + 1):
                        ext = ' '.join(right_words[:width])
                        key = (pattern, 'right', ext)
                        if key not in extensions:
                            # Build snippet for example
                            snip_start = max(0, idx - 20)
                            snip_end = min(len(text), match_end + 40)
                            snippet = text[snip_start:snip_end]
                            extensions[key] = {
                                'count': 0,
                                'example_tid': tid,
                                'example_text': snippet,
                            }
                        extensions[key]['count'] += 1

                    # Extract left context words
                    left_text = text[:idx]
                    left_words = _WORD_RE.findall(left_text)
                    for width in range(1, min(context_words, len(left_words)) + 1):
                        ext = ' '.join(left_words[-width:])
                        key = (pattern, 'left', ext)
                        if key not in extensions:
                            snip_start = max(0, idx - 40)
                            snip_end = min(len(text), match_end + 20)
                            snippet = text[snip_start:snip_end]
                            extensions[key] = {
                                'count': 0,
                                'example_tid': tid,
                                'example_text': snippet,
                            }
                        extensions[key]['count'] += 1

                    start_pos = idx + 1

        pattern_match_counts[pattern] = total_matches

    # Filter by min_context_freq and build output rows
    rows = []
    for (pattern, side, ext_text), data in extensions.items():
        freq = data['count']
        if freq < min_context_freq:
            continue
        total = pattern_match_counts.get(pattern, 1)
        pct = freq / total * 100 if total > 0 else 0
        if side == 'right':
            combined = f"{pattern} {ext_text}"
        else:
            combined = f"{ext_text} {pattern}"
        rows.append({
            'pattern': pattern,
            'side': side,
            'extension': ext_text,
            'combined': combined,
            'freq': freq,
            'pct_of_matches': f"{pct:.1f}",
            'example_tinyId': data['example_tid'],
            'example_snippet': data['example_text'].replace('\t', ' ')[:120],
        })

    # Sort by frequency descending
    rows.sort(key=lambda r: (-r['freq'], r['pattern'], r['side']))

    # Write output
    out_fields = [
        'pattern', 'side', 'extension', 'combined',
        'freq', 'pct_of_matches', 'example_tinyId', 'example_snippet',
    ]
    out_path = Path(output_path)
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, delimiter='\t',
                                quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nRemnant analysis (context_words={context_words}, "
          f"min_freq={min_context_freq}):")
    print(f"  Patterns:   {len(patterns):>6,d}")
    print(f"  Extensions: {len(rows):>6,d}  (freq >= {min_context_freq})")
    print(f"  Output:     {out_path}")

    # Show top 10 right extensions as preview
    right_rows = [r for r in rows if r['side'] == 'right']
    if right_rows:
        print(f"\n  Top right extensions:")
        for r in right_rows[:10]:
            print(f"    {r['freq']:>5d} ({r['pct_of_matches']:>5s}%)  "
                  f"{r['combined'][:80]}")

    return 0


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for pattern_util action."""

    # Check for interactive editor mode (early — interactive, long-running)
    edit_path = getattr(args, 'edit', None)
    if edit_path is not None:
        return _run_edit(args, edit_path)

    # YAML ↔ TSV conversion for supplementary patterns
    yaml_to_tsv = getattr(args, 'yaml_to_tsv', None)
    if yaml_to_tsv:
        return _run_yaml_to_tsv(args, yaml_to_tsv)

    tsv_to_yaml = getattr(args, 'tsv_to_yaml', None)
    if tsv_to_yaml:
        return _run_tsv_to_yaml(args, tsv_to_yaml)

    # Check for to-minimal mode first (simple normalization)
    to_minimal = getattr(args, 'to_minimal', None)
    if to_minimal:
        return _run_to_minimal(args, to_minimal)

    # Check for generate-proxies mode (requires LLM)
    generate_proxies = getattr(args, 'generate_proxies', None)
    if generate_proxies:
        return _run_generate_proxies(args, generate_proxies)

    # Check for add-to-supplementary mode first (standalone)
    add_to_supplementary = getattr(args, 'add_to_supplementary', None)
    if add_to_supplementary:
        section_name = getattr(args, 'supplementary_section', 'added_patterns')
        count = add_patterns_to_supplementary(
            add_to_supplementary,
            section_name=section_name,
            delete_after=True
        )
        print(f"Added {count} patterns to supplementary_patterns.yaml ({section_name} section)")
        if count > 0:
            print("Input file deleted. Re-run phrase_miner with --extract-supplementary to pick up new patterns.")
        return 0

    # Check for harvest-to-supplementary mode
    harvest_to_supp = getattr(args, 'harvest_to_supplementary', None)
    if harvest_to_supp:
        return _run_harvest_to_supplementary(args, harvest_to_supp)

    # Check for promote-supplementary mode
    promote_supp = getattr(args, 'promote_supplementary', False)
    if promote_supp:
        return _run_promote_supplementary(args)

    # Check for init-curation mode
    init_curation = getattr(args, 'init_curation', None)
    if init_curation:
        return _run_init_curation(args, init_curation)

    # Check for merge-curation mode
    merge_curation = getattr(args, 'merge_curation', None)
    if merge_curation:
        return _run_merge_curation(args, merge_curation)

    # Check for serve-curation mode (centralized server)
    serve_curation_cfg = getattr(args, 'serve_curation', None)
    if serve_curation_cfg:
        return _run_serve_curation(args, serve_curation_cfg)

    # Check for curation-status mode
    curation_status_dir = getattr(args, 'curation_status', None)
    if curation_status_dir:
        return _run_curation_status(args, curation_status_dir)

    # Check for curation-gate mode (incremental curation)
    curation_gate = getattr(args, 'curation_gate', None)
    if curation_gate:
        return _run_curation_gate(args, curation_gate)

    # Check for finalize-curation mode (incremental curation)
    finalize_curation = getattr(args, 'finalize_curation', None)
    if finalize_curation:
        return _run_finalize_curation(args, finalize_curation)

    # Check for generate-strip-patterns mode
    gen_strip = getattr(args, 'generate_strip_patterns', None)
    if gen_strip:
        return _run_generate_strip_patterns(args, gen_strip)

    # Check for group-hierarchy mode
    group_hierarchy = getattr(args, 'group_hierarchy', None)
    if group_hierarchy:
        return _run_group_hierarchy(args, group_hierarchy)

    # Check for group-semantic mode
    group_semantic = getattr(args, 'group_semantic', None)
    if group_semantic:
        return _run_group_semantic(args, group_semantic)

    # Check for expand-verbatim mode
    expand_verbatim = getattr(args, 'expand_verbatim', None)
    if expand_verbatim:
        return _run_expand_verbatim(args, expand_verbatim)

    # Check for expand-temporal-seeds mode
    expand_temporal = getattr(args, 'expand_temporal_seeds', False)
    if expand_temporal:
        return _run_expand_temporal_seeds(args)

    # Check for field-analysis mode
    field_analysis = getattr(args, 'field_analysis', None)
    if field_analysis:
        return _run_field_analysis(args, field_analysis)

    # Check for harvest-residuals mode
    harvest_residuals = getattr(args, 'harvest_residuals', None)
    if harvest_residuals:
        return _run_harvest_residuals(args, harvest_residuals)

    # Check for update-ledger mode
    update_ledger = getattr(args, 'update_ledger', None)
    if update_ledger:
        return _run_update_ledger(args, update_ledger)

    # Check for validate-subsumption mode
    validate_sub = getattr(args, 'validate_subsumption', None)
    if validate_sub:
        return _run_validate_subsumption(args, validate_sub)

    # Check for rare-word detection mode
    detect_rare = getattr(args, 'detect_rare_words', False)
    if detect_rare:
        return _run_detect_rare_words(args)

    # Check for priority split mode (Zipf-based curation triage)
    split_priority = getattr(args, 'split_priority', None)
    if split_priority:
        return _run_split_priority(args, split_priority)

    # Check for remnant analysis mode (pre-strip diagnostic)
    remnant_analysis = getattr(args, 'remnant_analysis', None)
    if remnant_analysis:
        return _run_remnant_analysis(args, remnant_analysis)

    recover_parent_filtered = getattr(args, 'recover_parent_filtered', None)
    if recover_parent_filtered:
        return _run_recover_parent_filtered(args, recover_parent_filtered)

    # Check for merge mode (supports multiple files)
    merge_patterns = getattr(args, 'merge_patterns', None)
    if merge_patterns:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --merge-patterns")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import merge_verbatim_tsv
        import tempfile

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')

        # If multiple files, normalize columns and concatenate into a temp file
        if isinstance(merge_patterns, list) and len(merge_patterns) > 1:
            logger.info(f"Multi-file merge: concatenating {len(merge_patterns)} files")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False, encoding='utf-8') as tmp:
                tmp_path = tmp.name
                # Write normalized header
                tmp.write(f"{pattern_column}\t{tinyids_column}\n")
                for file_path in merge_patterns:
                    from utils.file_utils import exit_if_missing
                    exit_if_missing(file_path, f"Merge input file")
                    with open(file_path, encoding='utf-8') as f:
                        file_header = f.readline().strip()
                        cols = file_header.split('\t')
                        try:
                            pat_idx = cols.index(pattern_column)
                        except ValueError:
                            logger.error(f"Column '{pattern_column}' not found in {file_path}. "
                                         f"Columns: {cols}")
                            raise SystemExit(1)
                        tid_idx = cols.index(tinyids_column) if tinyids_column in cols else None
                        for line in f:
                            line = line.rstrip('\n\r')
                            if not line:
                                continue
                            fields = line.split('\t')
                            pat_val = fields[pat_idx] if pat_idx < len(fields) else ''
                            tid_val = fields[tid_idx] if tid_idx is not None and tid_idx < len(fields) else ''
                            tmp.write(f"{pat_val}\t{tid_val}\n")
            merge_input = tmp_path
        else:
            merge_input = merge_patterns[0] if isinstance(merge_patterns, list) else merge_patterns

        logger.info(f"Merge mode: combining duplicate patterns in {merge_input}")
        stats = merge_verbatim_tsv(
            merge_input,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column
        )

        # Clean up temp file if created
        if isinstance(merge_patterns, list) and len(merge_patterns) > 1:
            os.unlink(tmp_path)

        print(f"Input:  {stats['input_rows']} rows from {len(merge_patterns) if isinstance(merge_patterns, list) else 1} file(s)")
        print(f"Output: {stats['output_rows']} unique patterns")
        print(f"Merged: {stats['merged_count']} duplicate patterns")
        print(f"Wrote:  {args.output}")
        return 0

    # Check for coalesce mode
    coalesce_variants = getattr(args, 'coalesce_variants', None)
    if coalesce_variants:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --coalesce-variants")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import coalesce_variants_tsv

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')
        report_path = getattr(args, 'coalesce_report', None)
        min_prefix_tinyids = getattr(args, 'min_prefix_tinyids', 0)
        min_parent_tinyids = getattr(args, 'min_parent_tinyids', 0)
        rollup_subset_tinyids = getattr(args, 'rollup_subset_tinyids', False)
        trim_anchors = not getattr(args, 'no_trim_anchors', False)
        emit_def_variants = getattr(args, 'emit_def_variants', False)
        defer_parent_filter = getattr(args, 'defer_parent_filter', False)
        min_actual_tinyids = getattr(args, 'min_actual_tinyids', 0)

        logger.info(f"Coalesce mode: removing subsumed patterns from {coalesce_variants}")
        if trim_anchors:
            logger.info("Anchor trimming enabled (strip anchor phrases to bare names)")
        if min_prefix_tinyids > 0:
            logger.info(f"Prefix extraction enabled (min_tinyids={min_prefix_tinyids})")
        if min_parent_tinyids > 0:
            mode = "deferred (after prefix extraction)" if defer_parent_filter else "immediate"
            logger.info(f"Parent threshold filter enabled (min_parent_tinyids={min_parent_tinyids}, mode={mode})")
        if rollup_subset_tinyids:
            logger.info("TinyId-subset rollup enabled")
        if emit_def_variants:
            logger.info("Definition-form variant emission enabled")

        stats = coalesce_variants_tsv(
            coalesce_variants,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column,
            report_path=report_path,
            min_prefix_tinyids=min_prefix_tinyids,
            min_parent_tinyids=min_parent_tinyids,
            rollup_subset_tinyids=rollup_subset_tinyids,
            trim_anchors=trim_anchors,
            emit_def_variants=emit_def_variants,
            defer_parent_filter=defer_parent_filter,
            min_actual_tinyids=min_actual_tinyids
        )

        print(f"\nCoalesce complete:")
        print(f"  Input:    {stats['input_patterns']} patterns")
        print(f"  Output:   {stats['output_patterns']} patterns")
        if stats.get('anchor_trimmed_count', 0) > 0:
            print(f"  Anchors:  {stats['anchor_trimmed_count']} patterns trimmed to bare names")
        print(f"  Subsumed: {stats['subsumed_count']} patterns removed")
        if stats.get('prefix_kept_count', 0) > 0:
            print(f"  Prefix-kept: {stats['prefix_kept_count']} shorter patterns retained for stripping")
        if stats.get('reverse_subsumed_count', 0) > 0:
            print(f"  Roll-down: {stats['reverse_subsumed_count']} greedy expansions removed")
        if stats.get('prefix_extracted_count', 0) > 0:
            print(f"  Prefixes: {stats['prefix_extracted_count']} patterns -> common stems")
        if stats.get('rollup_count', 0) > 0:
            print(f"  Rollup:   {stats['rollup_count']} short patterns rolled up by tinyId subset")
        if stats.get('parent_filtered_count', 0) > 0:
            print(f"  Parent filter: {stats['parent_filtered_count']} patterns below threshold")
        if stats.get('parent_rescued_count', 0) > 0:
            print(f"  Parent rescued: {stats['parent_rescued_count']} weak-parent patterns saved by prefix groups")
        if stats.get('high_freq_rescued_count', 0) > 0:
            print(f"  High-freq rescued: {stats['high_freq_rescued_count']} patterns protected by min_actual_tinyids={min_actual_tinyids}")
        if stats.get('def_variant_count', 0) > 0:
            print(f"  Def variants: {stats['def_variant_count']} definition-form patterns added")
        if report_path:
            print(f"  Report:   {report_path}")
        print(f"  Wrote:    {args.output}")

        # Show a few examples of subsumptions
        if stats['subsumptions']:
            print(f"\nExample subsumptions (showing first 5):")
            for pattern, covers in stats['subsumptions'][:5]:
                cover_sample = covers[0][:40] if covers else "?"
                if len(covers) > 1:
                    cover_sample += f" (+{len(covers)-1} more)"
                print(f"  '{pattern[:50]}' -> '{cover_sample}'")

        # Split tiers if requested
        split_tiers = getattr(args, 'split_tiers', 0)
        if split_tiers > 0:
            import csv
            base, ext = os.path.splitext(args.output)
            short_path = f"{base}_short{ext}"

            tier1_rows = []
            tier2_rows = []
            with open(args.output, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                fieldnames = reader.fieldnames
                for row in reader:
                    pattern = row.get(pattern_column, '')
                    if len(pattern.split()) >= split_tiers:
                        tier1_rows.append(row)
                    else:
                        tier2_rows.append(row)

            # Rewrite main output with tier-1 only
            with open(args.output, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                                        lineterminator='\n')
                writer.writeheader()
                for row in tier1_rows:
                    writer.writerow(row)

            # Write tier-2 (short patterns)
            with open(short_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                                        lineterminator='\n')
                writer.writeheader()
                for row in tier2_rows:
                    writer.writerow(row)

            print(f"\n  Tier split (min_tokens={split_tiers}):")
            print(f"    Tier-1 (long):  {len(tier1_rows)} patterns → {args.output}")
            print(f"    Tier-2 (short): {len(tier2_rows)} patterns → {short_path}")

        return 0

    # No mode specified
    logger.error("No mode specified.")
    print("\nUsage:")
    print("  cde-analyzer pattern_util --edit FILE                    # interactive TSV editor")
    print("  cde-analyzer pattern_util --yaml-to-tsv FILE -o OUT.tsv # YAML → TSV for editing")
    print("  cde-analyzer pattern_util --tsv-to-yaml FILE -o OUT.yaml # TSV → YAML")
    print("  cde-analyzer pattern_util --to-minimal FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --merge-patterns FILE [FILE ...] -o OUTPUT")
    print("  cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --group-hierarchy FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --field-analysis FILE -i JSON -m CDE -o OUTPUT")
    print("  cde-analyzer pattern_util --harvest-residuals SANITY.tsv --curated CURATED.tsv -o OUTPUT")
    print("  cde-analyzer pattern_util --update-ledger NEW.tsv --ledger LEDGER.tsv -o OUTPUT")
    print("  cde-analyzer pattern_util --add-to-supplementary FILE")
    print("  cde-analyzer pattern_util --harvest-to-supplementary HARVEST.tsv")
    print("  cde-analyzer pattern_util --promote-supplementary [--clean-local]")
    print("  cde-analyzer pattern_util --detect-rare-words -i JSON -o OUTPUT")
    print("  cde-analyzer pattern_util --init-curation FILE --curators a,b -o DIR")
    print("  cde-analyzer pattern_util --merge-curation F1.tsv F2.tsv -o DIR")
    raise SystemExit(1)
