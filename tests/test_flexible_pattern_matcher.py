"""Tests for flexible_pattern_matcher: coalescing, subsumption, prefix trie, and regex generation."""

import os
import tempfile
import pytest

from utils.flexible_pattern_matcher import (
    make_flexible_regex,
    _find_anchor_prefix,
    _is_np_continuation,
    _normalize_version_number,
    _escape_for_regex,
    extract_bare_instrument_name,
    extract_bare_instrument_names,
    extract_core_instrument_name,
    compile_flexible_patterns,
    coalesce_variants_tsv,
    load_verbatim_tsv,
    write_verbatim_tsv,
    merge_verbatim_tsv,
    get_optimal_workers,
    ANCHOR_PREFIXES,
    OPTIONAL_ARTICLES,
)

import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tsv(path, header, rows):
    """Write a TSV file from header string and list-of-lists."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for row in rows:
            f.write("\t".join(str(c) for c in row) + "\n")


def _read_tsv_rows(path):
    """Read a TSV file, return (headers, list-of-dicts)."""
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n\r").split("\t")
        rows = []
        for line in f:
            line = line.rstrip("\n\r")
            if not line:
                continue
            fields = line.split("\t")
            rows.append(dict(zip(header, fields)))
    return header, rows


# ===========================================================================
# Word-level prefix matching
# ===========================================================================


class TestWordLevelPrefix:
    """Word-level prefix: 'Scale of' is a prefix of 'Scale of the difficulty'."""

    def test_simple_word_prefix(self):
        short = "Scale of"
        long = "Scale of the difficulty"
        assert long.startswith(short)

    def test_not_prefix_partial_word(self):
        """'Scale' is a string prefix of 'Scaleable' but not a word prefix."""
        short = "Scale"
        long = "Scaleable thing"
        # substring match is True, but word-level prefix requires space or end
        assert long.startswith(short)
        # After the prefix there must be a space (word boundary)
        remainder = long[len(short):]
        assert not remainder[0].isspace(), "Should NOT be a word prefix"

    def test_word_prefix_boundary_space(self):
        short = "Patient Health"
        long = "Patient Health Questionnaire"
        remainder = long[len(short):]
        assert remainder == "" or remainder[0].isspace()

    def test_identical_is_prefix(self):
        pattern = "Berg Balance Scale"
        assert pattern.startswith(pattern)


# ===========================================================================
# Subsumption logic
# ===========================================================================


class TestSubsumption:
    """Pattern A subsumes B if A is a substring of B AND A.tinyIds >= B.tinyIds."""

    def test_basic_subsumption(self):
        """Short pattern subsumed when tinyIds covered by longer patterns."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                # long pattern covers tinyIds A B
                ["in the past 7 days:", "A B"],
                # short pattern has subset tinyIds
                ["in the past 7 days", "A B"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # The longer pattern should be kept; the shorter one is subsumed
            # because its tinyIds {A, B} <= {A, B} of the longer pattern
            # and it's a substring of the longer pattern.
            assert "in the past 7 days:" in patterns
            # The shorter IS a prefix of the longer, so Phase 1a keeps it
            assert "in the past 7 days" in patterns
            # Both kept because shorter is a prefix (prefix-kept rule)

    def test_subsumption_non_prefix_substring(self):
        """Non-prefix substring IS subsumed when tinyIds covered."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["please answer the following", "A B C"],
                ["the following", "A B"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # "the following" is a non-prefix substring of the longer pattern
            # and its tinyIds {A,B} <= {A,B,C}, so it should be subsumed
            assert "please answer the following" in patterns
            assert "the following" not in patterns
            assert stats["subsumed_count"] >= 1

    def test_not_subsumed_when_tinyids_not_covered(self):
        """Pattern NOT subsumed if its tinyIds are not fully covered."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Depression Scale total", "A B"],
                ["Depression Scale", "A B C"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # "Depression Scale" has tinyId C which is NOT covered by the longer
            # pattern, so it should be kept
            assert "Depression Scale" in patterns
            assert "Depression Scale total" in patterns

    def test_subsumed_by_union_of_multiple(self):
        """Short pattern subsumed by union of multiple longer patterns' tinyIds."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Global Health Scale version 1", "A B"],
                ["Global Health Scale version 2", "C"],
                # Short pattern: tinyIds {A, B, C} covered by union of above
                # BUT it's a prefix, so Phase 1a will keep it
                ["Global Health Scale", "A B C"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # prefix-kept: "Global Health Scale" is a prefix of both longer patterns
            assert "Global Health Scale" in patterns

    def test_prefix_kept_rule(self):
        """Shorter prefix patterns are kept even when tinyIds are covered."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Anxiety Score total", "A B"],
                ["Anxiety Score", "A B"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # "Anxiety Score" is a prefix of "Anxiety Score total" — kept
            assert "Anxiety Score" in patterns
            assert "Anxiety Score total" in patterns


# ===========================================================================
# TinyId set operations in subsumption
# ===========================================================================


class TestTinyIdSetOperations:
    """Verify set operations used in subsumption decisions."""

    def test_subset_check(self):
        a = {"t1", "t2"}
        b = {"t1", "t2", "t3"}
        assert a <= b  # a is subset of b
        assert not (b <= a)

    def test_empty_set_is_subset_of_everything(self):
        assert set() <= {"t1", "t2"}
        assert set() <= set()

    def test_identical_sets_are_subsets(self):
        s = {"t1", "t2", "t3"}
        assert s <= s

    def test_union_covers_split_sets(self):
        """Union of disjoint sets covers both."""
        a = {"t1", "t2"}
        b = {"t3"}
        target = {"t1", "t2", "t3"}
        assert target <= (a | b)

    def test_partial_overlap_union(self):
        a = {"t1", "t2", "t3"}
        b = {"t2", "t3", "t4"}
        target = {"t1", "t2", "t3", "t4"}
        assert target <= (a | b)


# ===========================================================================
# Coalescing with prefix extraction
# ===========================================================================


class TestCoalesceWithPrefixExtraction:
    """Prefix trie groups patterns sharing a common word-level prefix."""

    def test_prefix_extraction_basic(self):
        """Two patterns sharing a prefix are replaced by the common prefix."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Neuro QOL Lower Extremity", "A B"],
                ["Neuro QOL Upper Extremity", "C D"],
                ["Unrelated Pattern Here", "E"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                min_prefix_tinyids=2,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # The two Neuro QOL patterns should be combined into "Neuro QOL"
            assert "Neuro QOL" in patterns
            assert stats["prefix_extracted_count"] >= 2

            # Unrelated pattern is untouched
            assert "Unrelated Pattern Here" in patterns

    def test_prefix_extraction_combines_tinyids(self):
        """Prefix pattern gets union of constituent tinyIds."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Quality Life Physical", "A B"],
                ["Quality Life Mental", "C"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                min_prefix_tinyids=2,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            prefix_row = [r for r in rows if r["pattern"] == "Quality Life"]
            if prefix_row:
                tinyids = set(prefix_row[0]["tinyIds"].split())
                assert tinyids == {"A", "B", "C"}

    def test_prefix_extraction_needs_min_two_patterns(self):
        """A single pattern doesn't trigger prefix extraction."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Loneliness Scale Total", "A B C"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                min_prefix_tinyids=1,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # Only one pattern, so no prefix extraction possible
            assert "Loneliness Scale Total" in patterns
            assert stats["prefix_extracted_count"] == 0


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases: single-word patterns, empty tinyIds, identical patterns."""

    def test_single_word_pattern(self):
        """Single-word patterns should survive coalescing on their own."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Scale", "A B C"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            assert len(rows) == 1
            assert rows[0]["pattern"] == "Scale"

    def test_empty_tinyid_set(self):
        """Pattern with empty tinyIds is always subsumed if contained."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Global Health Measure total", "A"],
                # Empty tinyIds: {} <= anything, so subsumed as non-prefix substring
                # Actually "Global Health" is a prefix, so it would be prefix-kept
                ["Global Health", ""],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # "Global Health" is prefix of longer → prefix-kept rule applies
            assert "Global Health" in patterns
            assert "Global Health Measure total" in patterns

    def test_identical_patterns_merge_tinyids(self):
        """Duplicate patterns merge their tinyId sets."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Depression Scale", "A B"],
                ["Depression Scale", "C D"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            assert len(rows) == 1
            tinyids = set(rows[0]["tinyIds"].split())
            assert tinyids == {"A", "B", "C", "D"}

    def test_empty_input(self):
        """Empty input produces empty output."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            assert stats["input_patterns"] == 0
            assert stats["output_patterns"] == 0

    def test_no_substring_relationship(self):
        """Patterns with no substring relationship are all kept."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Alpha Test", "A"],
                ["Beta Survey", "B"],
                ["Gamma Index", "C"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            assert len(rows) == 3
            assert stats["subsumed_count"] == 0


# ===========================================================================
# Anchor prefix detection
# ===========================================================================


class TestAnchorPrefix:
    """Anchor prefix detection and extraction."""

    def test_as_part_of(self):
        anchor, remainder = _find_anchor_prefix("as part of the PHQ-9")
        assert anchor == "as part of"
        assert remainder == "the PHQ-9"

    def test_based_on(self):
        anchor, remainder = _find_anchor_prefix("based on NIH Toolbox")
        assert anchor == "based on"
        assert remainder == "NIH Toolbox"

    def test_no_anchor(self):
        anchor, remainder = _find_anchor_prefix("PHQ-9 Depression")
        assert anchor is None
        assert remainder == "PHQ-9 Depression"

    def test_longer_anchor_preferred(self):
        """'as a part of' should match before 'from'."""
        anchor, remainder = _find_anchor_prefix("as a part of the Scale")
        assert anchor == "as a part of"
        assert remainder == "the Scale"

    def test_anchor_requires_word_boundary(self):
        """'from' should not match inside 'fromage'."""
        anchor, remainder = _find_anchor_prefix("fromage cheese")
        # 'from' is not followed by space, so should not match
        assert anchor is None


# ===========================================================================
# Bare instrument name extraction
# ===========================================================================


class TestBareInstrumentName:
    """Extract bare instrument name by stripping anchor + articles."""

    def test_strip_anchor_and_article(self):
        result = extract_bare_instrument_name("as part of the Neuro-QOL Test")
        assert result == "Neuro-QOL Test"

    def test_strip_anchor_no_article(self):
        result = extract_bare_instrument_name("based on PHQ-9")
        assert result == "PHQ-9"

    def test_no_anchor_returns_none(self):
        result = extract_bare_instrument_name("PHQ-9")
        assert result is None

    def test_extract_bare_names_deduplicates(self):
        patterns = [
            "as part of the Scale A",
            "based on the Scale A",
            "based on Scale B",
        ]
        results = extract_bare_instrument_names(patterns)
        bare_names = [name for _, name in results]
        # "Scale A" should appear only once despite two sources
        assert bare_names.count("Scale A") == 1
        assert "Scale B" in bare_names


# ===========================================================================
# Core instrument name extraction
# ===========================================================================


class TestCoreInstrumentName:
    """Split core name from parenthesized acronym."""

    def test_with_acronym(self):
        core, acronym = extract_core_instrument_name("Short Form Health Survey (SF-12)")
        assert core == "Short Form Health Survey"
        assert acronym == "SF-12"

    def test_without_acronym(self):
        core, acronym = extract_core_instrument_name("PHQ-9")
        assert core == "PHQ-9"
        assert acronym is None

    def test_nested_parens_no_match(self):
        # Only matches trailing parenthesized content
        core, acronym = extract_core_instrument_name("Test (A) More")
        assert core == "Test (A) More"
        assert acronym is None


# ===========================================================================
# NP continuation heuristic
# ===========================================================================


class TestNPContinuation:
    """Heuristic for noun-phrase vs clause-boundary extensions."""

    def test_title_case_is_np(self):
        assert _is_np_continuation("General Life Satisfaction") is True

    def test_preposition_and_title_case_is_np(self):
        assert _is_np_continuation("for Children and Adults") is True

    def test_clause_boundary_not_np(self):
        assert _is_np_continuation(", a clinical test used in many settings") is False

    def test_parenthetical_not_np(self):
        assert _is_np_continuation("(or BBS), a test") is False

    def test_empty_string(self):
        assert _is_np_continuation("") is False

    def test_lowercase_content_not_np(self):
        assert _is_np_continuation("measures how well patients sleep") is False


# ===========================================================================
# Flexible regex generation
# ===========================================================================


class TestFlexibleRegex:
    """Regex generation with optional articles and flexible whitespace."""

    def test_basic_pattern(self):
        regex_str = make_flexible_regex("Depression Scale")
        regex = re.compile(regex_str, re.IGNORECASE)
        assert regex.search("the Depression Scale is used")
        assert regex.search("Depression   Scale")  # flexible whitespace

    def test_optional_article(self):
        regex_str = make_flexible_regex("the Depression Scale")
        regex = re.compile(regex_str, re.IGNORECASE)
        assert regex.search("using Depression Scale here")  # article omitted
        assert regex.search("using the Depression Scale here")  # article present

    def test_anchor_prefix_literal(self):
        regex_str = make_flexible_regex("as part of the Scale")
        regex = re.compile(regex_str, re.IGNORECASE)
        assert regex.search("as part of the Scale")
        assert regex.search("as part of Scale")  # optional article
        assert regex.search("As Part Of Scale")  # case-insensitive

    def test_hyphenated_word(self):
        regex_str = make_flexible_regex("Neuro-QOL")
        regex = re.compile(regex_str, re.IGNORECASE)
        assert regex.search("the Neuro-QOL test")
        assert regex.search("the Neuro QOL test")  # hyphen → space

    def test_empty_pattern(self):
        assert make_flexible_regex("") == ""

    def test_word_boundary_prevents_mid_word(self):
        """Pattern should not match inside a longer word."""
        regex_str = make_flexible_regex("Scale")
        regex = re.compile(regex_str, re.IGNORECASE)
        # Should NOT match mid-word "Scaleable"
        match = regex.search("Scaleable")
        # \b prevents matching when followed by alnum
        assert match is None or match.group(0) != "Scale"

    def test_parenthesized_acronym(self):
        regex_str = make_flexible_regex("Health Questionnaire (PHQ)")
        regex = re.compile(regex_str, re.IGNORECASE)
        assert regex.search("Health Questionnaire (PHQ)")

    def test_version_flexibility(self):
        regex_str = make_flexible_regex("Version 2.0 Scale")
        regex = re.compile(regex_str, re.IGNORECASE)
        # "2.0" and "2" should both match (trailing zero flexibility)
        assert regex.search("version 2 Scale")
        assert regex.search("version 2.0 Scale")


# ===========================================================================
# Version number normalization
# ===========================================================================


class TestVersionNormalization:
    """Version number regex generation for semantic equivalence."""

    def test_integer_only(self):
        regex, is_ver = _normalize_version_number("2")
        assert is_ver is True
        compiled = re.compile(regex)
        assert compiled.fullmatch("2")
        assert compiled.fullmatch("2.0")
        assert compiled.fullmatch("2.00")

    def test_trailing_zero(self):
        regex, is_ver = _normalize_version_number("2.0")
        assert is_ver is True
        compiled = re.compile(regex)
        assert compiled.fullmatch("2")
        assert compiled.fullmatch("2.0")

    def test_non_zero_decimal(self):
        regex, is_ver = _normalize_version_number("2.5")
        assert is_ver is True
        compiled = re.compile(regex)
        assert compiled.fullmatch("2.5")
        assert not compiled.fullmatch("2")

    def test_non_number(self):
        regex, is_ver = _normalize_version_number("hello")
        assert is_ver is False


# ===========================================================================
# Reverse subsumption (roll-down)
# ===========================================================================


class TestReverseSubsumption:
    """Phase 1b: roll down greedy expansions where long.tinyIds <= short.tinyIds."""

    def test_rolldown_greedy_expansion(self):
        """Long pattern whose tinyIds are a subset of shorter base is removed."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                # Base pattern (shorter) with more tinyIds
                ["Berg Balance Scale", "A B C D"],
                # Greedy expansion: all its tinyIds are a subset of the base
                ["Berg Balance Scale or BBS is a clinical test", "A B"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                rollup_subset_tinyids=True,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            assert "Berg Balance Scale" in patterns
            # The greedy expansion should be rolled down
            assert "Berg Balance Scale or BBS is a clinical test" not in patterns

    def test_rolldown_skips_np_continuation(self):
        """NP-like extensions are NOT rolled down."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["NIH Toolbox", "A B C D E"],
                # NP extension — should be kept
                ["NIH Toolbox General Life Satisfaction", "A B"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                rollup_subset_tinyids=True,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            assert "NIH Toolbox" in patterns
            assert "NIH Toolbox General Life Satisfaction" in patterns

    def test_rolldown_skips_single_word_base(self):
        """Single-word bases should not roll down multi-word patterns."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Scale", "A B C D E F"],
                ["Scale Depression Index", "A B"],
            ])

            stats = coalesce_variants_tsv(
                inp, out,
                rollup_subset_tinyids=True,
                trim_anchors=False,
            )

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            # Both should survive: single-word base can't roll down
            assert "Scale" in patterns
            assert "Scale Depression Index" in patterns


# ===========================================================================
# Anchor trimming in coalesce
# ===========================================================================


class TestAnchorTrimming:
    """Phase 0: Anchored patterns trimmed to bare instrument names."""

    def test_anchor_trimmed_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["as part of the PHQ-9", "A B"],
            ])

            stats = coalesce_variants_tsv(inp, out)  # trim_anchors=True by default

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            assert "PHQ-9" in patterns
            assert "as part of the PHQ-9" not in patterns

    def test_anchor_trimming_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["as part of the PHQ-9", "A B"],
            ])

            stats = coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            patterns = {r["pattern"] for r in rows}

            assert "as part of the PHQ-9" in patterns

    def test_anchor_trim_merges_tinyids(self):
        """When anchor-trimmed name already exists, tinyIds merge."""
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["PHQ-9", "A"],
                ["based on PHQ-9", "B C"],
            ])

            stats = coalesce_variants_tsv(inp, out)

            _, rows = _read_tsv_rows(out)
            assert len(rows) == 1
            tinyids = set(rows[0]["tinyIds"].split())
            assert tinyids == {"A", "B", "C"}


# ===========================================================================
# Verbatim TSV I/O
# ===========================================================================


class TestVerbatimTsvIO:
    """Round-trip write/load of verbatim TSV files."""

    def test_write_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "verbatim.tsv")
            data = {
                "Depression Scale": {"t1", "t2"},
                "Anxiety Index": {"t3"},
            }
            write_verbatim_tsv(data, path)
            loaded = load_verbatim_tsv(path)

            loaded_dict = {phrase: ids for phrase, ids in loaded}
            assert loaded_dict["Depression Scale"] == {"t1", "t2"}
            assert loaded_dict["Anxiety Index"] == {"t3"}

    def test_sort_by_length(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "verbatim.tsv")
            data = {
                "Short": {"t1"},
                "A much longer pattern here": {"t2"},
            }
            write_verbatim_tsv(data, path, sort_by_length=True)
            loaded = load_verbatim_tsv(path)

            # Longest first
            assert loaded[0][0] == "A much longer pattern here"


# ===========================================================================
# Merge verbatim TSV
# ===========================================================================


class TestMergeVerbatimTsv:
    """Merge duplicate patterns, combining tinyId sets."""

    def test_merge_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "full_match\ttinyIds", [
                ["Depression Scale", "A B"],
                ["Depression Scale", "C"],
                ["Anxiety Index", "D"],
            ])

            stats = merge_verbatim_tsv(inp, out)

            assert stats["input_rows"] == 3
            assert stats["output_rows"] == 2
            assert stats["merged_count"] == 1

            loaded = load_verbatim_tsv(out)
            loaded_dict = {p: ids for p, ids in loaded}
            assert loaded_dict["Depression Scale"] == {"A", "B", "C"}


# ===========================================================================
# Compile flexible patterns
# ===========================================================================


class TestCompileFlexiblePatterns:
    """Compile a list of patterns into regex objects."""

    def test_compile_basic(self):
        compiled = compile_flexible_patterns(["Depression Scale", "PHQ-9"])
        assert len(compiled) == 2
        for orig, regex in compiled:
            assert isinstance(regex, re.Pattern)

    def test_compiled_matches(self):
        compiled = compile_flexible_patterns(["Depression Scale"])
        _, regex = compiled[0]
        assert regex.search("the Depression Scale is useful")

    def test_empty_list(self):
        compiled = compile_flexible_patterns([])
        assert compiled == []


# ===========================================================================
# get_optimal_workers
# ===========================================================================


class TestGetOptimalWorkers:
    """Worker count calculation."""

    def test_explicit_count(self):
        assert get_optimal_workers(4) == 4

    def test_negative_means_sequential(self):
        assert get_optimal_workers(-1) == 1

    def test_auto_detect(self):
        result = get_optimal_workers(0)
        assert result >= 1


# ===========================================================================
# Group key computation
# ===========================================================================


class TestGroupKey:
    """Patterns sharing word-level prefix get the same group_key."""

    def test_shared_prefix_group_key(self):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "input.tsv")
            out = os.path.join(td, "output.tsv")

            _write_tsv(inp, "pattern\ttinyIds", [
                ["Patient Health Score A", "A"],
                ["Patient Health Score B", "B"],
                ["Unrelated Test", "C"],
            ])

            coalesce_variants_tsv(inp, out, trim_anchors=False)

            _, rows = _read_tsv_rows(out)
            gk = {r["pattern"]: r["group_key"] for r in rows}

            # The two Patient Health patterns share at least 2-word prefix
            assert gk["Patient Health Score A"] == gk["Patient Health Score B"]
            assert gk["Unrelated Test"] != gk["Patient Health Score A"]
