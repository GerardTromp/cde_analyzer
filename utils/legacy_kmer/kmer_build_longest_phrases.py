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
        { "kmer": tuple[str], "k": int, "count": int }
    Returns: list of dicts with longest phrases
        { "phrase": tuple[str], "k": int, "count": int }
    """

    # group by count
    count_bins = defaultdict(list)
    for row in kmer_table:
        count_bins[row["count"]].append(row)

    results = []
    discarded = set()   # store kmers already covered

    # process bins in descending count order
    for count in sorted(count_bins.keys(), reverse=True):
        kmers = sorted(count_bins[count], key=lambda r: -r["k"])  # longest first
        used = set()

        for row in kmers:
            kmer = row["kmer"]
            if kmer in discarded or kmer in used:
                continue

            phrase = list(kmer)
            used.add(kmer)

            # extend forward as long as possible
            extended = True
            while extended:
                extended = False
                for nxt in kmers:
                    if nxt["kmer"] in discarded or nxt["kmer"] in used:
                        continue
                    # if last k-1 words of phrase match prefix of candidate
                    if tuple(phrase[-(nxt["k"]-1):]) == nxt["kmer"][:-1]:
                        phrase.append(nxt["kmer"][-1])
                        used.add(nxt["kmer"])
                        extended = True
                        break  # restart scan

            phrase_tuple = tuple(phrase)
            results.append({
                "phrase": phrase_tuple,
                "k": len(phrase_tuple),
                "count": count
            })

            # mark all sub-kmers inside this phrase as discarded
            for row2 in kmers:
                if row2["kmer"] not in discarded and is_sub_kmer(row2["kmer"], phrase_tuple):
                    discarded.add(row2["kmer"])

    return results

