from collections import defaultdict

def group_connectors(
    phrases,
    min_branch=2,
    constrain_fields=False,
    both_directions=True,
):
    """
    Phase 3: Group phrases around common connector phrases 
    that appear as prefixes/suffixes of multiple extended phrases.

    Parameters
    ----------
    phrases : list of dict
        Output from polish_phrases (phase 2).
        Each dict must contain "phrase", "count", "tinyIds", "fields".
    min_branch : int
        Minimum number of divergent extensions needed to treat
        a phrase as a connector.
    constrain_fields : bool
        If True, only merge branches that share the same field(s).
        If False, merge across all fields.
    both_directions : bool
        If True, consider both prefix and suffix connectors.
        If False, only prefixes.

    Returns
    -------
    list of dict
        Connector groups with recomputed counts. Each group has:
            - "connector" : dict with phrase and recomputed counts
            - "branches"  : list of branch dicts
            - "direction" : "prefix" or "suffix"
    """

    phrase_map = {tuple(p["phrase"]): p for p in phrases}
    connector_groups = []
    used = set()

    def process_connector(conn_phrase, branches, direction):
        """Build a connector group, recomputing counts."""
        if len(branches) < min_branch:
            return None

        # field partitioning
        if constrain_fields:
            groups = defaultdict(list)
            for b in branches:
                for f in b["fields"]:
                    groups[f].append(b)
        else:
            groups = {"*": branches}

        results = []
        for field, branch_list in groups.items():
            if len(branch_list) < min_branch:
                continue

            connector = phrase_map[conn_phrase]

            branch_ids = set().union(*(b["tinyIds"] for b in branch_list))
            branch_fields = set().union(*(b["fields"] for b in branch_list))

            connector_recomputed = {
                "phrase": list(conn_phrase),
                "count": len(branch_ids),
                "tinyIds": branch_ids,
                "fields": branch_fields,
                "original_count": connector["count"],
            }

            group = {
                "connector": connector_recomputed,
                "branches": branch_list,
                "direction": direction,
            }
            results.append(group)

            used.add(conn_phrase)
            for b in branch_list:
                used.add(tuple(b["phrase"]))

        return results

    # --- Prefix connectors ---
    prefix_groups = defaultdict(list)
    for ph in phrases:
        for i in range(1, len(ph["phrase"])):
            prefix = tuple(ph["phrase"][:i])
            if prefix in phrase_map:
                prefix_groups[prefix].append(tuple(ph["phrase"]))

    for prefix, exts in prefix_groups.items():
        branches = [phrase_map[e] for e in exts if e in phrase_map]
        results = process_connector(prefix, branches, "prefix")
        if results:
            connector_groups.extend(results)

    # --- Suffix connectors ---
    if both_directions:
        suffix_groups = defaultdict(list)
        for ph in phrases:
            for i in range(1, len(ph["phrase"])):
                suffix = tuple(ph["phrase"][i:])
                if suffix in phrase_map:
                    suffix_groups[suffix].append(tuple(ph["phrase"]))

        for suffix, exts in suffix_groups.items():
            branches = [phrase_map[e] for e in exts if e in phrase_map]
            results = process_connector(suffix, branches, "suffix")
            if results:
                connector_groups.extend(results)

    return connector_groups
