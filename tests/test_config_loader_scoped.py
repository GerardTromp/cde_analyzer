"""Tests for tinyId-scoped verbatim strip pattern loading.

Tests the config_loader extensions:
- _parse_tinyid_field: parses tinyId strings
- _extract_verbatim_patterns_from_config: returns 3-tuples with tinyIds
- _auto_propagate_bare_patterns: bracketed [TAG] -> bare TAG propagation
- load_verbatim_strip_patterns: end-to-end with scoping
"""

import pytest
from utils.config_loader import (
    _parse_tinyid_field,
    _extract_verbatim_patterns_from_config,
    _auto_propagate_bare_patterns,
)


# ── _parse_tinyid_field ────────────────────────────────────────────────

class TestParseTinyidField:
    def test_none_returns_none(self):
        assert _parse_tinyid_field(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_tinyid_field("") is None

    def test_whitespace_only_returns_none(self):
        assert _parse_tinyid_field("   ") is None

    def test_single_id(self):
        assert _parse_tinyid_field("abc123") == {"abc123"}

    def test_space_delimited(self):
        result = _parse_tinyid_field("abc def ghi")
        assert result == {"abc", "def", "ghi"}

    def test_comma_delimited(self):
        result = _parse_tinyid_field("abc,def,ghi")
        assert result == {"abc", "def", "ghi"}

    def test_pipe_delimited(self):
        result = _parse_tinyid_field("abc|def|ghi")
        assert result == {"abc", "def", "ghi"}

    def test_mixed_delimiters(self):
        result = _parse_tinyid_field("abc,def ghi|jkl")
        assert result == {"abc", "def", "ghi", "jkl"}

    def test_deduplicates(self):
        result = _parse_tinyid_field("abc abc def abc")
        assert result == {"abc", "def"}


# ── _extract_verbatim_patterns_from_config ─────────────────────────────

class TestExtractVerbatimPatternsFromConfig:
    def test_basic_pattern_no_tinyids(self):
        config = {
            "instruments": [
                {"pattern": "[PhenX]"},
            ]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        assert len(result) == 1
        assert result[0] == ("[PhenX]", "", None)

    def test_pattern_with_tinyids(self):
        config = {
            "scoped": [
                {"pattern": "UPPS-P", "tinyIds": "tid1 tid2 tid3"},
            ]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        assert len(result) == 1
        pat, replace, tinyids = result[0]
        assert pat == "UPPS-P"
        assert replace == ""
        assert tinyids == {"tid1", "tid2", "tid3"}

    def test_pattern_with_replace_and_tinyids(self):
        config = {
            "substitutions": [
                {"pattern": "PROMIS", "replace_with": "", "tinyIds": "a b"},
            ]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        pat, replace, tinyids = result[0]
        assert pat == "PROMIS"
        assert replace == ""
        assert tinyids == {"a", "b"}

    def test_mixed_scoped_and_universal(self):
        config = {
            "tags": [
                {"pattern": "[PhenX]"},
                {"pattern": "UPPS-P", "tinyIds": "tid1"},
                {"pattern": "[LTVH]"},
            ]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        assert len(result) == 3
        assert result[0][2] is None    # [PhenX] universal
        assert result[1][2] == {"tid1"}  # UPPS-P scoped
        assert result[2][2] is None    # [LTVH] universal

    def test_empty_tinyids_treated_as_universal(self):
        config = {
            "tags": [
                {"pattern": "BMI", "tinyIds": ""},
            ]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        assert result[0][2] is None  # empty string -> None (universal)

    def test_skips_non_dict_items(self):
        config = {
            "tags": ["just a string", {"pattern": "OK"}]
        }
        result = _extract_verbatim_patterns_from_config(config, "test")
        assert len(result) == 1
        assert result[0][0] == "OK"


# ── _auto_propagate_bare_patterns ──────────────────────────────────────

class TestAutoPropagateBarePatterns:
    def test_bracketed_with_tinyids_creates_bare(self):
        patterns = [
            ("[UPPS-P]", "", {"tid1", "tid2"}),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 2
        # Original
        assert result[0][0] == "[UPPS-P]"
        # Propagated bare
        assert result[1][0] == "UPPS-P"
        assert result[1][2] == {"tid1", "tid2"}

    def test_bracketed_without_tinyids_no_propagation(self):
        patterns = [
            ("[PhenX]", "", None),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 1  # No bare added

    def test_bare_already_exists_universal_not_downgraded(self):
        patterns = [
            ("[UPPS-P]", "", {"tid1"}),
            ("UPPS-P", "", None),  # Already universal
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 2  # No new entry
        # The bare pattern stays universal
        assert result[1][2] is None

    def test_bare_already_exists_scoped_gets_union(self):
        patterns = [
            ("[UPPS-P]", "", {"tid1", "tid2"}),
            ("UPPS-P", "", {"tid3"}),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 2  # No new entry, existing updated
        assert result[1][2] == {"tid1", "tid2", "tid3"}

    def test_multiple_bracketed_sources_union(self):
        patterns = [
            ("[TAG]", "", {"a", "b"}),
            ("TAG", "", {"c"}),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert result[1][2] == {"a", "b", "c"}

    def test_no_propagation_for_non_bracketed(self):
        patterns = [
            ("PROMIS", "", {"tid1"}),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 1  # No change

    def test_replace_with_preserved(self):
        patterns = [
            ("[TAG]", "replacement", {"tid1"}),
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert result[1][1] == "replacement"

    def test_mixed_scenario(self):
        """Multiple bracketed and bare patterns in realistic config."""
        patterns = [
            ("[PhenX]", "", None),        # Universal bracketed, no propagation
            ("[UPPS-P]", "", {"t1"}),      # Scoped bracketed, should propagate
            ("[LTVH]", "", {"t2", "t3"}),  # Scoped bracketed, should propagate
            ("PROMIS", "", {"t4"}),         # Already bare scoped
        ]
        result = _auto_propagate_bare_patterns(patterns)
        assert len(result) == 6  # 4 original + 2 propagated (UPPS-P, LTVH)
        bare_names = [p[0] for p in result[4:]]
        assert "UPPS-P" in bare_names
        assert "LTVH" in bare_names
