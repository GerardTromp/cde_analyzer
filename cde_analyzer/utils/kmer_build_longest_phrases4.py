import json
from collections import defaultdict

def is_sub_kmer(small, large):
    """Return True if tuple `small` is a contiguous subsequence of tuple `large`."""
    n, m = len(small), len(large)
    for i in range(m - n + 1):
        if large[i:i+n] == small:
            return True
    return False


def extend_phrases_once(kmer_table):
    """
    Perform one iteration: process highest-count bin, return longest phrases,
    and remove all consumed kmers.
    """
    if not kmer_table:
        return [], []

    # normalize kmers to tuples
    for row in kmer_table:
        if not isinstance(row["kmer"], tuple):
            row["kmer"] = tuple(row["kmer"])

    # group by count
    count_bins = defaultdict(list)
    for row in kmer_table:
        count_bins[row["count"]].append(row)

    # take highest count bin
    top_count = max(count_bins.keys())
    kmers = sorted(count_bins[top_count], key=lambda r: -r["k"])

    results = []
    consumed = set()   # kmers consumed or subsumed

    used = set()
    for row in kmers:
        kmer = row["kmer"]
        if kmer in consumed or kmer in used:
            continue

        phrase = list(kmer)
        merged_sources = set(row.get("kmer_source", []))
        fields = set([row.get("field")]) if row.get("field") else set()

        used.add(kmer)
        extended = True
        while extended:
            extended = False
            for nxt in kmers:
                nkmer = nxt["kmer"]
                if nkmer in consumed or nkmer in used:
                    continue
                if tuple(phrase[-(nxt["k"]-1):]) == nkmer[:-1]:
                    phrase.append(nkmer[-1])
                    merged_sources.update(nxt.get("kmer_source", []))
                    if nxt.get("field"):
                        fields.add(nxt["field"])
                    used.add(nkmer)
                    extended = True
                    break

        phrase_tuple = tuple(phrase)
        results.append({
            "phrase": list(phrase_tuple),
            "k": len(phrase_tuple),
            "count": top_count,
            "kmer_source": sorted(merged_sources),
            "fields": sorted(fields)
        })

        # mark all sub-kmers inside this phrase as consumed
        for row2 in kmers:
            if row2["kmer"] not in consumed and is_sub_kmer(row2["kmer"], phrase_tuple):
                consumed.add(row2["kmer"])

    # remove consumed kmers from dataset
    remaining = [row for row in kmer_table if row["kmer"] not in consumed]

    return results, remaining


def build_longest_phrases_iterative(kmer_table):
    """
    Iteratively process all bins until all kmers are consumed.
    """
    all_results = []
    working = kmer_table[:]
    while working:
        results, working = extend_phrases_once(working)
        all_results.extend(results)
    return all_results

