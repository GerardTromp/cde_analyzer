"""Tests for logic/abbreviation_dictionary.py."""
import csv
import tempfile
import unittest
from pathlib import Path

from logic.abbreviation_dictionary import (
    AbbreviationDictionary,
    AbbreviationEntry,
    DICTIONARY_TSV_HEADERS,
    acronym_align,
)


class TestAbbreviationEntry(unittest.TestCase):
    """Test AbbreviationEntry defaults."""

    def test_defaults(self):
        e = AbbreviationEntry(abbreviation="PHQ")
        self.assertEqual(e.abbreviation, "PHQ")
        self.assertEqual(e.expansion, "")
        self.assertEqual(e.category, "unknown")
        self.assertEqual(e.confidence, 0.0)
        self.assertEqual(e.tinyIds, set())


class TestDictionaryRoundTrip(unittest.TestCase):
    """Test TSV save/load round-trip."""

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.tsv")
            d = AbbreviationDictionary(path)
            d.entries["PHQ"] = AbbreviationEntry(
                abbreviation="PHQ",
                expansion="Patient Health Questionnaire",
                category="instrument",
                confidence=0.95,
                source="parenthetical",
                tinyIds={"tid1", "tid2"},
                n_tinyIds=2,
                aliases="PHQ-9|PHQ-2",
                decided_at="2026-04-01",
                notes="test note",
            )
            d.entries["[BFI]"] = AbbreviationEntry(
                abbreviation="[BFI]",
                expansion="Big Five Inventory",
                category="instrument",
                confidence=0.85,
                source="bracketed",
                tinyIds={"tid3"},
                n_tinyIds=1,
            )
            d.save()

            d2 = AbbreviationDictionary(path)
            self.assertTrue(d2.load())
            self.assertEqual(len(d2.entries), 2)
            self.assertEqual(d2.entries["PHQ"].expansion, "Patient Health Questionnaire")
            self.assertEqual(d2.entries["PHQ"].confidence, 0.95)
            self.assertEqual(d2.entries["PHQ"].tinyIds, {"tid1", "tid2"})
            self.assertEqual(d2.entries["PHQ"].aliases, "PHQ-9|PHQ-2")
            self.assertEqual(d2.entries["[BFI]"].category, "instrument")

    def test_load_nonexistent(self):
        d = AbbreviationDictionary("/nonexistent/path.tsv")
        self.assertFalse(d.load())
        self.assertEqual(len(d.entries), 0)

    def test_empty_dictionary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "empty.tsv")
            d = AbbreviationDictionary(path)
            d.save()
            d2 = AbbreviationDictionary(path)
            self.assertTrue(d2.load())
            self.assertEqual(len(d2.entries), 0)


class TestDiscoverParenthetical(unittest.TestCase):
    """Test parenthetical abbreviation discovery."""

    def _make_data(self, defs):
        """Helper to create CDE-like records."""
        return [
            {"tinyId": f"tid{i}", "definitions": [{"definition": d}], "designations": []}
            for i, d in enumerate(defs)
        ]

    def test_basic_expansion(self):
        data = self._make_data([
            "The Patient Health Questionnaire (PHQ) is a self-report measure.",
            "NIH Stroke Scale (NIHSS) assessment.",
        ])
        d = AbbreviationDictionary()
        n = d.discover_parenthetical(data)
        self.assertEqual(n, 2)
        self.assertIn("PHQ", d.entries)
        self.assertIn("NIHSS", d.entries)
        self.assertEqual(d.entries["PHQ"].expansion, "Patient Health Questionnaire")
        self.assertEqual(d.entries["NIHSS"].expansion, "NIH Stroke Scale")
        self.assertEqual(d.entries["PHQ"].source, "parenthetical")
        self.assertAlmostEqual(d.entries["PHQ"].confidence, 0.95)

    def test_tinyid_accumulation(self):
        data = self._make_data([
            "Patient Health Questionnaire (PHQ) score.",
            "Patient Health Questionnaire (PHQ) result.",
        ])
        d = AbbreviationDictionary()
        d.discover_parenthetical(data)
        self.assertEqual(d.entries["PHQ"].n_tinyIds, 2)

    def test_hyphenated_acronym(self):
        data = self._make_data([
            "Unified Parkinsons Disease Rating Scale (MDS-UPDRS) motor.",
        ])
        d = AbbreviationDictionary()
        d.discover_parenthetical(data)
        self.assertIn("MDS-UPDRS", d.entries)

    def test_ignores_short(self):
        data = self._make_data(["Something (X) small."])
        d = AbbreviationDictionary()
        n = d.discover_parenthetical(data)
        self.assertEqual(n, 0)


class TestDiscoverBracketed(unittest.TestCase):
    """Test bracketed tag discovery."""

    def test_basic_tag(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "Felt angry when in pain [LTVH]"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bracketed(data)
        self.assertEqual(n, 1)
        self.assertIn("[LTVH]", d.entries)
        self.assertEqual(d.entries["[LTVH]"].source, "bracketed")

    def test_filters_unit_tags(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "Glucose [Moles/volume] in Serum"},
                {"designation": "Active imagination [BFI]"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bracketed(data)
        self.assertEqual(n, 1)
        self.assertIn("[BFI]", d.entries)
        self.assertNotIn("[Moles/volume]", d.entries)


class TestDiscoverBareCaps(unittest.TestCase):
    """Test bare ALL-CAPS discovery."""

    def test_trailing_caps(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "Arising from chair UPDRS"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bare_caps(data)
        self.assertEqual(n, 1)
        self.assertIn("UPDRS", d.entries)
        self.assertEqual(d.entries["UPDRS"].confidence, 0.5)

    def test_filters_english(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "Test result THE"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bare_caps(data, english_words={"the"})
        self.assertEqual(n, 0)


class TestExpandFromContext(unittest.TestCase):
    """Test context-based expansion."""

    def test_cross_field_expansion(self):
        data = [
            {"tinyId": "t1", "definitions": [
                {"definition": "Score on the Big Five Inventory (BFI)."},
            ], "designations": [
                {"designation": "Active imagination [BFI]"},
            ]},
        ]
        d = AbbreviationDictionary()
        d.entries["[BFI]"] = AbbreviationEntry(
            abbreviation="[BFI]", source="bracketed", tinyIds={"t1"}, n_tinyIds=1,
        )
        n = d.expand_from_context(data)
        self.assertEqual(n, 1)
        self.assertEqual(d.entries["[BFI]"].expansion, "Big Five Inventory")


class TestClassifyByHeuristic(unittest.TestCase):
    """Test heuristic classification."""

    def test_instrument_words(self):
        d = AbbreviationDictionary()
        d.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", expansion="Patient Health Questionnaire",
        )
        n = d.classify_by_heuristic()
        self.assertEqual(n, 1)
        self.assertEqual(d.entries["PHQ"].category, "instrument")

    def test_study_words(self):
        d = AbbreviationDictionary()
        d.entries["PLCO"] = AbbreviationEntry(
            abbreviation="PLCO", expansion="Prostate Lung Colorectal Ovarian Cancer Trial",
        )
        n = d.classify_by_heuristic()
        self.assertEqual(n, 1)
        self.assertEqual(d.entries["PLCO"].category, "study")

    def test_no_expansion_stays_unknown(self):
        d = AbbreviationDictionary()
        d.entries["XYZ"] = AbbreviationEntry(abbreviation="XYZ")
        n = d.classify_by_heuristic()
        self.assertEqual(n, 0)
        self.assertEqual(d.entries["XYZ"].category, "unknown")


class TestMerge(unittest.TestCase):
    """Test dictionary merge."""

    def test_merge_adds_new(self):
        base = AbbreviationDictionary()
        base.entries["PHQ"] = AbbreviationEntry(abbreviation="PHQ", decided_at="2026-01-01")
        update = AbbreviationDictionary()
        update.entries["BFI"] = AbbreviationEntry(abbreviation="BFI", decided_at="2026-01-02")
        counts = base.merge(update)
        self.assertEqual(counts["added"], 1)
        self.assertEqual(len(base.entries), 2)

    def test_merge_updates_newer(self):
        base = AbbreviationDictionary()
        base.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", category="unknown", decided_at="2026-01-01",
        )
        update = AbbreviationDictionary()
        update.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", category="instrument", decided_at="2026-01-02",
        )
        counts = base.merge(update)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(base.entries["PHQ"].category, "instrument")

    def test_merge_keeps_newer_base(self):
        base = AbbreviationDictionary()
        base.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", category="instrument", decided_at="2026-01-02",
        )
        update = AbbreviationDictionary()
        update.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", category="unknown", decided_at="2026-01-01",
        )
        counts = base.merge(update)
        self.assertEqual(counts["unchanged"], 1)
        self.assertEqual(base.entries["PHQ"].category, "instrument")


class TestExport(unittest.TestCase):
    """Test export functions."""

    def test_export_strip_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.yaml")
            d = AbbreviationDictionary()
            d.entries["[BFI]"] = AbbreviationEntry(
                abbreviation="[BFI]", expansion="Big Five Inventory",
                category="instrument", confidence=0.9,
                tinyIds={"t1", "t2"}, n_tinyIds=2,
            )
            d.entries["XYZ"] = AbbreviationEntry(
                abbreviation="XYZ", category="unknown",
            )
            n = d.export_strip_patterns(path, ["instrument"])
            self.assertEqual(n, 1)
            content = Path(path).read_text()
            self.assertIn("[BFI]", content)
            self.assertNotIn("XYZ", content)

    def test_export_scoped_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "scoped.tsv")
            d = AbbreviationDictionary()
            d.entries["UPDRS"] = AbbreviationEntry(
                abbreviation="UPDRS", category="instrument",
                tinyIds={"t1", "t2"}, n_tinyIds=2,
            )
            d.entries["[BFI]"] = AbbreviationEntry(
                abbreviation="[BFI]", category="instrument",
                tinyIds={"t3"}, n_tinyIds=1,
            )
            n = d.export_scoped_patterns(path, ["instrument"])
            self.assertEqual(n, 1)  # Only bare UPDRS, not bracketed [BFI]
            with open(path) as f:
                rows = list(csv.DictReader(f, delimiter="\t"))
            self.assertEqual(rows[0]["pattern"], "UPDRS")


class TestSummary(unittest.TestCase):
    """Test summary statistics."""

    def test_summary_counts(self):
        d = AbbreviationDictionary()
        d.entries["A"] = AbbreviationEntry(abbreviation="A", category="instrument")
        d.entries["B"] = AbbreviationEntry(abbreviation="B", category="instrument")
        d.entries["C"] = AbbreviationEntry(abbreviation="C", category="study")
        d.entries["D"] = AbbreviationEntry(abbreviation="D", category="unknown")
        summary = d.summary()
        self.assertEqual(summary["instrument"], 2)
        self.assertEqual(summary["study"], 1)
        self.assertEqual(summary["unknown"], 1)


# ---- v1.4.0 tests ----

class TestAcronymAlign(unittest.TestCase):
    """Test acronym-alignment heuristic."""

    def test_basic_alignment(self):
        result = acronym_align("Patient Health Questionnaire", "PHQ")
        self.assertEqual(result, "Patient Health Questionnaire")

    def test_trims_preamble(self):
        result = acronym_align(
            "following protocol was taken from the "
            "Coronary Artery Risk Development in Young Adults",
            "CARDIA",
        )
        self.assertEqual(result, "Coronary Artery Risk Development in Young Adults")

    def test_hyphenated_segments(self):
        result = acronym_align("Epstein-Barr Virus", "EBV")
        self.assertEqual(result, "Epstein-Barr Virus")

    def test_filler_words_skipped(self):
        result = acronym_align(
            "Screen for Child Anxiety Related Disorders", "SCARED",
        )
        self.assertEqual(result, "Screen for Child Anxiety Related Disorders")

    def test_partial_match_fallback(self):
        # If alignment fails, return original text
        result = acronym_align("Completely Unrelated Text", "XYZ")
        self.assertEqual(result, "Completely Unrelated Text")

    def test_single_word(self):
        result = acronym_align("Electroencephalography", "EEG")
        # Can't fully align EEG to one word — fallback
        self.assertEqual(result, "Electroencephalography")


class TestAllCapsFieldDetection(unittest.TestCase):
    """Test that all-caps multi-token fields are skipped in bare-caps discovery."""

    def test_all_caps_multi_token_skipped(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "PHYSICAL EXAM FINDINGS DETAILS"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bare_caps(data)
        self.assertEqual(n, 0)

    def test_single_caps_token_kept(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "MRN"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bare_caps(data)
        self.assertEqual(n, 1)
        self.assertIn("MRN", d.entries)

    def test_mixed_case_with_trailing_caps_kept(self):
        data = [
            {"tinyId": "t1", "definitions": [], "designations": [
                {"designation": "Arising from chair UPDRS"},
            ]},
        ]
        d = AbbreviationDictionary()
        n = d.discover_bare_caps(data)
        self.assertEqual(n, 1)


class TestKFoldReEvaluation(unittest.TestCase):
    """Test k-fold tinyId growth triggers re-evaluation of skip decisions."""

    def test_skip_flagged_on_growth(self):
        base = AbbreviationDictionary()
        base.entries["XYZ"] = AbbreviationEntry(
            abbreviation="XYZ", category="unknown", decision="skip",
            decided_at="2026-01-01", tinyIds={"t1", "t2"}, n_tinyIds=2,
        )
        update = AbbreviationDictionary()
        update.entries["XYZ"] = AbbreviationEntry(
            abbreviation="XYZ", decided_at="2025-12-01",  # older
            tinyIds={"t1", "t2", "t3", "t4", "t5", "t6"}, n_tinyIds=6,
        )
        counts = base.merge(update, growth_factor=3.0)
        self.assertEqual(counts["flagged_for_review"], 1)
        self.assertEqual(base.entries["XYZ"].decision, "tentative_skip")
        self.assertIn("FLAGGED", base.entries["XYZ"].notes)

    def test_skip_not_flagged_below_threshold(self):
        base = AbbreviationDictionary()
        base.entries["XYZ"] = AbbreviationEntry(
            abbreviation="XYZ", decision="skip",
            decided_at="2026-01-01", tinyIds={"t1", "t2"}, n_tinyIds=2,
        )
        update = AbbreviationDictionary()
        update.entries["XYZ"] = AbbreviationEntry(
            abbreviation="XYZ", decided_at="2025-12-01",
            tinyIds={"t1", "t2", "t3", "t4", "t5"}, n_tinyIds=5,
        )
        counts = base.merge(update, growth_factor=3.0)
        self.assertEqual(counts["flagged_for_review"], 0)
        self.assertEqual(base.entries["XYZ"].decision, "skip")

    def test_permanent_skip_exempt(self):
        base = AbbreviationDictionary()
        base.entries["BMI"] = AbbreviationEntry(
            abbreviation="BMI", decision="skip",
            decided_at="2026-01-01", tinyIds={"t1"}, n_tinyIds=1,
        )
        update = AbbreviationDictionary()
        update.entries["BMI"] = AbbreviationEntry(
            abbreviation="BMI", decided_at="2025-12-01",
            tinyIds={"t1", "t2", "t3", "t4", "t5"}, n_tinyIds=5,
        )
        counts = base.merge(update, growth_factor=3.0,
                            permanent_skips={"BMI"})
        self.assertEqual(counts["flagged_for_review"], 0)
        self.assertEqual(base.entries["BMI"].decision, "skip")

    def test_strip_decision_not_flagged(self):
        base = AbbreviationDictionary()
        base.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", decision="strip",
            decided_at="2026-01-01", tinyIds={"t1"}, n_tinyIds=1,
        )
        update = AbbreviationDictionary()
        update.entries["PHQ"] = AbbreviationEntry(
            abbreviation="PHQ", decided_at="2025-12-01",
            tinyIds={"t1", "t2", "t3", "t4"}, n_tinyIds=4,
        )
        counts = base.merge(update, growth_factor=3.0)
        self.assertEqual(counts["flagged_for_review"], 0)


class TestDecisionRoundTrip(unittest.TestCase):
    """Test decision field persists through save/load."""

    def test_decision_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.tsv")
            d = AbbreviationDictionary(path)
            d.entries["PHQ"] = AbbreviationEntry(
                abbreviation="PHQ", category="instrument",
                decision="strip", decided_at="2026-04-01",
            )
            d.entries["BMI"] = AbbreviationEntry(
                abbreviation="BMI", category="medical_term",
                decision="skip", decided_at="2026-04-01",
            )
            d.save()

            d2 = AbbreviationDictionary(path)
            d2.load()
            self.assertEqual(d2.entries["PHQ"].decision, "strip")
            self.assertEqual(d2.entries["BMI"].decision, "skip")

    def test_tentative_auto_fill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.tsv")
            d = AbbreviationDictionary(path)
            d.entries["PHQ"] = AbbreviationEntry(
                abbreviation="PHQ", category="instrument",
                # no decision set
            )
            d.save()

            d2 = AbbreviationDictionary(path)
            d2.load()
            self.assertEqual(d2.entries["PHQ"].decision, "tentative_strip")


class TestDecisionAwareExport(unittest.TestCase):
    """Test that export methods respect firm decisions."""

    def test_strip_decision_overrides_category(self):
        """An unknown-category entry with strip decision should be exported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.yaml")
            d = AbbreviationDictionary()
            d.entries["K6"] = AbbreviationEntry(
                abbreviation="K6", category="unknown",
                decision="strip", tinyIds={"t1"}, n_tinyIds=1,
            )
            n = d.export_strip_patterns(path, ["instrument"])
            self.assertEqual(n, 1)

    def test_skip_decision_overrides_category(self):
        """An instrument-category entry with skip decision should NOT be exported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.yaml")
            d = AbbreviationDictionary()
            d.entries["BMI"] = AbbreviationEntry(
                abbreviation="BMI", category="instrument",
                decision="skip", tinyIds={"t1"}, n_tinyIds=1,
            )
            n = d.export_strip_patterns(path, ["instrument"])
            self.assertEqual(n, 0)


class TestHyphenatedExpansion(unittest.TestCase):
    """Test that parenthetical discovery captures hyphenated expansions."""

    def _make_data(self, defs):
        return [
            {"tinyId": f"tid{i}", "definitions": [{"definition": d}], "designations": []}
            for i, d in enumerate(defs)
        ]

    def test_hyphenated_expansion(self):
        data = self._make_data([
            "Epstein-Barr Virus (EBV) serology results.",
        ])
        d = AbbreviationDictionary()
        n = d.discover_parenthetical(data)
        self.assertEqual(n, 1)
        self.assertIn("EBV", d.entries)
        self.assertEqual(d.entries["EBV"].expansion, "Epstein-Barr Virus")

    def test_greedy_preamble_trimmed(self):
        data = self._make_data([
            "The following protocol was taken from the "
            "Coronary Artery Risk Development in Young Adults (CARDIA) study.",
        ])
        d = AbbreviationDictionary()
        n = d.discover_parenthetical(data)
        if n > 0 and "CARDIA" in d.entries:
            exp = d.entries["CARDIA"].expansion
            # Should NOT include "following protocol was taken from the"
            self.assertNotIn("following", exp)
            self.assertIn("Coronary", exp)


if __name__ == "__main__":
    unittest.main()
