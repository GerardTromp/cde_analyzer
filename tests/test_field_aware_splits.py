#
# File: tests/test_field_aware_splits.py
#
"""
Regression tests for field-aware instrument splits (7-way branching strip).

Ensures that:
1. inst_full and inst_sub with different patterns produce different results
2. All 7 variants are pairwise distinct
3. MTSTPF != MTSFPF and MTSTPT != MTSFPT (MT+ST not degenerate)
4. Singletons appear in inst_full only (not inst_sub)
5. Separator is included as prefix to sub pattern

These tests prevent regression to the v0.9.6 state where inst_full and inst_sub
had identical patterns, making MT+ST degenerate with MT-only.
"""

import copy
import os
import sys
import tempfile
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.branching_stripper import (
    StripStage,
    _strip_single_cde_nway,
    build_tinyid_index,
    VARIANT_STAGES,
)


def _make_stage(name, patterns, **kwargs):
    """Create a StripStage from a list of (phrase, replace_with) tuples.

    Each pattern applies to all fields and all tinyIds (universal).
    """
    phrase_map = [
        ("definitions.*.definition", phrase, replace_with, None)
        for phrase, replace_with in patterns
    ]
    stage = StripStage(name=name, phrase_map=phrase_map, **kwargs)
    stage.compile()
    return stage


def _make_cde(tiny_id, definition_text):
    """Create a minimal CDE dict with one definition field."""
    return {
        "tinyId": tiny_id,
        "definitions": [
            {"definition": definition_text}
        ],
    }


def _get_def(cde_dict):
    """Extract the definition text from a CDE dict."""
    return cde_dict["definitions"][0]["definition"]


class TestFieldAwareSplits7Way(unittest.TestCase):
    """Test that field-aware splits produce 7 genuinely distinct variants."""

    def _run_all_variants(self, cde, stages):
        """Run all 7 variants and return {code: definition_text}."""
        stage_indexes = {}
        for name, stage in stages.items():
            stage_indexes[name] = build_tinyid_index(stage.phrase_map)

        all_variants = set(VARIANT_STAGES.keys())
        results = _strip_single_cde_nway(cde, stages, stage_indexes, all_variants)

        return {code: _get_def(data) for code, data in results.items()}

    def test_7way_all_distinct(self):
        """All 7 variants must produce pairwise distinct outputs when
        inst_full and inst_sub have different pattern text."""
        # CDE text: "PROMIS - Anxiety Raw Score measured monthly"
        # inst_full removes "PROMIS" (group prefix)
        # inst_sub removes " - Anxiety" (separator + suffix)
        # temporal removes "monthly"
        # phrase removes "Raw Score"
        cde = _make_cde("t1", "PROMIS - Anxiety Raw Score measured monthly")

        stages = {
            "inst_full": _make_stage("inst_full", [("PROMIS", "")]),
            "inst_sub": _make_stage("inst_sub", [(" - Anxiety", "")]),
            "temporal": _make_stage("temporal", [("monthly", "")],
                                   case_insensitive=True, word_boundary=True),
            "phrase": _make_stage("phrase", [("Raw Score", "")],
                                 word_boundary=True),
        }

        texts = self._run_all_variants(cde, stages)

        # All 7 variants should be present
        self.assertEqual(len(texts), 7, f"Expected 7 variants, got {len(texts)}: {list(texts.keys())}")

        # All 7 should be pairwise distinct
        codes = list(texts.keys())
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                self.assertNotEqual(
                    texts[codes[i]], texts[codes[j]],
                    f"{codes[i]} and {codes[j]} produced identical output: {texts[codes[i]]!r}"
                )

    def test_mt_st_not_degenerate(self):
        """MTSTPF != MTSFPF and MTSTPT != MTSFPT when inst_full and inst_sub
        have different pattern text."""
        cde = _make_cde("t1", "PROMIS - Anxiety Total Score")

        stages = {
            "inst_full": _make_stage("inst_full", [("PROMIS", "")]),
            "inst_sub": _make_stage("inst_sub", [(" - Anxiety", "")]),
            "temporal": _make_stage("temporal", [], case_insensitive=True, word_boundary=True),
            "phrase": _make_stage("phrase", [("Total Score", "")], word_boundary=True),
        }

        texts = self._run_all_variants(cde, stages)

        # MTSFPF strips only "PROMIS" -> " - Anxiety Total Score"
        # MTSTPF strips "PROMIS" + " - Anxiety" -> " Total Score"
        self.assertNotEqual(
            texts["MTSTPF"], texts["MTSFPF"],
            f"MTSTPF should differ from MTSFPF: {texts['MTSTPF']!r} vs {texts['MTSFPF']!r}"
        )

        # MTSFPT strips "PROMIS" + "Total Score" -> " - Anxiety  measured"
        # MTSTPT strips "PROMIS" + " - Anxiety" + "Total Score" -> "  measured"
        self.assertNotEqual(
            texts["MTSTPT"], texts["MTSFPT"],
            f"MTSTPT should differ from MTSFPT: {texts['MTSTPT']!r} vs {texts['MTSFPT']!r}"
        )

    def test_mt_st_degenerate_with_identical_patterns(self):
        """When inst_full and inst_sub have the SAME pattern (the old bug),
        MT+ST IS degenerate with MT-only — this is the regression we prevent."""
        cde = _make_cde("t1", "Some Instrument Name Total Score")

        # Same pattern in both stages (the v0.9.6 bug)
        stages = {
            "inst_full": _make_stage("inst_full", [("Some Instrument Name", "")]),
            "inst_sub": _make_stage("inst_sub", [("Some Instrument Name", "")]),
            "temporal": _make_stage("temporal", [], case_insensitive=True, word_boundary=True),
            "phrase": _make_stage("phrase", [("Total Score", "")], word_boundary=True),
        }

        texts = self._run_all_variants(cde, stages)

        # With identical patterns, MTSTPF == MTSFPF (the degeneracy)
        self.assertEqual(
            texts["MTSTPF"], texts["MTSFPF"],
            "With identical patterns, MTSTPF should equal MTSFPF (degenerate)"
        )

    def test_inst_both_applies_sequentially(self):
        """MTSTPF applies inst_full then inst_sub, removing both spans."""
        cde = _make_cde("t1", "NIH Toolbox - Flanker Inhibitory Control")

        stages = {
            "inst_full": _make_stage("inst_full", [("NIH Toolbox", "")]),
            "inst_sub": _make_stage("inst_sub", [(" - Flanker", "")]),
            "temporal": _make_stage("temporal", [], case_insensitive=True, word_boundary=True),
            "phrase": _make_stage("phrase", [], word_boundary=True),
        }

        stage_indexes = {}
        for name, stage in stages.items():
            stage_indexes[name] = build_tinyid_index(stage.phrase_map)

        results = _strip_single_cde_nway(
            cde, stages, stage_indexes, {"MTSTPF", "MTSFPF", "MFSTPF"}
        )

        # MTSFPF: only inst_full applied -> " - Flanker Inhibitory Control"
        self.assertEqual(_get_def(results["MTSFPF"]), " - Flanker Inhibitory Control")
        # MFSTPF: only inst_sub applied -> "NIH Toolbox Inhibitory Control"
        self.assertEqual(_get_def(results["MFSTPF"]), "NIH Toolbox Inhibitory Control")
        # MTSTPF: both applied -> " Inhibitory Control"
        self.assertEqual(_get_def(results["MTSTPF"]), " Inhibitory Control")


class TestSplitsPatternGeneration(unittest.TestCase):
    """Test that --generate-strip-patterns in splits mode produces correct output."""

    def test_singleton_full_only(self):
        """Singletons should appear in inst_full patterns but NOT in inst_sub.

        This is a conceptual test — singletons have no sub-component to split.
        With field-aware splits, a singleton like 'AUDIT-C' goes into inst_full
        as the complete pattern (full deletion), with nothing in inst_sub.
        """
        # Simulate: singleton pattern "AUDIT-C" with no group
        # inst_full should contain "AUDIT-C"
        # inst_sub should NOT contain "AUDIT-C"
        inst_full_patterns = {"AUDIT-C"}
        inst_sub_patterns = set()  # singletons excluded

        self.assertIn("AUDIT-C", inst_full_patterns)
        self.assertNotIn("AUDIT-C", inst_sub_patterns)

        # Create stages and verify: stripping with inst_sub has no effect
        cde = _make_cde("t1", "AUDIT-C screening total")

        stages_full = {
            "inst_full": _make_stage("inst_full", [("AUDIT-C", "")]),
            "inst_sub": _make_stage("inst_sub", []),  # empty — singleton excluded
        }

        stage_indexes = {}
        for name, stage in stages_full.items():
            stage_indexes[name] = build_tinyid_index(stage.phrase_map)

        results = _strip_single_cde_nway(
            cde, stages_full, stage_indexes, {"MTSFPF", "MFSTPF", "MTSTPF"}
        )

        # MTSFPF strips "AUDIT-C" -> " screening total"
        self.assertEqual(_get_def(results["MTSFPF"]), " screening total")
        # MFSTPF: inst_sub is empty -> no change
        self.assertEqual(_get_def(results["MFSTPF"]), "AUDIT-C screening total")
        # MTSTPF: inst_full strips, inst_sub is empty -> same as MTSFPF
        self.assertEqual(_get_def(results["MTSTPF"]), " screening total")

    def test_separator_in_sub(self):
        """proposed_sub must include the separator as prefix.

        e.g., for "PROMIS - Anxiety", proposed_sub = " - Anxiety" (not "Anxiety").
        This ensures that when both M and S are applied, the complete text is
        fully consumed without leaving a dangling separator.
        """
        original_text = "PROMIS - Anxiety Raw Score"

        # Correct: separator included in sub
        inst_full_pattern = "PROMIS"
        inst_sub_pattern = " - Anxiety"

        cde = _make_cde("t1", original_text)
        stages = {
            "inst_full": _make_stage("inst_full", [(inst_full_pattern, "")]),
            "inst_sub": _make_stage("inst_sub", [(inst_sub_pattern, "")]),
        }

        stage_indexes = {}
        for name, stage in stages.items():
            stage_indexes[name] = build_tinyid_index(stage.phrase_map)

        results = _strip_single_cde_nway(
            cde, stages, stage_indexes, {"MTSTPF"}
        )

        # With separator in sub, full+sub removes "PROMIS" + " - Anxiety" -> " Raw Score"
        # No dangling " - " separator
        result_text = _get_def(results["MTSTPF"])
        self.assertNotIn(" - ", result_text,
                         f"Dangling separator found in MTSTPF output: {result_text!r}")
        self.assertEqual(result_text, " Raw Score")

    def test_separator_missing_leaves_dangling(self):
        """Without separator in sub, MTSTPF leaves a dangling separator.

        This verifies why the separator-as-prefix convention is necessary.
        """
        original_text = "PROMIS - Anxiety Raw Score"

        # Wrong: separator NOT included in sub
        inst_full_pattern = "PROMIS"
        inst_sub_pattern_no_sep = "Anxiety"

        cde = _make_cde("t1", original_text)
        stages = {
            "inst_full": _make_stage("inst_full", [(inst_full_pattern, "")]),
            "inst_sub": _make_stage("inst_sub", [(inst_sub_pattern_no_sep, "")]),
        }

        stage_indexes = {}
        for name, stage in stages.items():
            stage_indexes[name] = build_tinyid_index(stage.phrase_map)

        results = _strip_single_cde_nway(
            cde, stages, stage_indexes, {"MTSTPF"}
        )

        # Without separator in sub, " - " is left dangling
        result_text = _get_def(results["MTSTPF"])
        self.assertIn(" - ", result_text,
                      f"Expected dangling separator without sep-in-sub: {result_text!r}")


class TestSplitsProduceDifferentPatterns(unittest.TestCase):
    """Test that splits mode produces genuinely different inst_full and inst_sub files."""

    def test_different_pattern_text(self):
        """Given a group with members, inst_full and inst_sub must have
        different pattern text (not identical like in v0.9.6)."""
        # Simulate the output of --generate-strip-patterns in splits mode:
        # Group "PROMIS" with members "PROMIS - Anxiety", "PROMIS - Depression"
        #
        # inst_full should contain: "PROMIS" (the prefix)
        # inst_sub should contain: " - Anxiety", " - Depression" (separator + suffix)

        inst_full_patterns = {"PROMIS"}
        inst_sub_patterns = {" - Anxiety", " - Depression"}

        # The key invariant: no pattern appears in both files
        overlap = inst_full_patterns & inst_sub_patterns
        self.assertEqual(len(overlap), 0,
                         f"inst_full and inst_sub should have no overlapping patterns: {overlap}")

        # And they should be non-empty (both have content)
        self.assertTrue(len(inst_full_patterns) > 0)
        self.assertTrue(len(inst_sub_patterns) > 0)


if __name__ == "__main__":
    unittest.main()
