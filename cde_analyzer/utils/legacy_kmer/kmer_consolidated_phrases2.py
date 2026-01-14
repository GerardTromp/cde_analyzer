from typing import List, Dict

def consolidate_phrases(phrases: List[Dict]) -> List[Dict]:
    """
    Consolidate phrases that share the same count and are subsequences
    of a longer phrase in that count-bin.

    Args:
        phrases: list of dicts with keys: phrase (list[str]), count, k, etc.

    Returns:
        new list of dicts, with redundant subsequences removed.
    """

    def is_subsequence(short: List[str], long: List[str]) -> bool:
        """Check if short is contiguous subsequence of long."""
        if len(short) > len(long):
            return False
        for i in range(len(long) - len(short) + 1):
            if long[i:i+len(short)] == short:
                return True
        return False

    # group by count
    bins: Dict[int, List[Dict]] = {}
    for p in phrases:
        bins.setdefault(p["count"], []).append(p)

    consolidated = []
    for count, group in bins.items():
        # sort by length descending, so longest phrases are considered first
        group_sorted = sorted(group, key=lambda x: len(x["phrase"]), reverse=True)
        kept = []
        for cand in group_sorted:
            # check if candidate is already covered by a longer kept phrase
            if any(is_subsequence(cand["phrase"], longer["phrase"]) for longer in kept):
                continue
            kept.append(cand)
        consolidated.extend(kept)

    return consolidated
