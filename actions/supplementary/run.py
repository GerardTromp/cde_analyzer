#
# File: actions/supplementary/run.py
#
"""
Supplementary - Run module for supplementary pattern management.

Provides import, harvest, YAML/TSV conversion, and ledger utilities.
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
    print(f"Convert back: cde-analyzer supplementary --tsv-to-yaml {output_path} -o {yaml_path}")

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


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for supplementary action."""

    yaml_to_tsv = getattr(args, 'yaml_to_tsv', None)
    if yaml_to_tsv:
        return _run_yaml_to_tsv(args, yaml_to_tsv)

    tsv_to_yaml = getattr(args, 'tsv_to_yaml', None)
    if tsv_to_yaml:
        return _run_tsv_to_yaml(args, tsv_to_yaml)

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

    harvest_to_supp = getattr(args, 'harvest_to_supplementary', None)
    if harvest_to_supp:
        return _run_harvest_to_supplementary(args, harvest_to_supp)

    promote_supp = getattr(args, 'promote_supplementary', False)
    if promote_supp:
        return _run_promote_supplementary(args)

    harvest_residuals = getattr(args, 'harvest_residuals', None)
    if harvest_residuals:
        return _run_harvest_residuals(args, harvest_residuals)

    update_ledger = getattr(args, 'update_ledger', None)
    if update_ledger:
        return _run_update_ledger(args, update_ledger)

    logger.error("No supplementary mode specified. Use --help for available options.")
    raise SystemExit(1)
