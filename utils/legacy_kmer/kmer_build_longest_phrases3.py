import json
from collections import defaultdict

def is_sub_kmer(small, large):
    """Return True if tuple `small` is a contiguous subsequence of tuple `large`."""
    n, m = len(small), len(large)
    for i in range(m - n + 1):
        if large[i:i+n] == small:
            return True
    return False


def build_longest_phrases(kmer_table):
    """
    kmer_table: list of dicts like:
        {
          "id": str,
          "kmer_source": list[str],
          "kmer": list[str] or tuple[str],
          "k": int,
          "count": int,
          "field": str
        }
    Returns: list of dicts with longest phrases.
    """

    # normalize kmers to tuples
    for row in kmer_table:
        if not isinstance(row["kmer"], tuple):
            row["kmer"] = tuple(row["kmer"])

    # group by count
    count_bins = defaultdict(list)
    for row in kmer_table:
        count_bins[row["count"]].append(row)

    results = []
    discarded = set()

    for count in sorted(count_bins.keys(), reverse=True):
        kmers = sorted(count_bins[count], key=lambda r: -r["k"])
        used = set()

        for row in kmers:
            kmer = row["kmer"]
            if kmer in discarded or kmer in used:
                continue

            phrase = list(kmer)
            merged_sources = set(row.get("tinyId", []))
            fields = set([row.get("field")]) if row.get("field") else set()

            used.add(kmer)
            extended = True

            while extended:
                extended = False
                for nxt in kmers:
                    nkmer = nxt["kmer"]
                    if nkmer in discarded or nkmer in used:
                        continue
                    if tuple(phrase[-(nxt["k"]-1):]) == nkmer[:-1]:
                        phrase.append(nkmer[-1])
                        merged_sources.update(nxt.get("tinyId", []))
                        if nxt.get("field"):
                            fields.add(nxt["field"])
                        used.add(nkmer)
                        extended = True
                        break

            phrase_tuple = tuple(phrase)
            results.append({
                "phrase": list(phrase_tuple),   # JSON-safe
                "k": len(phrase_tuple),
                "count": count,
                "tinyIds": sorted(merged_sources),
                "fields": sorted(fields)
            })

            # discard subsumed
            for row2 in kmers:
                if row2["kmer"] not in discarded and is_sub_kmer(row2["kmer"], phrase_tuple):
                    discarded.add(row2["kmer"])

    return results