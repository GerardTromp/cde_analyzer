#
# File: actions/pattern_util/run.py
#
"""
Pattern Util - Run module for core TSV pattern manipulation.

Provides merge, coalesce, field analysis, expand, and validate utilities.
Functions for curation, instruments, diagnostics, and supplementary management
have been moved to their respective action modules:
  - curation: Editor, multi-curator, ledger, gate, finalize, priority split
  - instrument_util: Group hierarchy, instrument splits, strip pattern generation
  - pattern_diag: Rare words, remnant analysis, recovery
  - supplementary: Import, harvest, YAML/TSV conversion, ledger updates
  - llm_classify: Semantic proxy generation
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


# ── Normalize to minimal format ──────────────────────────────────────────


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


# ── Helpers for field analysis ───────────────────────────────────────────


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


# ── Field analysis mode ──────────────────────────────────────────────────


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


# ── Validate subsumption ─────────────────────────────────────────────────


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


# ── Expand verbatim variants ─────────────────────────────────────────────


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
        f"Expanded {len(patterns)} patterns \u2192 {len(variant_to_sources)} variants "
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


# ── Expand temporal seeds ────────────────────────────────────────────────


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


# ── Main dispatcher ──────────────────────────────────────────────────────


def run_action(args: Namespace):
    """Main entry point for pattern_util action."""

    # Check for to-minimal mode first (simple normalization)
    to_minimal = getattr(args, 'to_minimal', None)
    if to_minimal:
        return _run_to_minimal(args, to_minimal)

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

    # Check for validate-subsumption mode
    validate_sub = getattr(args, 'validate_subsumption', None)
    if validate_sub:
        return _run_validate_subsumption(args, validate_sub)

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
            print(f"    Tier-1 (long):  {len(tier1_rows)} patterns \u2192 {args.output}")
            print(f"    Tier-2 (short): {len(tier2_rows)} patterns \u2192 {short_path}")

        return 0

    # No mode specified
    logger.error("No mode specified. Use --help for available options.")
    print("\nUsage:")
    print("  cde-analyzer pattern_util --merge-patterns FILE [FILE ...] -o OUTPUT")
    print("  cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --field-analysis FILE -i JSON -o OUTPUT")
    print("  cde-analyzer pattern_util --validate-subsumption FILE -i JSON -o OUTPUT")
    print("  cde-analyzer pattern_util --to-minimal FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --expand-verbatim FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --expand-temporal-seeds -o OUTPUT")
    print("\nSee also: curation, instrument_util, pattern_diag, supplementary, llm_classify")
    raise SystemExit(1)
