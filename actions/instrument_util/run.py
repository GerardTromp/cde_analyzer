#
# File: actions/instrument_util/run.py
#
"""
Instrument Util - Run module for instrument hierarchy analysis.

Provides group hierarchy, instrument split analysis, and strip pattern generation.
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


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


def _run_analyze_instrument_splits(args, input_path: str) -> int:
    """
    Analyze curated instrument patterns for field-aware full/sub splits.

    Groups patterns by shared prefix (hierarchy), computes field-level
    frequencies for the proposed full (prefix) and sub (separator+suffix)
    texts, and writes a curation TSV for curator review.

    The curator approves or rejects each proposed split.  After curation,
    the output is fed to --generate-strip-patterns (splits mode) to produce
    genuinely different inst_full.tsv and inst_sub.tsv pattern files.
    """
    import json
    import re
    from pydantic import ValidationError
    from utils.constants import MODEL_REGISTRY
    from utils.file_utils import exit_if_missing
    from utils.pattern_tsv_utils import find_column_index
    from actions.strip_discover.run import compute_field_distribution
    from logic.group_hierarchy import build_group_hierarchy

    # ── Validate args ────────────────────────────────────────────────────
    input_json = getattr(args, 'input', None)
    output_path = getattr(args, 'output', None)
    if not input_json:
        logger.error("--input (CDE JSON) is required for --analyze-instrument-splits")
        raise SystemExit(1)
    if not output_path:
        logger.error("--output is required for --analyze-instrument-splits")
        raise SystemExit(1)

    exit_if_missing(input_path, "Curated instrument patterns TSV")
    exit_if_missing(input_json, "Input CDE JSON")

    model_name = getattr(args, 'model', 'CDE')
    field_paths = getattr(args, 'fields',
                          ["definitions.*.definition", "designations.*.designation"])
    min_group_size = getattr(args, 'min_group_size', 2)
    min_prefix_words = getattr(args, 'min_prefix_words', 2)

    # ── Read curated patterns TSV ────────────────────────────────────────
    rows = []  # (pattern, tinyids_set, tinyids_str)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')
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
            if pattern:
                rows.append((pattern, tinyids, tinyids_str))

    logger.info(f"Loaded {len(rows)} curated instrument patterns")

    # ── Build group hierarchy ────────────────────────────────────────────
    patterns_with_tinyids = {pat: tids for pat, tids, _ in rows}
    assignments, stats = build_group_hierarchy(
        patterns_with_tinyids,
        min_group_size=min_group_size,
        min_prefix_words=min_prefix_words,
    )

    # Build lookup: pattern -> GroupAssignment
    pat_to_assign = {a.sub_group: a for a in assignments}

    logger.info(
        f"Hierarchy: {stats.get('grouped_count', 0)} grouped in "
        f"{stats.get('group_count', 0)} groups, "
        f"{stats.get('ungrouped_count', 0)} singletons"
    )

    # ── Abbreviation extraction helper ───────────────────────────────────
    # Matches trailing parenthesized/bracketed abbreviations like (PHQ-9),
    # (CES-D), (SF-12v2), [AHRQ].  Captures the full bracketed text.
    _ABBREV_RE = re.compile(
        r'\s*'                         # optional leading whitespace
        r'(\([A-Z][A-Za-z0-9\-/.]+\)'  # parenthesized: (PHQ-9)
        r'|\[[A-Z][A-Za-z0-9\-/.]+\])' # or bracketed:  [AHRQ]
        r'\s*[-.]?\s*$'                 # optional trailing punct
    )

    def _extract_abbrev(text):
        """Extract trailing abbreviation from text, return (clean_text, abbrev)."""
        m = _ABBREV_RE.search(text)
        if m:
            return text[:m.start()].rstrip(), m.group(1)
        return text, ''

    # ── Preposition guard ─────────────────────────────────────────────────
    # Group prefixes ending with function words are invalid — the prefix
    # cut too early.  Members of bad-prefix groups become singletons.
    _FUNCTION_WORDS = frozenset({
        'for', 'of', 'in', 'at', 'on', 'to', 'by', 'with', 'from',
        'and', 'or', 'the', 'a', 'an',
    })

    bad_prefix_groups = set()
    # Check each unique group name from assignments
    for a in assignments:
        if a.group:
            words = a.group.split()
            if words and words[-1].lower() in _FUNCTION_WORDS:
                bad_prefix_groups.add(a.group)

    if bad_prefix_groups:
        logger.info(
            f"Preposition guard: {len(bad_prefix_groups)} groups with "
            f"function-word suffix → members become singletons: "
            f"{sorted(bad_prefix_groups)}"
        )

    # ── Compute separator and proposed splits ────────────────────────────
    # For each pattern, determine: category, proposed_full, proposed_sub,
    # proposed_abbrev, separator.
    split_info = {}  # pattern -> dict
    for pat, tids, _ in rows:
        a = pat_to_assign.get(pat)

        # --- Preposition guard: demote bad-prefix group members to singletons
        if a and a.group and a.group in bad_prefix_groups:
            clean_pat, abbrev = _extract_abbrev(pat)
            split_info[pat] = {
                'category': 'singleton',
                'proposed_full': clean_pat if abbrev else pat,
                'proposed_sub': '',
                'proposed_abbrev': abbrev,
                'separator': '',
                'group': '',
                'group_size': 1,
                'group_tinyid_count': len(tids),
            }
            continue

        if not a or not a.group:
            # Singleton: no group structure
            clean_pat, abbrev = _extract_abbrev(pat)
            split_info[pat] = {
                'category': 'singleton',
                'proposed_full': clean_pat if abbrev else pat,
                'proposed_sub': '',
                'proposed_abbrev': abbrev,
                'separator': '',
                'group': '',
                'group_size': 1,
                'group_tinyid_count': len(tids),
            }
        elif not a.suffix:
            # Group base: pattern IS the prefix (no suffix to split)
            clean_pat, abbrev = _extract_abbrev(pat)
            split_info[pat] = {
                'category': 'group_base',
                'proposed_full': clean_pat if abbrev else pat,
                'proposed_sub': '',
                'proposed_abbrev': abbrev,
                'separator': '',
                'group': a.group,
                'group_size': a.group_size,
                'group_tinyid_count': a.group_tinyid_count,
            }
        else:
            # Group member: split into full (prefix) and sub (separator + suffix)
            group_name = a.group  # cleaned prefix, e.g., "PROMIS"
            suffix = a.suffix     # e.g., "Anxiety"
            # Compute separator: text between group_name end and suffix start
            # in the complete pattern
            try:
                after_full = pat[len(group_name):]
                suffix_pos = after_full.rfind(suffix)
                if suffix_pos >= 0:
                    separator = after_full[:suffix_pos]
                else:
                    separator = after_full.replace(suffix, '', 1) if suffix in after_full else ''
            except (IndexError, ValueError):
                separator = ''
            proposed_sub = separator + suffix if separator or suffix else ''

            # Extract abbreviation from proposed_sub
            clean_sub, abbrev = _extract_abbrev(proposed_sub)

            # If sub is abbreviation-only (no semantic content after extraction),
            # reclassify as singleton — the complete pattern IS the full pattern.
            if abbrev and not clean_sub.strip():
                clean_pat, pat_abbrev = _extract_abbrev(pat)
                split_info[pat] = {
                    'category': 'singleton',
                    'proposed_full': clean_pat if pat_abbrev else pat,
                    'proposed_sub': '',
                    'proposed_abbrev': pat_abbrev or abbrev,
                    'separator': '',
                    'group': '',
                    'group_size': 1,
                    'group_tinyid_count': len(tids),
                }
            else:
                split_info[pat] = {
                    'category': 'group_member',
                    'proposed_full': group_name,
                    'proposed_sub': clean_sub if abbrev else proposed_sub,
                    'proposed_abbrev': abbrev,
                    'separator': separator,
                    'group': a.group,
                    'group_size': a.group_size,
                    'group_tinyid_count': a.group_tinyid_count,
                }

    # ── Orphan cascade: groups where all members became singletons ────────
    # If every member of a group was reclassified (abbreviation-only or
    # preposition guard), the group_base also becomes a singleton.
    group_member_counts = {}  # group_name -> count of remaining group_members
    for info in split_info.values():
        if info['category'] == 'group_member' and info['group']:
            group_member_counts[info['group']] = group_member_counts.get(info['group'], 0) + 1

    orphaned_groups = set()
    for pat in list(split_info.keys()):
        info = split_info[pat]
        if info['category'] == 'group_base' and info['group']:
            if group_member_counts.get(info['group'], 0) == 0:
                # All members gone — base becomes singleton too
                orphaned_groups.add(info['group'])
                info['category'] = 'singleton'
                info['group'] = ''
                info['group_size'] = 1
                info['group_tinyid_count'] = len(patterns_with_tinyids.get(pat, set()))

    if orphaned_groups:
        logger.info(
            f"Orphan cascade: {len(orphaned_groups)} groups fully dissolved "
            f"(all members became singletons)"
        )

    # ── Recount group sizes after reclassifications ───────────────────────
    # Group sizes may have changed due to abbreviation-only reclassification.
    final_group_sizes = {}   # group_name -> member count
    final_group_tids = {}    # group_name -> set of tinyIds
    for pat, tids, _ in rows:
        info = split_info[pat]
        g = info['group']
        if g and info['category'] in ('group_member', 'group_base'):
            final_group_sizes[g] = final_group_sizes.get(g, 0) + 1
            final_group_tids.setdefault(g, set()).update(tids)

    for info in split_info.values():
        g = info['group']
        if g:
            info['group_size'] = final_group_sizes.get(g, info['group_size'])
            info['group_tinyid_count'] = len(final_group_tids.get(g, set()))

    # ── Load CDE JSON for frequency analysis ─────────────────────────────
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

    # ── Frequency scan: proposed_full, proposed_sub, proposed_abbrev ─────
    # Build a verbatim_map for the UNIQUE proposed texts so we can measure
    # how often each appears in CDE fields.
    freq_texts = {}  # text -> set of tinyIds (union of all patterns using this text)
    for pat, tids, _ in rows:
        info = split_info[pat]
        pf = info['proposed_full']
        ps = info['proposed_sub']
        pa = info.get('proposed_abbrev', '')
        if pf:
            freq_texts.setdefault(pf, set()).update(tids)
        if ps:
            freq_texts.setdefault(ps, set()).update(tids)
        if pa:
            freq_texts.setdefault(pa, set()).update(tids)

    logger.info(f"Frequency scan: {len(freq_texts)} unique full/sub/abbrev texts to check")
    freq_dist = compute_field_distribution(parsed, freq_texts, field_paths)

    # Derive short field names for counting
    field_short = [fp.rsplit('.', 1)[-1] for fp in field_paths]

    # Helper: total freq across all field types
    def _total_freq(text):
        dist = freq_dist.get(text, {})
        return sum(len(dist.get(fn, set())) for fn in field_short)

    # ── Write curation TSV ───────────────────────────────────────────────
    out_columns = [
        "pattern", "tinyIds", "tinyid_count",
        "category", "group",
        "proposed_full", "proposed_sub", "proposed_abbrev", "separator",
        "full_freq", "sub_freq", "abbrev_freq",
        "group_size", "group_tinyid_count",
        "decision", "modification",
    ]

    # Sort: group members grouped together, then singletons
    # Within groups: sort by group name, then pattern
    CATEGORY_ORDER = {'group_member': 0, 'group_base': 1, 'singleton': 2}

    def sort_key(row_tuple):
        pat, _, _ = row_tuple
        info = split_info[pat]
        return (
            CATEGORY_ORDER.get(info['category'], 9),
            info.get('group', '').lower(),
            pat.lower(),
        )

    sorted_rows = sorted(rows, key=sort_key)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('\t'.join(out_columns) + '\n')
        for pat, tids, tids_str in sorted_rows:
            info = split_info[pat]
            pa = info.get('proposed_abbrev', '')
            # Auto-accept singletons and group bases
            if info['category'] in ('singleton', 'group_base'):
                decision = 'approve'
            else:
                decision = ''
            f.write('\t'.join([
                pat,
                tids_str,
                str(len(tids)),
                info['category'],
                info['group'],
                info['proposed_full'],
                info['proposed_sub'],
                pa,
                info['separator'],
                str(_total_freq(info['proposed_full'])),
                str(_total_freq(info['proposed_sub'])) if info['proposed_sub'] else '0',
                str(_total_freq(pa)) if pa else '0',
                str(info['group_size']),
                str(info['group_tinyid_count']),
                decision,
                '',  # modification
            ]) + '\n')

    # ── Summary ──────────────────────────────────────────────────────────
    n_singleton = sum(1 for v in split_info.values() if v['category'] == 'singleton')
    n_base = sum(1 for v in split_info.values() if v['category'] == 'group_base')
    n_member = sum(1 for v in split_info.values() if v['category'] == 'group_member')
    n_groups = len(set(v['group'] for v in split_info.values() if v['group']))
    n_abbrev = sum(1 for v in split_info.values() if v.get('proposed_abbrev'))
    n_prepos = len(bad_prefix_groups)

    print(f"\nInstrument split analysis: {len(rows)} patterns")
    print(f"  Singletons (auto-approve): {n_singleton}")
    print(f"  Group bases (auto-approve): {n_base}")
    print(f"  Group members (needs review): {n_member}")
    print(f"  Unique groups: {n_groups}")
    print(f"  With abbreviation: {n_abbrev}")
    if n_prepos:
        print(f"  Bad-prefix groups dissolved: {n_prepos}")
    if orphaned_groups:
        print(f"  Orphan-cascaded groups: {len(orphaned_groups)}")
    print(f"\nOutput: {output_path}")
    print(f"Open in TSV editor: cde-analyzer pattern_util --edit {output_path}")

    return 0


def _run_generate_strip_patterns(args, input_path: str) -> int:
    """
    Generate two strip-ready pattern files from a group-hierarchy TSV.

    Produces:
    - {output}_full.tsv: pattern + tinyIds (full removal)
    - {output}_sub.tsv: pattern + tinyIds + replace_with (suffix retained)

    If the input contains 'proposed_full' and 'proposed_sub' columns (output
    of --analyze-instrument-splits after curation), uses field-aware splits
    mode producing genuinely different pattern text in full vs sub files.
    """
    import re
    from utils.file_utils import exit_if_missing
    from utils.pattern_tsv_utils import find_column_index

    output_base = getattr(args, 'output', None)
    if not output_base:
        logger.error("--output is required for --generate-strip-patterns")
        raise SystemExit(1)

    exit_if_missing(input_path, "Input TSV")

    # Strip .tsv extension from output base if present
    if output_base.endswith('.tsv'):
        output_base = output_base[:-4]

    full_path = f"{output_base}_full.tsv"
    sub_path = f"{output_base}_sub.tsv"

    # Read input TSV header to detect mode
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
    headers = header_line.split('\t')

    # Detect splits mode: presence of proposed_full column
    has_splits = 'proposed_full' in headers or 'proposed_full' in [h.lower() for h in headers]

    if has_splits:
        return _generate_strip_patterns_splits(input_path, headers, full_path, sub_path, args)
    else:
        return _generate_strip_patterns_legacy(input_path, headers, full_path, sub_path)


def _generate_strip_patterns_legacy(
    input_path: str, headers: list, full_path: str, sub_path: str,
) -> int:
    """Legacy mode: same pattern text in both files, suffix as replace_with."""
    from utils.pattern_tsv_utils import find_column_index

    pattern_idx = find_column_index(headers, 'pattern')
    tinyids_idx = find_column_index(headers, 'tinyIds')

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

    rows = []
    with open(input_path, encoding="utf-8") as f:
        f.readline()  # skip header
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
            replace_with = suffix if (group and suffix) else ""
            f.write(f"{pattern}\t{tinyids}\t{replace_with}\n")
            sub_count += 1
            if replace_with:
                replace_count += 1

    print(f"\nGenerated strip pattern files (legacy mode):")
    print(f"  Full removal: {full_path} ({full_count} patterns)")
    print(f"  Sub-group:    {sub_path} ({sub_count} patterns, {replace_count} with suffix retained)")

    return 0


def _generate_strip_patterns_splits(
    input_path: str, headers: list, full_path: str, sub_path: str,
    args=None,
) -> int:
    """Field-aware splits mode: different pattern text in full vs sub files.

    inst_full gets group prefix patterns (for grouped) or complete patterns
    (for singletons/rejected).  inst_sub gets separator+suffix patterns
    (for approved group members only).

    Abbreviation patterns are emitted to BOTH files so they are stripped
    whenever either M or S is active (no engine changes needed).

    Short prefix patterns (< 3 words) get REGEX: word-boundary anchoring.

    Decision mapping (curation → strip behavior):
      keep / modify  → emit to strip files (approved)
      remove         → skip entirely (not emitted)
      substitute     → emit to separate substitute file
      (empty)        → treated as approved (auto-accept singletons)

    When --input CDE JSON is provided, re-matches proposed_full and
    proposed_sub text against all CDE fields to get accurate tinyId sets.
    """
    import os
    import re
    from utils.pattern_tsv_utils import find_column_index

    pattern_idx = find_column_index(headers, 'pattern')
    tinyids_idx = find_column_index(headers, 'tinyIds')
    proposed_full_idx = find_column_index(headers, 'proposed_full')
    proposed_sub_idx = find_column_index(headers, 'proposed_sub')
    category_idx = find_column_index(headers, 'category')
    decision_idx = find_column_index(headers, 'decision')

    # Optional columns
    proposed_abbrev_idx = None
    modification_idx = None
    group_idx = None
    for i, h in enumerate(headers):
        hl = h.strip().lower()
        if hl == 'proposed_abbrev':
            proposed_abbrev_idx = i
        elif hl == 'modification':
            modification_idx = i
        elif hl == 'group':
            group_idx = i

    # Read all rows
    rows = []
    with open(input_path, encoding="utf-8") as f:
        f.readline()  # skip header
        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')

            def _col(idx):
                return fields[idx].strip().strip('"') if idx < len(fields) else ""

            pattern = _col(pattern_idx)
            tinyids_str = _col(tinyids_idx)
            proposed_full = _col(proposed_full_idx)
            proposed_sub = _col(proposed_sub_idx)
            category = _col(category_idx)
            decision = _col(decision_idx).lower()
            proposed_abbrev = _col(proposed_abbrev_idx) if proposed_abbrev_idx is not None else ""
            modification = _col(modification_idx) if modification_idx is not None else ""
            group = _col(group_idx) if group_idx is not None else ""

            if pattern:
                tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
                rows.append({
                    'pattern': pattern,
                    'tinyids': tinyids,
                    'tinyids_str': tinyids_str,
                    'proposed_full': proposed_full,
                    'proposed_sub': proposed_sub,
                    'proposed_abbrev': proposed_abbrev,
                    'category': category,
                    'decision': decision,
                    'modification': modification,
                    'group': group,
                })

    # ── Decision classification ──────────────────────────────────────────
    # Map curation decisions to strip actions
    EMIT_DECISIONS = {'keep', 'modify', 'approve', ''}  # emit to strip files
    SKIP_DECISIONS = {'remove'}
    SUBSTITUTE_DECISIONS = {'substitute'}

    emit_rows = [r for r in rows if r['decision'] in EMIT_DECISIONS]
    skip_rows = [r for r in rows if r['decision'] in SKIP_DECISIONS]
    substitute_rows = [r for r in rows if r['decision'] in SUBSTITUTE_DECISIONS]

    logger.info(
        f"Decision split: {len(emit_rows)} emit, "
        f"{len(skip_rows)} skip, {len(substitute_rows)} substitute"
    )

    # ── Build group tinyId scopes for sub-pattern re-matching ────────────
    # Sub-patterns should only match CDEs within their instrument group,
    # not all CDEs containing a common word like "Assessment" or "Anxiety".
    # Build group_name -> union(all member tinyIds) for scoping.
    group_tid_scopes = {}  # group_name -> set(tinyIds)
    for r in rows:
        g = r.get('group', '')
        if g:
            group_tid_scopes.setdefault(g, set()).update(r['tinyids'])

    # Map each proposed_sub text to the union of allowed tinyIds from its
    # group(s). A sub text appearing in multiple groups gets the union.
    sub_text_scopes = {}  # sub_text -> set(allowed_tinyIds)
    for r in emit_rows + substitute_rows:
        ps = r.get('proposed_sub', '')
        g = r.get('group', '')
        if ps and g and g in group_tid_scopes:
            sub_text_scopes.setdefault(ps, set()).update(group_tid_scopes[g])

    # ── Re-match against CDE JSON if --input provided ────────────────────
    rematch_map = None  # pattern_text -> set(tinyIds) from CDE scan
    cde_json_path = getattr(args, 'input', None) if args else None
    if cde_json_path:
        rematch_map = _rematch_patterns_against_cdes(
            emit_rows + substitute_rows, cde_json_path, args,
            sub_text_scopes=sub_text_scopes,
        )

    def _get_tinyids(pattern_text, fallback_tinyids):
        """Get tinyIds for a pattern text: re-matched if available, else fallback."""
        if rematch_map is not None and pattern_text in rematch_map:
            return rematch_map[pattern_text]
        return fallback_tinyids

    # ── Build inst_full.tsv ──────────────────────────────────────────────
    full_entries = {}  # pattern_text -> merged tinyIds set
    for r in emit_rows:
        is_group_member = r['category'] == 'group_member'
        pf = r['proposed_full'] or r['pattern']
        tids = _get_tinyids(pf, r['tinyids'])
        full_entries.setdefault(pf, set()).update(tids)

        # Abbreviation → also in inst_full (stripped whenever M is active)
        if r['proposed_abbrev']:
            abbrev_tids = _get_tinyids(r['proposed_abbrev'], r['tinyids'])
            full_entries.setdefault(r['proposed_abbrev'], set()).update(abbrev_tids)

    full_count = 0
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\n")
        for pat_text, tids in sorted(full_entries.items(), key=lambda x: x[0].lower()):
            emit_text = _anchor_short_pattern(pat_text)
            f.write(f"{emit_text}\t{' '.join(sorted(tids))}\n")
            full_count += 1

    # ── Build inst_sub.tsv ───────────────────────────────────────────────
    sub_entries = {}  # pattern_text -> merged tinyIds set
    for r in emit_rows:
        if r['proposed_sub']:
            ps = r['proposed_sub']
            tids = _get_tinyids(ps, r['tinyids'])
            sub_entries.setdefault(ps, set()).update(tids)

        # Abbreviation → also in inst_sub (stripped whenever S is active)
        if r['proposed_abbrev']:
            abbrev_tids = _get_tinyids(r['proposed_abbrev'], r['tinyids'])
            sub_entries.setdefault(r['proposed_abbrev'], set()).update(abbrev_tids)

    sub_count = 0
    with open(sub_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\n")
        for pat_text, tids in sorted(sub_entries.items(), key=lambda x: x[0].lower()):
            emit_text = _anchor_short_pattern(pat_text)
            f.write(f"{emit_text}\t{' '.join(sorted(tids))}\n")
            sub_count += 1

    # ── Build substitute file ────────────────────────────────────────────
    subst_path = None
    subst_count = 0
    if substitute_rows:
        subst_path = full_path.replace('_full.tsv', '_substitute.tsv')
        with open(subst_path, "w", encoding="utf-8") as f:
            f.write("pattern\treplace_with\ttinyIds\n")
            for r in substitute_rows:
                pat = r['proposed_full'] or r['pattern']
                replace_with = r['modification'] or ''
                tids = _get_tinyids(pat, r['tinyids'])
                f.write(f"{pat}\t{replace_with}\t{' '.join(sorted(tids))}\n")
                subst_count += 1

    # ── Summary ──────────────────────────────────────────────────────────
    n_abbrev = sum(1 for r in emit_rows if r['proposed_abbrev'])
    print(f"\nGenerated strip pattern files (field-aware splits mode):")
    print(f"  inst_full: {full_path} ({full_count} patterns)")
    print(f"  inst_sub:  {sub_path} ({sub_count} patterns)")
    if n_abbrev:
        print(f"  Abbreviations emitted to both files: {n_abbrev}")
    if subst_count:
        print(f"  Substitutes: {subst_path} ({subst_count} patterns)")
    print(f"  Skipped (remove): {len(skip_rows)}")
    if rematch_map is not None:
        print(f"  TinyIds re-matched against CDE JSON ({len(rematch_map)} unique texts)")

    return 0


def _rematch_patterns_against_cdes(rows, cde_json_path, args, *,
                                   sub_text_scopes=None):
    """Re-match proposed_full/proposed_sub/proposed_abbrev text against CDE fields.

    Returns dict mapping pattern_text -> set of tinyIds that contain it.

    Sub-pattern scoping: When ``sub_text_scopes`` is provided, sub-pattern texts
    are only matched against CDEs within their instrument group's tinyId scope.
    This prevents bare-word sub-patterns (e.g., "Assessment", "Anxiety") from
    matching thousands of unrelated CDEs, which would cause cross-instrument
    stripping artifacts (double-space gaps).
    """
    import re

    if sub_text_scopes is None:
        sub_text_scopes = {}

    # Collect unique pattern texts to match, tracking which are sub-scoped
    texts_to_match = set()
    for r in rows:
        if r.get('proposed_full'):
            texts_to_match.add(r['proposed_full'])
        if r.get('proposed_sub'):
            texts_to_match.add(r['proposed_sub'])
        if r.get('proposed_abbrev'):
            texts_to_match.add(r['proposed_abbrev'])
        if r.get('pattern'):
            texts_to_match.add(r['pattern'])
    texts_to_match.discard('')

    if not texts_to_match:
        return {}

    n_scoped = sum(1 for t in texts_to_match if t in sub_text_scopes)
    logger.info(
        f"Re-matching {len(texts_to_match)} unique pattern texts against CDE JSON "
        f"({n_scoped} group-scoped sub-patterns)"
    )

    # Load and parse CDEs
    import json
    from utils.constants import MODEL_REGISTRY

    model_name = getattr(args, 'model', 'CDE') or 'CDE'
    field_paths = getattr(args, 'fields', None) or [
        "definitions.*.definition", "designations.*.designation"
    ]

    model_cls = MODEL_REGISTRY[model_name]
    with open(cde_json_path, encoding="utf-8") as f:
        raw_data = json.load(f)
    parsed = [model_cls.model_validate(item) for item in raw_data]
    logger.info(f"Loaded {len(parsed)} CDEs from {cde_json_path}")

    # Build field text index (all CDEs, no filter)
    from actions.strip_discover.run import build_field_text_index
    tid_field_texts = build_field_text_index(parsed, field_paths)

    # Match each pattern text against CDE fields
    result = {}  # text -> set(tinyIds)
    n_scope_limited = 0
    for text in sorted(texts_to_match):
        matched_tids = set()
        escaped = re.escape(text)
        regex = re.compile(escaped)

        # Determine which CDEs to scan: scoped for sub-patterns, all for others
        scope_tids = sub_text_scopes.get(text)
        if scope_tids is not None:
            # Only scan CDEs within the instrument group's tinyId set
            scan_items = ((tid, tid_field_texts[tid])
                          for tid in scope_tids if tid in tid_field_texts)
            n_scope_limited += 1
        else:
            scan_items = tid_field_texts.items()

        for tid, field_dict in scan_items:
            for fp, field_texts in field_dict.items():
                for ft in field_texts:
                    if regex.search(ft):
                        matched_tids.add(tid)
                        break  # found in this field, check next field
        result[text] = matched_tids

    # Summary stats
    n_with_matches = sum(1 for tids in result.values() if tids)
    n_empty = sum(1 for tids in result.values() if not tids)
    logger.info(
        f"Re-match complete: {n_with_matches} texts matched, "
        f"{n_empty} texts with zero matches, "
        f"{n_scope_limited} group-scoped"
    )

    return result


def _anchor_short_pattern(text: str) -> str:
    """Add REGEX: word-boundary anchoring for short patterns (< 3 words).

    Short literal patterns risk false matches in unrelated text.
    Wrapping with \\b word boundaries prevents partial-word matches.
    """
    import re
    words = text.split()
    if len(words) >= 3:
        return text  # long enough to be safe as literal
    # Already a regex pattern
    if text.startswith("REGEX:"):
        return text
    # Anchor with word boundaries
    escaped = re.escape(text)
    return f"REGEX:\\b{escaped}\\b"


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


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for instrument_util action."""

    analyze_splits = getattr(args, 'analyze_instrument_splits', None)
    if analyze_splits:
        return _run_analyze_instrument_splits(args, analyze_splits)

    gen_strip = getattr(args, 'generate_strip_patterns', None)
    if gen_strip:
        return _run_generate_strip_patterns(args, gen_strip)

    group_hierarchy = getattr(args, 'group_hierarchy', None)
    if group_hierarchy:
        return _run_group_hierarchy(args, group_hierarchy)

    group_semantic = getattr(args, 'group_semantic', None)
    if group_semantic:
        return _run_group_semantic(args, group_semantic)

    logger.error("No instrument_util mode specified. Use --help for available options.")
    raise SystemExit(1)
