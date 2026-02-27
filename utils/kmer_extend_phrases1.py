from typing import List, Dict, Any, Optional

def extend_phrases_in_bin(
    phrases: List[Dict[str, Any]],
    overlap_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Extend overlapping phrases within a count bin, 
    merge tinyIds, and recompute counts correctly.
    """

    def try_merge(p1: List[str], p2: List[str]) -> Optional[List[str]]:
        """
        Try merging p1 and p2 if they overlap sufficiently.
        Return merged phrase if possible, else None.
        """
        max_overlap = min(len(p1), len(p2))
        for k in range(max_overlap, 0, -1):
            if p1[-k:] == p2[:k]:
                if k / len(p1) >= overlap_threshold:
                    return p1 + p2[k:]
            if p2[-k:] == p1[:k]:
                if k / len(p2) >= overlap_threshold:
                    return p2 + p1[k:]
        return None

    # Track phrase, count, tinyIds
    phrase_entries = [
        {
            "phrase": p["phrase"],
            "count": p["count"],
            "tinyIds": p.get("kmer_source", []),
            "fields": p.get("fields", []),
        }
        for p in phrases
    ]

    changed = True
    while changed:
        changed = False
        new_entries = []
        used = set()

        for i in range(len(phrase_entries)):
            if i in used:
                continue

            merged_entry = None
            for j in range(i + 1, len(phrase_entries)):
                if j in used:
                    continue

                merged_phrase = try_merge(
                    phrase_entries[i]["phrase"], phrase_entries[j]["phrase"]
                )
                if merged_phrase:
                    merged_entry = {
                        "phrase": merged_phrase,
                        # use min count as conservative proxy (avoid inflation)
                        "count": min(
                            phrase_entries[i]["count"],
                            phrase_entries[j]["count"],
                        ),
                        # union tinyIds
                        "tinyIds": list(
                            set(phrase_entries[i]["tinyIds"])
                            | set(phrase_entries[j]["tinyIds"])
                        ),
                        # union fields
                        "fields": list(
                            set(phrase_entries[i]["fields"])
                            | set(phrase_entries[j]["fields"])
                        ),
                    }
                    used.add(j)
                    break

            if merged_entry:
                new_entries.append(merged_entry)
                used.add(i)
                changed = True
            else:
                new_entries.append(phrase_entries[i])

        phrase_entries = new_entries

    # Deduplicate by phrase
    unique = {}
    for e in phrase_entries:
        key = tuple(e["phrase"])
        if key not in unique:
            unique[key] = e
        else:
            # merge counts conservatively and union tinyIds/fields
            unique[key]["count"] = max(unique[key]["count"], e["count"])
            unique[key]["tinyIds"] = list(set(unique[key]["tinyIds"]) | set(e["tinyIds"]))
            unique[key]["fields"] = list(set(unique[key]["fields"]) | set(e["fields"]))

    # Finalize with correct k
    result = []
    for e in unique.values():
        result.append(
            {
                "phrase": e["phrase"],
                "k": len(e["phrase"]),
                "count": e["count"],
                "kmer_source": e["tinyIds"],
                "fields": e["fields"],
            }
        )

    return sorted(result, key=lambda x: len(x["phrase"]), reverse=True)

