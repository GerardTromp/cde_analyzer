from collections import defaultdict
from typing import List, Dict, Any

def enrich_with_verbatim(
    phrases: List[Dict[str, Any]],
    tinyid_to_verbatim: Dict[str, str],
    add_variant_count: bool = True
) -> List[Dict[str, Any]]:
    """
    Map lemmatized phrase results back to verbatim variants using tinyIds.

    Args:
        phrases: list of dicts from polishing/connector phase.
        tinyid_to_verbatim: mapping tinyId -> verbatim text (full original).
        add_variant_count: if True, compute counts per verbatim variant.

    Returns:
        A new list of phrase dicts with 'verbatim_variants' attached:
        [
          {
            "phrase": [...],           # lemma tokens
            "k": ...,
            "count": ...,
            "tinyIds": [...],
            "fields": [...],
            "bin": (...),
            "verbatim_variants": [
                {"text": "...", "tinyIds": [...], "count": N},
                ...
            ]
          }
        ]
    """
    enriched = []

    for record in phrases:
        variant_map = defaultdict(list)

        for tid in record.get("tinyIds", []):
            if tid in tinyid_to_verbatim:
                text = tinyid_to_verbatim[tid]
                variant_map[text].append(tid)

        verbatim_variants = []
        for text, tids in variant_map.items():
            variant_info = {"text": text, "tinyIds": tids}
            if add_variant_count:
                variant_info["count"] = len(tids)
            verbatim_variants.append(variant_info)

        enriched.append({
            **record,
            "verbatim_variants": verbatim_variants
        })

    return enriched
