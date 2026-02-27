"""
Inter-rater reliability statistics for multi-curator curation workflows.

Implements Cohen's Kappa (pairwise, 2 raters) and Krippendorff's Alpha
(N raters, nominal scale, handles missing data) using only the Python
standard library.  No external dependencies required.

Algorithm references:
    Cohen's Kappa:  Cohen (1960), "A Coefficient of Agreement for Nominal Scales"
    Krippendorff's Alpha: Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability"
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default decision categories and tie-break order (highest priority first)
DEFAULT_CATEGORIES = ["keep", "remove", "modify"]
TIE_BREAK_ORDER = {"keep": 0, "modify": 1, "remove": 2}


# ──────────────────────────────────────────────────────────────
# Result dataclasses
# ──────────────────────────────────────────────────────────────

@dataclass
class PairwiseKappa:
    """Cohen's Kappa result for one curator pair."""
    curator_a: str
    curator_b: str
    observed_agreement: float   # P_o
    expected_agreement: float   # P_e
    kappa: float                # (P_o - P_e) / (1 - P_e)
    n_items: int                # Items both rated
    n_agree: int                # Items where both agree
    confusion_matrix: Dict[Tuple[str, str], int] = field(default_factory=dict)


@dataclass
class AgreementStats:
    """Complete inter-rater statistics for a curation round."""
    n_curators: int
    n_patterns: int
    n_reviewed: int             # Patterns with at least 2 non-empty decisions
    n_unanimous: int            # All curators who reviewed agree
    n_majority: int             # Majority agrees but not all
    n_split: int                # No majority

    overall_agreement_pct: float         # % unanimous among reviewed
    per_category_agreement: Dict[str, float] = field(default_factory=dict)

    pairwise_kappas: List[PairwiseKappa] = field(default_factory=list)
    krippendorff_alpha: Optional[float] = None

    consensus_decisions: Dict[str, str] = field(default_factory=dict)
    discrepancies: List[Dict] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Cohen's Kappa (pairwise, 2 raters)
# ──────────────────────────────────────────────────────────────

def cohens_kappa(
    ratings_a: List[str],
    ratings_b: List[str],
    curator_a: str = "A",
    curator_b: str = "B",
    categories: Optional[List[str]] = None,
) -> PairwiseKappa:
    """
    Compute Cohen's Kappa for two raters on the same items.

    Parameters
    ----------
    ratings_a : list[str]
        Category labels from rater A (one per item).
    ratings_b : list[str]
        Category labels from rater B (same length as ratings_a).
    curator_a, curator_b : str
        Names of the two raters (for reporting).
    categories : list[str], optional
        Explicit category list.  If None, inferred from data.

    Returns
    -------
    PairwiseKappa
        Kappa statistic with supporting metrics.

    Notes
    -----
    - All-agree → kappa = 1.0.
    - P_e == 1.0 (degenerate) → kappa = 1.0.
    - Empty input → kappa = 0.0, n_items = 0.
    """
    n = len(ratings_a)
    if n == 0 or n != len(ratings_b):
        return PairwiseKappa(
            curator_a=curator_a, curator_b=curator_b,
            observed_agreement=0.0, expected_agreement=0.0,
            kappa=0.0, n_items=0, n_agree=0,
        )

    if categories is None:
        categories = sorted(set(ratings_a) | set(ratings_b))

    # Build confusion matrix
    confusion: Dict[Tuple[str, str], int] = Counter()
    n_agree = 0
    for a, b in zip(ratings_a, ratings_b):
        confusion[(a, b)] += 1
        if a == b:
            n_agree += 1

    # Observed agreement
    p_o = n_agree / n

    # Marginal proportions
    count_a = Counter(ratings_a)
    count_b = Counter(ratings_b)

    # Expected agreement by chance
    p_e = sum((count_a.get(c, 0) / n) * (count_b.get(c, 0) / n)
              for c in categories)

    # Kappa
    if p_e >= 1.0:
        kappa = 1.0  # Degenerate: both always choose same category
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    return PairwiseKappa(
        curator_a=curator_a,
        curator_b=curator_b,
        observed_agreement=round(p_o, 4),
        expected_agreement=round(p_e, 4),
        kappa=round(kappa, 4),
        n_items=n,
        n_agree=n_agree,
        confusion_matrix=dict(confusion),
    )


# ──────────────────────────────────────────────────────────────
# Krippendorff's Alpha (N raters, nominal, missing data)
# ──────────────────────────────────────────────────────────────

def krippendorff_alpha(
    ratings_matrix: Dict[str, Dict[str, str]],
    categories: Optional[List[str]] = None,
) -> Optional[float]:
    """
    Compute Krippendorff's Alpha for N raters on nominal data.

    Uses the coincidence matrix method (Krippendorff 2011).
    Handles missing data naturally — not all raters need to rate all items.

    Parameters
    ----------
    ratings_matrix : dict[str, dict[str, str]]
        ``{item_id: {rater_name: category_label}}``.
        Missing entries mean the rater did not review that item.
        Empty strings are treated as missing.
    categories : list[str], optional
        Explicit category list.  If None, inferred from data.

    Returns
    -------
    float or None
        Alpha value, or None if fewer than 2 items have 2+ raters.
    """
    # Collect all non-empty ratings per item
    item_ratings: Dict[str, List[str]] = {}
    all_values: Set[str] = set()

    for item_id, rater_decisions in ratings_matrix.items():
        vals = [v for v in rater_decisions.values() if v]  # skip empty
        if len(vals) >= 2:
            item_ratings[item_id] = vals
            all_values.update(vals)

    if len(item_ratings) < 2:
        return None  # Insufficient data

    if categories is None:
        categories = sorted(all_values)

    cat_idx = {c: i for i, c in enumerate(categories)}
    n_cats = len(categories)

    # Build coincidence matrix
    # o[c][k] = sum over items of (count_c * count_k) / (m - 1) for c != k
    #           and count_c * (count_c - 1) / (m - 1) for c == k
    o = [[0.0] * n_cats for _ in range(n_cats)]
    n_total = 0.0

    for vals in item_ratings.values():
        m = len(vals)
        if m < 2:
            continue
        val_counts = Counter(vals)
        for c_val, c_count in val_counts.items():
            ci = cat_idx.get(c_val)
            if ci is None:
                continue
            for k_val, k_count in val_counts.items():
                ki = cat_idx.get(k_val)
                if ki is None:
                    continue
                if ci == ki:
                    # Pairs of same category: c_count * (c_count - 1)
                    o[ci][ki] += (c_count * (c_count - 1)) / (m - 1)
                else:
                    # Pairs of different categories: c_count * k_count
                    o[ci][ki] += (c_count * k_count) / (m - 1)

    # Total coincidences
    n_total = sum(o[i][j] for i in range(n_cats) for j in range(n_cats))
    if n_total == 0:
        return None

    # Observed disagreement proportion
    diag_sum = sum(o[i][i] for i in range(n_cats))
    d_o = 1.0 - (diag_sum / n_total)

    # Marginals
    n_c = [sum(o[c][k] for k in range(n_cats)) for c in range(n_cats)]

    # Expected disagreement
    d_e_numer = sum(n_c[c] * (n_c[c] - 1) for c in range(n_cats))
    d_e_denom = n_total * (n_total - 1)

    if d_e_denom == 0:
        return 1.0  # Degenerate

    d_e = 1.0 - (d_e_numer / d_e_denom)

    if d_e == 0:
        return 1.0  # No expected disagreement → perfect

    alpha = 1.0 - (d_o / d_e)
    return round(alpha, 4)


# ──────────────────────────────────────────────────────────────
# Aggregate statistics
# ──────────────────────────────────────────────────────────────

def compute_agreement_stats(
    decisions: Dict[str, Dict[str, str]],
    curators: List[str],
    categories: Optional[List[str]] = None,
) -> AgreementStats:
    """
    Compute all inter-rater statistics for a set of curation decisions.

    Parameters
    ----------
    decisions : dict[str, dict[str, str]]
        ``{pattern: {curator_name: decision_str}}``.
        Empty string or missing key = not reviewed.
    curators : list[str]
        Ordered list of curator names.
    categories : list[str], optional
        Valid decision categories.  Default: ["keep", "remove", "modify"].

    Returns
    -------
    AgreementStats
        Complete statistics with consensus, discrepancies, and metrics.
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    n_patterns = len(decisions)
    n_curators = len(curators)

    # Filter to patterns with 2+ non-empty decisions
    reviewed: Dict[str, Dict[str, str]] = {}
    for pattern, curator_map in decisions.items():
        non_empty = {c: d for c, d in curator_map.items() if d}
        if len(non_empty) >= 2:
            reviewed[pattern] = non_empty

    n_reviewed = len(reviewed)

    # Classify each reviewed pattern
    n_unanimous = 0
    n_majority = 0
    n_split = 0
    consensus_decisions: Dict[str, str] = {}
    discrepancies: List[Dict] = []

    for pattern, curator_map in reviewed.items():
        vals = list(curator_map.values())
        counts = Counter(vals)
        most_common_val, most_common_count = counts.most_common(1)[0]
        total_raters = len(vals)

        if most_common_count == total_raters:
            # Unanimous
            n_unanimous += 1
            consensus_decisions[pattern] = most_common_val
        elif most_common_count > total_raters / 2:
            # Majority
            n_majority += 1
            consensus_decisions[pattern] = most_common_val
            discrepancies.append({
                "pattern": pattern,
                "decisions": dict(curator_map),
                "consensus": most_common_val,
                "agreement_level": "majority",
            })
        else:
            # Split — tie-break by priority order
            n_split += 1
            # Among tied categories, pick by TIE_BREAK_ORDER
            max_count = counts.most_common(1)[0][1]
            tied = [c for c, cnt in counts.items() if cnt == max_count]
            winner = min(tied, key=lambda c: TIE_BREAK_ORDER.get(c, 99))
            consensus_decisions[pattern] = winner
            discrepancies.append({
                "pattern": pattern,
                "decisions": dict(curator_map),
                "consensus": winner,
                "agreement_level": "split",
            })

    # Also include patterns with only 1 decision (consensus = that decision)
    for pattern, curator_map in decisions.items():
        if pattern not in consensus_decisions:
            non_empty = {c: d for c, d in curator_map.items() if d}
            if non_empty:
                # Single rater — take their decision
                consensus_decisions[pattern] = next(iter(non_empty.values()))

    # Overall agreement %
    overall_pct = (n_unanimous / n_reviewed * 100) if n_reviewed > 0 else 0.0

    # Per-category agreement
    per_cat: Dict[str, float] = {}
    for cat in categories:
        # Among patterns where any curator chose this category, % unanimous
        cat_patterns = [
            p for p, cm in reviewed.items()
            if cat in cm.values()
        ]
        if cat_patterns:
            cat_unanimous = sum(
                1 for p in cat_patterns
                if len(set(reviewed[p].values())) == 1
            )
            per_cat[cat] = round(cat_unanimous / len(cat_patterns) * 100, 1)
        else:
            per_cat[cat] = 0.0

    # Pairwise Cohen's Kappa
    pairwise_kappas: List[PairwiseKappa] = []
    if n_curators >= 2:
        for ca, cb in combinations(curators, 2):
            # Collect items both curators rated
            ra, rb = [], []
            for pattern, curator_map in reviewed.items():
                da = curator_map.get(ca, "")
                db = curator_map.get(cb, "")
                if da and db:
                    ra.append(da)
                    rb.append(db)
            if ra:
                pk = cohens_kappa(ra, rb, curator_a=ca, curator_b=cb,
                                  categories=categories)
                pairwise_kappas.append(pk)

    # Krippendorff's Alpha
    alpha = None
    if n_curators >= 2 and n_reviewed >= 2:
        alpha = krippendorff_alpha(reviewed, categories=categories)

    logger.info(
        f"Agreement stats: {n_reviewed} reviewed, "
        f"{n_unanimous} unanimous ({overall_pct:.1f}%), "
        f"{n_majority} majority, {n_split} split"
    )

    return AgreementStats(
        n_curators=n_curators,
        n_patterns=n_patterns,
        n_reviewed=n_reviewed,
        n_unanimous=n_unanimous,
        n_majority=n_majority,
        n_split=n_split,
        overall_agreement_pct=round(overall_pct, 1),
        per_category_agreement=per_cat,
        pairwise_kappas=pairwise_kappas,
        krippendorff_alpha=alpha,
        consensus_decisions=consensus_decisions,
        discrepancies=discrepancies,
    )
