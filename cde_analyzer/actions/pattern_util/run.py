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

    # Load exclusion set if provided
    exclusion_set = set()
    if exclude_path:
        exit_if_missing(exclude_path, "Exclusion patterns file")
        exclusion_set = _load_exclusion_set(exclude_path)
        logger.info(f"Loaded {len(exclusion_set)} exclusion patterns")

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

    # Compute field distribution
    field_dist = compute_field_distribution(parsed, verbatim_map, field_paths)

    # Derive field column names
    field_col_names = [fp.rsplit('.', 1)[-1] for fp in field_paths]

    # Apply filters and write output
    # Strip existing field columns from header if re-running
    existing_field_cols = set()
    for col in field_col_names:
        col_count = f"{col}_count"
        if col_count in headers:
            existing_field_cols.add(col_count)
    if "field_profile" in headers:
        existing_field_cols.add("field_profile")

    # Build clean header (remove old field columns if present)
    clean_header_indices = [i for i, h in enumerate(headers) if h not in existing_field_cols]
    clean_headers = [headers[i] for i in clean_header_indices]

    # Add new field columns
    new_headers = clean_headers[:]
    for col in field_col_names:
        new_headers.append(f"{col}_count")
    new_headers.append("field_profile")

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

        # Append field columns
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
        print(f"  Excluded: {excluded_count} (from exclusion list)")
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

        logger.info(f"Coalesce mode: removing subsumed patterns from {coalesce_variants}")
        if trim_anchors:
            logger.info("Anchor trimming enabled (strip anchor phrases to bare names)")
        if min_prefix_tinyids > 0:
            logger.info(f"Prefix extraction enabled (min_tinyids={min_prefix_tinyids})")
        if min_parent_tinyids > 0:
            logger.info(f"Parent threshold filter enabled (min_parent_tinyids={min_parent_tinyids})")
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
            emit_def_variants=emit_def_variants
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
    raise SystemExit(1)
