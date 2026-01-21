"""
Verbatim template extraction.

Extracts common structural templates from multiple verbatim forms of the same phrase,
identifying variable slots (prefix, suffix, internal infixes) where forms diverge.

Output is designed for programmatic use - slots contain regex patterns that can
match the observed variations.
"""

import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field


@dataclass
class TemplateSlot:
    """Represents a variable slot in a template."""
    name: str  # e.g., "prefix", "suffix", "infix1"
    position: int  # Character position in template where slot appears
    variants: List[str] = field(default_factory=list)  # Observed values
    regex: str = ""  # Generated regex pattern

    def __post_init__(self):
        if self.variants and not self.regex:
            self.regex = self._build_regex()

    def _build_regex(self) -> str:
        """Build a regex pattern that matches all observed variants."""
        if not self.variants:
            return ""

        # Filter out empty strings for the pattern, but note if empty is valid
        non_empty = [v for v in self.variants if v]
        has_empty = "" in self.variants or len(non_empty) < len(self.variants)

        if not non_empty:
            # All variants are empty - slot is optional/empty
            return ""

        if len(non_empty) == 1:
            # Single non-empty variant
            pattern = re.escape(non_empty[0])
            return f"({pattern})?" if has_empty else f"({pattern})"

        # Multiple variants - create alternation
        # Sort by length descending for greedy matching
        sorted_variants = sorted(non_empty, key=len, reverse=True)
        escaped = [re.escape(v) for v in sorted_variants]
        pattern = "|".join(escaped)
        return f"({pattern})?" if has_empty else f"({pattern})"


@dataclass
class VerbatimTemplate:
    """Represents an extracted template from multiple verbatim forms."""
    phrase_id: str
    core: str  # The common core text
    template_pattern: str  # Full regex pattern
    prefix_slot: Optional[TemplateSlot] = None
    suffix_slot: Optional[TemplateSlot] = None
    infix_slots: List[TemplateSlot] = field(default_factory=list)
    source_forms: List[str] = field(default_factory=list)

    def get_slot_regex(self, slot_name: str) -> str:
        """Get regex for a specific slot by name."""
        if slot_name == "prefix" and self.prefix_slot:
            return self.prefix_slot.regex
        elif slot_name == "suffix" and self.suffix_slot:
            return self.suffix_slot.regex
        else:
            for slot in self.infix_slots:
                if slot.name == slot_name:
                    return slot.regex
        return ""


def find_common_core(strings: List[str], case_sensitive: bool = False) -> Tuple[str, int]:
    """
    Find the longest common substring shared by ALL strings.

    Returns:
        Tuple of (common_core, start_position_in_first_string)
    """
    if not strings:
        return "", 0
    if len(strings) == 1:
        return strings[0], 0

    # Prepare comparison strings
    if case_sensitive:
        compare_strings = strings
    else:
        compare_strings = [s.lower() for s in strings]

    # Start with first string and find substrings common to all
    base = compare_strings[0]
    best_substring = ""
    best_start = 0

    # Try all substrings of base, longest first
    for length in range(len(base), 0, -1):
        for start in range(len(base) - length + 1):
            candidate = base[start:start + length]

            # Check if this substring exists in all other strings
            found_in_all = True
            for other in compare_strings[1:]:
                if candidate not in other:
                    found_in_all = False
                    break

            if found_in_all and len(candidate) > len(best_substring):
                best_substring = candidate
                best_start = start
                # Found longest possible at this length, can break inner loop
                break

        # If we found something at this length, no need to check shorter
        if len(best_substring) == length:
            break

    # Return original case from first string
    if best_substring:
        return strings[0][best_start:best_start + len(best_substring)], best_start
    return "", 0


def extract_prefix_suffix_variants(
    strings: List[str],
    core: str,
    case_sensitive: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Extract prefix and suffix variants for each string relative to the core.

    Returns:
        Tuple of (prefix_variants, suffix_variants) - parallel lists
    """
    prefixes = []
    suffixes = []

    if case_sensitive:
        core_compare = core
    else:
        core_compare = core.lower()

    for s in strings:
        if case_sensitive:
            s_compare = s
        else:
            s_compare = s.lower()

        # Find where core appears in this string
        idx = s_compare.find(core_compare)
        if idx >= 0:
            prefixes.append(s[:idx])
            suffixes.append(s[idx + len(core):])
        else:
            # Core not found as-is - shouldn't happen if find_common_core worked
            prefixes.append("")
            suffixes.append("")

    return prefixes, suffixes


def detect_internal_divergence(
    strings: List[str],
    case_sensitive: bool = False
) -> Tuple[str, List[Tuple[str, List[str]]]]:
    """
    Detect if strings have internal divergence (infixes) beyond prefix/suffix.

    This handles cases like:
        "the quick brown fox" vs "the quick red fox"
    where "brown" vs "red" is an internal variation.

    Returns:
        Tuple of (reconstructed_core_with_slots, list of (slot_name, variants))
    """
    if len(strings) < 2:
        return strings[0] if strings else "", []

    # Prepare comparison strings
    if case_sensitive:
        compare_strings = strings
    else:
        compare_strings = [s.lower() for s in strings]

    # Find common prefix
    min_len = min(len(s) for s in compare_strings)
    prefix_len = 0
    for i in range(min_len):
        chars = set(s[i] for s in compare_strings)
        if len(chars) == 1:
            prefix_len = i + 1
        else:
            break

    # Find common suffix (from the end)
    suffix_len = 0
    for i in range(1, min_len - prefix_len + 1):
        chars = set(s[-i] for s in compare_strings)
        if len(chars) == 1:
            suffix_len = i
        else:
            break

    # Extract the middle portions (potential infixes)
    common_prefix = strings[0][:prefix_len]
    common_suffix = strings[0][-suffix_len:] if suffix_len > 0 else ""

    # Get middle variants
    middles = []
    for s in strings:
        end_idx = len(s) - suffix_len if suffix_len > 0 else len(s)
        middles.append(s[prefix_len:end_idx])

    # Check if middles are all different (simple case) or have sub-structure
    unique_middles = list(set(middles))

    if len(unique_middles) <= 1:
        # No internal divergence
        return strings[0], []

    # For now, treat the entire middle as a single infix slot
    # More sophisticated analysis could recursively find common sub-cores
    infix_slots = [("infix1", middles)]

    # Reconstruct template: prefix + {infix1} + suffix
    template = f"{common_prefix}{{infix1}}{common_suffix}"

    return template, infix_slots


def extract_template(
    verbatim_forms: List[str],
    phrase_id: str,
    case_sensitive: bool = False,
    min_core_length: int = 10
) -> Optional[VerbatimTemplate]:
    """
    Extract a template from multiple verbatim forms.

    Args:
        verbatim_forms: List of verbatim strings to analyze
        phrase_id: Identifier for this phrase
        case_sensitive: Whether to use case-sensitive comparison
        min_core_length: Minimum length for common core to be valid

    Returns:
        VerbatimTemplate object, or None if no meaningful template found
    """
    if not verbatim_forms:
        return None

    if len(verbatim_forms) == 1:
        # Single form - template is the form itself, no slots
        return VerbatimTemplate(
            phrase_id=phrase_id,
            core=verbatim_forms[0],
            template_pattern=re.escape(verbatim_forms[0]),
            source_forms=verbatim_forms
        )

    # Find common core
    core, core_start = find_common_core(verbatim_forms, case_sensitive)

    if len(core) < min_core_length:
        # No meaningful common core found
        # Fall back to using longest form as "template"
        longest = max(verbatim_forms, key=len)
        return VerbatimTemplate(
            phrase_id=phrase_id,
            core=longest,
            template_pattern=re.escape(longest),
            source_forms=verbatim_forms
        )

    # Extract prefix and suffix variants
    prefixes, suffixes = extract_prefix_suffix_variants(
        verbatim_forms, core, case_sensitive
    )

    # Create slots
    prefix_slot = None
    suffix_slot = None

    unique_prefixes = list(set(prefixes))
    if len(unique_prefixes) > 1 or (len(unique_prefixes) == 1 and unique_prefixes[0]):
        prefix_slot = TemplateSlot(
            name="prefix",
            position=0,
            variants=unique_prefixes
        )

    unique_suffixes = list(set(suffixes))
    if len(unique_suffixes) > 1 or (len(unique_suffixes) == 1 and unique_suffixes[0]):
        suffix_slot = TemplateSlot(
            name="suffix",
            position=len(core),
            variants=unique_suffixes
        )

    # Build template pattern
    pattern_parts = []
    if prefix_slot:
        pattern_parts.append(prefix_slot.regex)
    pattern_parts.append(re.escape(core))
    if suffix_slot:
        pattern_parts.append(suffix_slot.regex)

    template_pattern = "".join(pattern_parts)

    return VerbatimTemplate(
        phrase_id=phrase_id,
        core=core,
        template_pattern=template_pattern,
        prefix_slot=prefix_slot,
        suffix_slot=suffix_slot,
        source_forms=verbatim_forms
    )


def extract_templates_for_phrase(
    refined_groups: Dict[str, Dict],
    phrase_id: str,
    case_sensitive: bool = False
) -> Optional[VerbatimTemplate]:
    """
    Extract template from refined verbatim groups for a single phrase.

    Args:
        refined_groups: Dict mapping verbatim_text -> {"count": int, "tinyids": set}
        phrase_id: Identifier for this phrase
        case_sensitive: Whether to use case-sensitive comparison

    Returns:
        VerbatimTemplate object, or None if only one form exists
    """
    verbatim_forms = list(refined_groups.keys())

    if len(verbatim_forms) <= 1:
        # Single form - no template needed
        return None

    return extract_template(verbatim_forms, phrase_id, case_sensitive)


def format_template_row(template: VerbatimTemplate) -> Dict[str, str]:
    """
    Format a template for TSV output.

    Returns dict with keys:
        phrase_id, core, template_regex, prefix_slot, suffix_slot,
        infix1_slot, infix2_slot, n_variants, variant_forms
    """
    result = {
        "phrase_id": template.phrase_id,
        "core": template.core,
        "template_regex": template.template_pattern,
        "prefix_slot": template.prefix_slot.regex if template.prefix_slot else "",
        "prefix_variants": "|".join(template.prefix_slot.variants) if template.prefix_slot else "",
        "suffix_slot": template.suffix_slot.regex if template.suffix_slot else "",
        "suffix_variants": "|".join(template.suffix_slot.variants) if template.suffix_slot else "",
        "infix1_slot": "",
        "infix1_variants": "",
        "infix2_slot": "",
        "infix2_variants": "",
        "n_variants": str(len(template.source_forms)),
        "variant_forms": "|".join(template.source_forms)
    }

    # Add infix slots if present
    for i, slot in enumerate(template.infix_slots[:2]):  # Max 2 infixes
        key_slot = f"infix{i+1}_slot"
        key_variants = f"infix{i+1}_variants"
        result[key_slot] = slot.regex
        result[key_variants] = "|".join(slot.variants)

    return result
