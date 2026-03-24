"""Tests for verbatim coalescing functionality."""

import pytest
from utils.verbatim_coalesce import (
    find_overlap,
    merge_two_strings,
    coalesce_fragments,
    coalesce_verbatim_groups
)


class TestFindOverlap:
    """Tests for find_overlap function."""

    def test_no_overlap(self):
        assert find_overlap("hello", "world") is None

    def test_exact_overlap(self):
        # "hello world" suffix "world" matches "world peace" prefix "world"
        assert find_overlap("hello world", "world peace", min_overlap=5) == 5

    def test_partial_overlap(self):
        # "abc def ghi" suffix "def ghi" matches "def ghi jkl" prefix
        assert find_overlap("abc def ghi", "def ghi jkl", min_overlap=5) == 7

    def test_min_overlap_threshold(self):
        # Short overlap should be rejected
        assert find_overlap("hello", "lo world", min_overlap=5) is None
        assert find_overlap("hello", "lo world", min_overlap=2) == 2


class TestMergeTwoStrings:
    """Tests for merge_two_strings function."""

    def test_simple_merge(self):
        result = merge_two_strings(
            "harmful and usually subject to legal",
            "subject to legal restriction), or over",
            min_overlap=10
        )
        assert result == "harmful and usually subject to legal restriction), or over"

    def test_reverse_order_merge(self):
        # Should work regardless of argument order
        result = merge_two_strings(
            "subject to legal restriction), or over",
            "harmful and usually subject to legal",
            min_overlap=10
        )
        assert result == "harmful and usually subject to legal restriction), or over"

    def test_no_overlap_returns_none(self):
        result = merge_two_strings("hello world", "goodbye moon", min_overlap=5)
        assert result is None


class TestCoalesceFragments:
    """Tests for coalesce_fragments function."""

    def test_empty_list(self):
        assert coalesce_fragments([]) == []

    def test_single_fragment(self):
        assert coalesce_fragments(["hello"]) == ["hello"]

    def test_non_overlapping_fragments(self):
        result = coalesce_fragments(["hello world", "goodbye moon"], min_overlap=5)
        assert len(result) == 2
        assert "hello world" in result
        assert "goodbye moon" in result

    def test_phrase_07389_style_fragments(self):
        """Test with fragments similar to phrase_07389 problem."""
        fragments = [
            "harmful and usually subject to legal restriction), or over-the-counter",
            "and usually subject to legal restriction), or over-the-counter drugs",
            "usually subject to legal restriction), or over-the-counter drugs (medicine",
        ]
        result = coalesce_fragments(fragments, min_overlap=10)

        # Should coalesce into a single string
        assert len(result) == 1
        merged = result[0]

        # The merged string should contain all unique content
        assert "harmful" in merged
        assert "(medicine" in merged


class TestCoalesceVerbatimGroups:
    """Tests for coalesce_verbatim_groups function."""

    def test_single_fragment_unchanged(self):
        groups = {
            "hello world": {"count": 5, "tinyids": {"A", "B"}}
        }
        result = coalesce_verbatim_groups(groups)
        assert len(result) == 1
        assert "hello world" in result

    def test_different_tinyid_sets_not_merged(self):
        """Fragments with different tinyId sets should not be merged."""
        groups = {
            "fragment one here": {"count": 3, "tinyids": {"A", "B"}},
            "one here plus more": {"count": 2, "tinyids": {"C", "D"}},
        }
        result = coalesce_verbatim_groups(groups, min_overlap=5)

        # Different tinyId sets -> no merging
        assert len(result) == 2

    def test_same_tinyid_sets_merged(self):
        """Fragments with same tinyId set should be merged if overlapping."""
        tinyids = {"71hVkLVkyx", "7JeWTQE1yx", "QJ8x6T71Je"}
        groups = {
            "harmful and usually subject to legal restriction": {
                "count": 9,
                "tinyids": tinyids.copy()
            },
            "usually subject to legal restriction), or over-the-counter": {
                "count": 9,
                "tinyids": tinyids.copy()
            },
        }
        result = coalesce_verbatim_groups(groups, min_overlap=10)

        # Same tinyId set + overlapping -> should merge
        assert len(result) == 1

    def test_counts_aggregated(self):
        """Merged fragments should have aggregated counts."""
        tinyids = {"A", "B"}
        groups = {
            "the quick brown fox": {"count": 5, "tinyids": tinyids.copy()},
            "brown fox jumps over": {"count": 3, "tinyids": tinyids.copy()},
        }
        result = coalesce_verbatim_groups(groups, min_overlap=5)

        # Should merge and aggregate counts
        assert len(result) == 1
        merged_key = list(result.keys())[0]
        assert result[merged_key]["count"] == 8  # 5 + 3


class TestPhrase07389Integration:
    """Integration test simulating the phrase_07389 scenario."""

    def test_sliding_window_coalescing(self):
        """
        Simulate the phrase_07389 problem: multiple sliding window extractions
        from the same source text with the same tinyId set.
        """
        tinyids = {
            "71hVkLVkyx", "7JeWTQE1yx", "QJ8x6T71Je", "QJ9KFOQkJe",
            "QJV8wSQyyx", "QkVxztmQJ1g", "XylxyiaQk1e", "mkgGuTXykg", "mygNCBVykl"
        }

        # Simplified version of the phrase_07389 fragments
        groups = {
            "that may lead to social, occupational, psychological, or physical problems": {
                "count": 9, "tinyids": tinyids.copy()
            },
            "may lead to social, occupational, psychological, or physical problems as": {
                "count": 9, "tinyids": tinyids.copy()
            },
            "lead to social, occupational, psychological, or physical problems as part": {
                "count": 9, "tinyids": tinyids.copy()
            },
            "to social, occupational, psychological, or physical problems as part of": {
                "count": 9, "tinyids": tinyids.copy()
            },
        }

        result = coalesce_verbatim_groups(groups, min_overlap=10)

        # All fragments share the same tinyId set and overlap
        # Should coalesce into a single string
        assert len(result) == 1

        merged = list(result.keys())[0]
        # Merged string should contain the full extent
        assert "that may lead to" in merged
        assert "as part of" in merged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
