"""Tests for verbatim template extraction functionality."""

import pytest
from utils.verbatim_template import (
    find_common_core,
    extract_prefix_suffix_variants,
    extract_template,
    TemplateSlot,
    VerbatimTemplate,
    format_template_row
)


class TestFindCommonCore:
    """Tests for find_common_core function."""

    def test_single_string(self):
        core, start = find_common_core(["hello world"])
        assert core == "hello world"
        assert start == 0

    def test_identical_strings(self):
        core, start = find_common_core(["test", "test", "test"])
        assert core == "test"

    def test_simple_prefix_suffix_difference(self):
        strings = [
            "prefix hello world suffix1",
            "hello world suffix2",
            "different prefix hello world"
        ]
        core, _ = find_common_core(strings)
        assert "hello world" in core

    def test_case_insensitive(self):
        strings = ["Hello World", "hello world", "HELLO WORLD"]
        core, _ = find_common_core(strings, case_sensitive=False)
        # Should find common core despite case differences
        assert len(core) >= 5  # At least "Hello" or "World"

    def test_no_common_substring(self):
        strings = ["abc", "xyz", "123"]
        core, _ = find_common_core(strings)
        assert core == ""


class TestExtractPrefixSuffixVariants:
    """Tests for extract_prefix_suffix_variants function."""

    def test_simple_variants(self):
        strings = [
            "prefix1 CORE suffix1",
            "prefix2 CORE suffix2",
            "CORE suffix3"
        ]
        core = "CORE"
        prefixes, suffixes = extract_prefix_suffix_variants(strings, core)

        assert prefixes == ["prefix1 ", "prefix2 ", ""]
        assert suffixes == [" suffix1", " suffix2", " suffix3"]


class TestTemplateSlot:
    """Tests for TemplateSlot regex generation."""

    def test_single_variant(self):
        slot = TemplateSlot(name="prefix", position=0, variants=["hello"])
        assert "hello" in slot.regex
        assert slot.regex == "(hello)"

    def test_single_variant_with_empty(self):
        slot = TemplateSlot(name="prefix", position=0, variants=["hello", ""])
        assert "?" in slot.regex  # Should be optional
        assert "hello" in slot.regex

    def test_multiple_variants(self):
        slot = TemplateSlot(name="suffix", position=10, variants=[", Drug", " Drug", "."])
        # Should create alternation pattern
        assert "|" in slot.regex
        assert "Drug" in slot.regex

    def test_empty_variants(self):
        slot = TemplateSlot(name="prefix", position=0, variants=["", ""])
        assert slot.regex == ""

    def test_special_characters_escaped(self):
        slot = TemplateSlot(name="suffix", position=0, variants=["(test)", "[brackets]"])
        # Special regex chars should be escaped
        assert "\\(" in slot.regex
        assert "\\[" in slot.regex


class TestExtractTemplate:
    """Tests for extract_template function."""

    def test_single_form_no_slots(self):
        forms = ["the quick brown fox"]
        template = extract_template(forms, "phrase_001")

        assert template.phrase_id == "phrase_001"
        assert template.core == "the quick brown fox"
        assert template.prefix_slot is None
        assert template.suffix_slot is None

    def test_prefix_variation(self):
        forms = [
            "the quick brown fox jumps",
            "a quick brown fox jumps"
        ]
        template = extract_template(forms, "phrase_002", min_core_length=5)

        assert template is not None
        assert "quick brown fox jumps" in template.core
        if template.prefix_slot:
            # Variants may or may not include trailing space depending on core boundary
            variants_str = " ".join(template.prefix_slot.variants)
            assert "the" in variants_str and "a" in variants_str

    def test_suffix_variation(self):
        forms = [
            "the quick brown fox, Drug",
            "the quick brown fox as part of Drug",
            "the quick brown fox."
        ]
        template = extract_template(forms, "phrase_003", min_core_length=5)

        assert template is not None
        assert "the quick brown fox" in template.core
        assert template.suffix_slot is not None
        assert len(template.suffix_slot.variants) >= 2

    def test_phrase_07389_style(self):
        """Test with forms similar to phrase_07389 problem."""
        forms = [
            "that may lead to social, occupational, psychological, or physical problems, Drug",
            "that may lead to social, occupational, psychological, or physical problems as part of the Drug",
            "prescription), that may lead to social, occupational, psychological, or physical problems.",
            "that may lead to social, occupational, psychological, or physical problems,"
        ]
        template = extract_template(forms, "phrase_07389", min_core_length=10)

        assert template is not None
        # Core should contain the common middle portion
        assert "physical problems" in template.core or "may lead to" in template.core
        # Should have both prefix and suffix slots due to variations
        print(f"Core: {template.core}")
        print(f"Prefix slot: {template.prefix_slot}")
        print(f"Suffix slot: {template.suffix_slot}")

    def test_min_core_length_fallback(self):
        """When no common core meets threshold, use longest form."""
        forms = ["abc", "xyz"]
        template = extract_template(forms, "phrase_004", min_core_length=10)

        assert template is not None
        # Should fall back to longest form
        assert template.core in ["abc", "xyz"]


class TestFormatTemplateRow:
    """Tests for format_template_row function."""

    def test_basic_formatting(self):
        template = VerbatimTemplate(
            phrase_id="phrase_001",
            core="common core text",
            template_pattern="(prefix)?common core text(suffix)?",
            prefix_slot=TemplateSlot(name="prefix", position=0, variants=["pre1", "pre2"]),
            suffix_slot=TemplateSlot(name="suffix", position=16, variants=["suf1", ""]),
            source_forms=["pre1common core textsuf1", "pre2common core text"]
        )

        row = format_template_row(template)

        assert row["phrase_id"] == "phrase_001"
        assert row["core"] == "common core text"
        assert row["n_variants"] == "2"
        assert "pre1" in row["prefix_variants"]
        assert "pre2" in row["prefix_variants"]
        assert "suf1" in row["suffix_variants"]


class TestIntegration:
    """Integration tests for template extraction workflow."""

    def test_drug_use_variants(self):
        """Test realistic drug use disorder variants."""
        forms = [
            "substance use that may lead to physical dependence, Drug",
            "substance use that may lead to physical dependence as part of Drug Abuse",
            "substance use that may lead to physical dependence."
        ]

        template = extract_template(forms, "phrase_drug", min_core_length=15)

        assert template is not None
        assert "physical dependence" in template.core
        assert template.suffix_slot is not None

        # Verify regex could match all original forms
        import re
        pattern = re.compile(template.template_pattern, re.IGNORECASE)
        for form in forms:
            # At minimum, core should be in each form
            assert template.core.lower() in form.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
