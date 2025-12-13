def consolidate_phrases(phrases):
    """
    Given a list of phrase dicts (all same count),
    try to merge them if they overlap.
    Repeat until no changes.
    """
    changed = True
    while changed:
        changed = False
        new_phrases = []
        used = [False] * len(phrases)

        for i, p1 in enumerate(phrases):
            if used[i]:
                continue
            merged = False
            for j, p2 in enumerate(phrases):
                if i == j or used[j]:
                    continue
                a, b = p1["phrase"], p2["phrase"]

                # Case: p1 overlaps p2 at suffix/prefix
                for overlap in range(min(len(a), len(b)) - 1, 0, -1):
                    if a[-overlap:] == b[:overlap]:
                        merged_phrase = a + b[overlap:]
                        new_phrases.append({
                            "phrase": merged_phrase,
                            "k": len(merged_phrase),
                            "count": p1["count"],
                            "kmer_source": sorted(set(p1["kmer_source"]) | set(p2["kmer_source"])),
                            "fields": sorted(set(p1["fields"]) | set(p2["fields"]))
                        })
                        used[i] = used[j] = True
                        merged = True
                        changed = True
                        break

                if merged:
                    break

            if not merged:
                new_phrases.append(p1)
                used[i] = True

        phrases = new_phrases

    return phrases
