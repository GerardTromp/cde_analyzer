#
# File: actions/pattern_diag/run.py
#
"""
Pattern Diag - Run module for pattern diagnostics.

Provides rare word detection, remnant analysis, and parent-filtered recovery.
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helper: exclusion set loader
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Helper: rare-word whitelist loader
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Rare word detection
# ──────────────────────────────────────────────────────────────

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
# Parent-filtered recovery diagnostic
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Remnant analysis
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for pattern_diag action."""

    detect_rare = getattr(args, 'detect_rare_words', False)
    if detect_rare:
        return _run_detect_rare_words(args)

    remnant_analysis = getattr(args, 'remnant_analysis', None)
    if remnant_analysis:
        return _run_remnant_analysis(args, remnant_analysis)

    recover_parent_filtered = getattr(args, 'recover_parent_filtered', None)
    if recover_parent_filtered:
        return _run_recover_parent_filtered(args, recover_parent_filtered)

    logger.error("No pattern_diag mode specified. Use --help for available options.")
    raise SystemExit(1)
