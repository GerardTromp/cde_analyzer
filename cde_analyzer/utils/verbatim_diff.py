"""
Verbatim text difference detection.

Compares multiple verbatim forms of the same phrase to identify
divergent regions (prefix, suffix, internal differences).
"""

from typing import List, Dict, Tuple, Optional


def _longest_common_substring(s1: str, s2: str) -> Tuple[str, int, int]:
    """
    Find the longest common substring between two strings.

    Returns:
        Tuple of (substring, start_index_in_s1, start_index_in_s2)
    """
    m, n = len(s1), len(s2)
    # Use suffix array approach for better performance on longer strings
    result = ''
    result_i, result_j = 0, 0

    # Dynamic programming approach
    # dp[j] represents the length of LCS ending at s1[i-1] and s2[j-1]
    dp = [0] * (n + 1)

    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev + 1
                if dp[j] > len(result):
                    result = s1[i - dp[j]:i]
                    result_i = i - dp[j]
                    result_j = j - dp[j]
            else:
                dp[j] = 0
            prev = temp

    return result, result_i, result_j


def find_common_prefix(strings: List[str], case_sensitive: bool = False) -> str:
    """Find the longest common prefix among all strings."""
    if not strings:
        return ""
    if len(strings) == 1:
        return strings[0]

    if case_sensitive:
        compare_strings = strings
    else:
        compare_strings = [s.lower() for s in strings]

    # Use the shortest string as reference
    min_len = min(len(s) for s in compare_strings)
    prefix_len = 0

    for i in range(min_len):
        chars = set(s[i] for s in compare_strings)
        if len(chars) == 1:
            prefix_len = i + 1
        else:
            break

    # Return original case from first string
    return strings[0][:prefix_len]


def find_common_suffix(strings: List[str], case_sensitive: bool = False) -> str:
    """Find the longest common suffix among all strings."""
    if not strings:
        return ""
    if len(strings) == 1:
        return strings[0]

    if case_sensitive:
        compare_strings = strings
    else:
        compare_strings = [s.lower() for s in strings]

    # Use the shortest string as reference
    min_len = min(len(s) for s in compare_strings)
    suffix_len = 0

    for i in range(1, min_len + 1):
        chars = set(s[-i] for s in compare_strings)
        if len(chars) == 1:
            suffix_len = i
        else:
            break

    if suffix_len == 0:
        return ""
    # Return original case from first string
    return strings[0][-suffix_len:]


def extract_divergent_region(
    verbatim: str,
    common_prefix: str,
    common_suffix: str,
    case_sensitive: bool = False
) -> str:
    """
    Extract the divergent (middle) portion of a string after removing
    common prefix and suffix.

    Args:
        verbatim: The full verbatim string
        common_prefix: Common prefix to remove
        common_suffix: Common suffix to remove
        case_sensitive: Whether comparison is case-sensitive

    Returns:
        The divergent middle portion, or empty string if none
    """
    if case_sensitive:
        text = verbatim
        prefix = common_prefix
        suffix = common_suffix
    else:
        text = verbatim.lower()
        prefix = common_prefix.lower()
        suffix = common_suffix.lower()

    start = len(prefix)
    end = len(verbatim) - len(suffix) if suffix else len(verbatim)

    if start >= end:
        return ""

    # Return original case
    return verbatim[start:end]


def compute_verbatim_diffs(
    verbatim_forms: List[str],
    case_sensitive: bool = False
) -> Dict[str, Dict]:
    """
    Compute difference annotations for multiple verbatim forms.

    Compares each form to the longest form (reference) to identify:
    - prefix_diff: Content at start of reference that this form is missing
    - suffix_diff: Content at end of reference that this form is missing
    - unique_content: Any content in this form not in the reference

    Args:
        verbatim_forms: List of verbatim strings to compare
        case_sensitive: Whether to use case-sensitive comparison

    Returns:
        Dict mapping each verbatim form to its diff annotations:
        {
            "verbatim_text": {
                "prefix_diff": "...",
                "suffix_diff": "...",
                "diff_summary": "..."  # Human-readable summary
            }
        }
    """
    if not verbatim_forms:
        return {}

    if len(verbatim_forms) == 1:
        # Single form - no differences to annotate
        return {verbatim_forms[0]: {"prefix_diff": "", "suffix_diff": "", "diff_summary": ""}}

    # Use longest form as the reference
    sorted_forms = sorted(verbatim_forms, key=len, reverse=True)
    reference = sorted_forms[0]

    if case_sensitive:
        ref_compare = reference
    else:
        ref_compare = reference.lower()

    result = {}
    for verbatim in verbatim_forms:
        if case_sensitive:
            verb_compare = verbatim
        else:
            verb_compare = verbatim.lower()

        # Find where this form appears in the reference (if it does)
        match_start = ref_compare.find(verb_compare)

        if verbatim == reference:
            # This is the reference - mark it as such
            result[verbatim] = {
                "prefix_diff": "",
                "suffix_diff": "",
                "diff_summary": "[longest form]"
            }
        elif match_start >= 0:
            # This form is a substring of reference
            prefix_missing = reference[:match_start] if match_start > 0 else ""
            suffix_missing = reference[match_start + len(verbatim):] if match_start + len(verbatim) < len(reference) else ""

            # Truncate for display
            prefix_display = _truncate(prefix_missing, 40, "start")
            suffix_display = _truncate(suffix_missing, 40, "end")

            diff_parts = []
            if prefix_missing:
                diff_parts.append(f"prefix: \"{prefix_display}\"")
            if suffix_missing:
                diff_parts.append(f"suffix: \"{suffix_display}\"")

            result[verbatim] = {
                "prefix_diff": prefix_display,
                "suffix_diff": suffix_display,
                "diff_summary": "; ".join(diff_parts) if diff_parts else "[exact match]"
            }
        else:
            # Not a substring - find longest common substring
            lcs, ref_lcs_start, verb_lcs_start = _longest_common_substring(ref_compare, verb_compare)

            if len(lcs) > 20:
                # Significant overlap found via LCS
                match_len = len(lcs)

                # What's before the match in each (using original case)
                ref_prefix = reference[:ref_lcs_start]
                verb_prefix = verbatim[:verb_lcs_start]

                # What's after the match in each
                ref_suffix = reference[ref_lcs_start + match_len:]
                verb_suffix = verbatim[verb_lcs_start + match_len:]

                diff_parts = []
                if ref_prefix.lower() != verb_prefix.lower():
                    if verb_prefix and not ref_prefix:
                        diff_parts.append(f"extra prefix: \"{_truncate(verb_prefix, 30, 'end')}\"")
                    elif ref_prefix and not verb_prefix:
                        diff_parts.append(f"missing prefix: \"{_truncate(ref_prefix, 30, 'end')}\"")
                    else:
                        diff_parts.append(f"prefix: \"{_truncate(verb_prefix, 25, 'end')}\" vs \"{_truncate(ref_prefix, 25, 'end')}\"")

                if ref_suffix.lower() != verb_suffix.lower():
                    if verb_suffix and not ref_suffix:
                        diff_parts.append(f"extra suffix: \"{_truncate(verb_suffix, 30, 'start')}\"")
                    elif ref_suffix and not verb_suffix:
                        diff_parts.append(f"missing suffix: \"{_truncate(ref_suffix, 30, 'start')}\"")
                    else:
                        diff_parts.append(f"suffix: \"{_truncate(verb_suffix, 25, 'start')}\" vs \"{_truncate(ref_suffix, 25, 'start')}\"")

                result[verbatim] = {
                    "prefix_diff": _truncate(verb_prefix, 50, "end") if verb_prefix else "",
                    "suffix_diff": _truncate(verb_suffix, 50, "start") if verb_suffix else "",
                    "diff_summary": "; ".join(diff_parts) if diff_parts else "[minor variation]"
                }
            else:
                # No significant overlap - just note they differ
                result[verbatim] = {
                    "prefix_diff": "",
                    "suffix_diff": "",
                    "diff_summary": "[no significant overlap with longest]"
                }

    return result


def _truncate(s: str, max_len: int, keep: str = "end") -> str:
    """Truncate string, keeping start or end portion."""
    if len(s) <= max_len:
        return s
    if keep == "start":
        return s[:max_len - 3] + "..."
    else:  # keep == "end"
        return "..." + s[-(max_len - 3):]


def annotate_verbatim_differences(
    refined_groups: Dict[str, Dict],
    case_sensitive: bool = False
) -> Dict[str, Dict]:
    """
    Add difference annotations to refined verbatim groups.

    For phrases with multiple verbatim forms, computes and adds
    diff annotations. For phrases with single forms, adds empty annotations.

    Args:
        refined_groups: Dict mapping verbatim_text -> {"count": int, "tinyids": set}
        case_sensitive: Whether to use case-sensitive comparison

    Returns:
        Same dict with added diff annotations for each entry
    """
    verbatim_forms = list(refined_groups.keys())

    if len(verbatim_forms) <= 1:
        # Single form or empty - no differences to compute
        for verbatim in refined_groups:
            refined_groups[verbatim]["prefix_diff"] = ""
            refined_groups[verbatim]["suffix_diff"] = ""
            refined_groups[verbatim]["diff_summary"] = ""
        return refined_groups

    # Compute differences
    diffs = compute_verbatim_diffs(verbatim_forms, case_sensitive)

    # Merge diff annotations into refined_groups
    for verbatim, diff_data in diffs.items():
        refined_groups[verbatim]["prefix_diff"] = diff_data.get("prefix_diff", "")
        refined_groups[verbatim]["suffix_diff"] = diff_data.get("suffix_diff", "")
        refined_groups[verbatim]["diff_summary"] = diff_data.get("diff_summary", "")

    return refined_groups
