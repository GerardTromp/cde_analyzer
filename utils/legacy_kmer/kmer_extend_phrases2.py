from collections import defaultdict

def extend_within_bins(phrases):
    """
    Stage 1: Extend phrases within the same (count, k) bin.

    Parameters
    ----------
    phrases : list of dict
        Each dict must have:
        - "phrase": list[str]
        - "k": int
        - "count": int
        - "tinyIds": list[str]

    Returns
    -------
    list of dict
        Extended phrases in the same format.
    """

    # group by (count, k)
    bins = defaultdict(list)
    for ph in phrases:
        bins[(ph["count"], ph["k"])].append(ph)

    extended_phrases = []

    for (count, k), bin_phrases in bins.items():
        # build index by prefix and suffix
        prefix_index = defaultdict(list)
        suffix_index = defaultdict(list)

        for ph in bin_phrases:
            prefix_index[tuple(ph["phrase"][:-1])].append(ph)
            suffix_index[tuple(ph["phrase"][1:])].append(ph)

        visited = set()

        for ph in bin_phrases:
            if id(ph) in visited:
                continue

            current = ph
            phrase_words = current["phrase"][:]
            tinyIds = set(current["tinyIds"])
            visited.add(id(current))

            # extend forward
            while tuple(phrase_words[1:]) in prefix_index:
                candidates = prefix_index[tuple(phrase_words[1:])]
                next_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        next_ph = cand
                        break
                if not next_ph:
                    break
                phrase_words.append(next_ph["phrase"][-1])
                tinyIds.update(next_ph["tinyIds"])
                visited.add(id(next_ph))

            # extend backward
            while tuple(phrase_words[:-1]) in suffix_index:
                candidates = suffix_index[tuple(phrase_words[:-1])]
                prev_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        prev_ph = cand
                        break
                if not prev_ph:
                    break
                phrase_words.insert(0, prev_ph["phrase"][0])
                tinyIds.update(prev_ph["tinyIds"])
                visited.add(id(prev_ph))

            extended_phrases.append({
                "phrase": phrase_words,
                "k": len(phrase_words),
                "count": count,  # stays same inside bin
                "tinyIds": sorted(tinyIds),
                "bin": (count, k)
            })

    return extended_phrases
