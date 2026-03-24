#
# File: tests/test_remnant_detector.py
#
"""Tests for logic/remnant_detector.py — post-strip artifact detection."""

import os
import tempfile
import unittest

from logic.remnant_detector import (
    Remnant,
    detect_remnants_from_json,
    summarize_remnants,
    affected_records,
    write_remnant_report,
    _scan_text,
)


class TestScanText(unittest.TestCase):
    """Unit tests for individual remnant pattern matching."""

    def test_trailing_article(self):
        hits = _scan_text("Score from the")
        types = [h[0] for h in hits]
        self.assertIn("trailing_article", types)

    def test_orphan_article_before_punct(self):
        hits = _scan_text("Total score the,")
        types = [h[0] for h in hits]
        self.assertIn("orphan_article", types)

    def test_leading_article_punct(self):
        hits = _scan_text("the, raw score")
        types = [h[0] for h in hits]
        self.assertIn("leading_article", types)

    def test_floating_punct(self):
        hits = _scan_text("Score , total")
        types = [h[0] for h in hits]
        self.assertIn("floating_punct", types)

    def test_excess_whitespace(self):
        hits = _scan_text("Score  total")
        types = [h[0] for h in hits]
        self.assertIn("excess_whitespace", types)

    def test_empty_parens(self):
        hits = _scan_text("Score () total")
        types = [h[0] for h in hits]
        self.assertIn("empty_parens", types)

    def test_empty_brackets(self):
        hits = _scan_text("Score [] total")
        types = [h[0] for h in hits]
        self.assertIn("empty_brackets", types)

    def test_leading_punct(self):
        hits = _scan_text(", raw score")
        types = [h[0] for h in hits]
        self.assertIn("leading_punct", types)

    def test_orphan_preposition(self):
        hits = _scan_text("Amount of.")
        types = [h[0] for h in hits]
        self.assertIn("orphan_preposition", types)

    def test_double_punct(self):
        hits = _scan_text("Score,, total")
        types = [h[0] for h in hits]
        self.assertIn("double_punct", types)

    def test_trailing_punct_space(self):
        hits = _scan_text("Score .")
        types = [h[0] for h in hits]
        self.assertIn("trailing_punct_space", types)

    def test_clean_text_no_remnants(self):
        """Normal text should produce no hits (or minimal false positives)."""
        hits = _scan_text("The patient reported a score of 5 on the pain scale.")
        # The leading "The" at start of sentence is legitimate, not a remnant.
        # We only flag trailing/orphan articles, not sentence-initial ones.
        orphan_types = {"orphan_article", "trailing_article", "leading_article",
                        "floating_punct", "empty_parens", "empty_brackets",
                        "leading_punct", "orphan_preposition", "double_punct"}
        flagged = [h for h in hits if h[0] in orphan_types]
        # Normal prose should have very few if any of these
        self.assertLessEqual(len(flagged), 1, f"Too many false positives: {flagged}")

    def test_dangling_s(self):
        hits = _scan_text("The patient's")
        types = [h[0] for h in hits]
        # This is a legitimate possessive — the pattern requires non-alpha before 's
        # "patient's" has 't' before apostrophe, so should NOT match
        self.assertNotIn("dangling_s", types)

    def test_dangling_s_after_space(self):
        hits = _scan_text("CES-D  's response")
        types = [h[0] for h in hits]
        self.assertIn("dangling_s", types)


class TestDetectRemnants(unittest.TestCase):
    """Integration tests for detect_remnants_from_json."""

    def _make_record(self, tinyId, definition="", designation=""):
        return {
            "tinyId": tinyId,
            "definitions": [{"definition": definition}] if definition else [],
            "designations": [{"designation": designation}] if designation else [],
        }

    def test_finds_remnants_in_definition(self):
        records = [self._make_record("t1", definition="Score from the")]
        remnants = detect_remnants_from_json(records)
        self.assertTrue(len(remnants) > 0)
        self.assertEqual(remnants[0].tinyId, "t1")

    def test_finds_remnants_in_designation(self):
        records = [self._make_record("t2", designation="Total , score")]
        remnants = detect_remnants_from_json(records)
        types = [r.remnant_type for r in remnants]
        self.assertIn("floating_punct", types)

    def test_clean_record_no_remnants(self):
        records = [self._make_record("t3", definition="Normal definition text")]
        remnants = detect_remnants_from_json(records)
        self.assertEqual(len(remnants), 0)

    def test_multiple_remnants_one_record(self):
        records = [self._make_record("t4", definition="the, Score () from the")]
        remnants = detect_remnants_from_json(records)
        types = set(r.remnant_type for r in remnants)
        self.assertTrue(len(types) >= 2, f"Expected multiple types, got {types}")

    def test_custom_field_paths(self):
        records = [{"tinyId": "t5", "name": "Score from the"}]
        remnants = detect_remnants_from_json(records, field_paths=["name"])
        self.assertTrue(len(remnants) > 0)


class TestSummarize(unittest.TestCase):

    def test_summarize(self):
        remnants = [
            Remnant("t1", "f", "orphan_article", "the,", 0),
            Remnant("t2", "f", "orphan_article", "a.", 0),
            Remnant("t3", "f", "excess_whitespace", "  ", 0),
        ]
        summary = summarize_remnants(remnants)
        self.assertEqual(summary["orphan_article"], 2)
        self.assertEqual(summary["excess_whitespace"], 1)

    def test_affected_records(self):
        remnants = [
            Remnant("t1", "f", "a", "x", 0),
            Remnant("t1", "f", "b", "y", 0),
            Remnant("t2", "f", "a", "x", 0),
        ]
        self.assertEqual(affected_records(remnants), 2)


class TestWriteReport(unittest.TestCase):

    def test_write_and_read(self):
        remnants = [
            Remnant("t1", "definitions.0.definition", "orphan_article", "the,", 5),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False) as f:
            path = f.name

        try:
            write_remnant_report(remnants, path)
            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2)  # header + 1 row
            self.assertIn("orphan_article", lines[1])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
