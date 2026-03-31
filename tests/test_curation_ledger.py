"""Tests for logic/curation_ledger.py — CurationLedger and classify_patterns."""
import os
import tempfile
import unittest
from pathlib import Path

from logic.curation_ledger import (
    CurationDecision,
    CurationLedger,
    classify_patterns,
)


class TestClassifyPatterns(unittest.TestCase):
    """Tests for the core classification algorithm."""

    def _make_row(self, pattern, tinyids="tid1 tid2"):
        return {"pattern": pattern, "tinyIds": tinyids, "type": "instrument"}

    def _make_decision(self, pattern, decision, tinyids=None, modification=""):
        tids = tinyids or {"tid1", "tid2"}
        return CurationDecision(
            pattern=pattern,
            decision=decision,
            modification=modification,
            tinyIds=tids,
            n_tinyIds=len(tids),
            decided_at="2026-01-01",
            run_id="run_test",
            notes="",
        )

    def test_new_pattern(self):
        """Pattern not in ledger → needs_review."""
        current = [self._make_row("New Pattern")]
        prior = {}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 0)
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]["pattern"], "New Pattern")
        self.assertEqual(summary["new_pattern"], 1)

    def test_strip_same_tinyids(self):
        """Prior strip + same tinyIds → auto_strip."""
        current = [self._make_row("PHQ-9", "tid1 tid2")]
        prior = {"PHQ-9": self._make_decision("PHQ-9", "strip", {"tid1", "tid2"})}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(review), 0)
        self.assertEqual(auto[0]["prior_decision"], "strip")
        self.assertEqual(summary["auto_strip"], 1)

    def test_strip_new_tinyids(self):
        """Prior strip + new tinyIds → auto_strip (validity is inherent)."""
        current = [self._make_row("PHQ-9", "tid1 tid2 tid3")]
        prior = {"PHQ-9": self._make_decision("PHQ-9", "strip", {"tid1", "tid2"})}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(review), 0)
        self.assertEqual(summary["auto_strip"], 1)

    def test_skip_same_tinyids(self):
        """Prior skip + same tinyIds → auto_skip."""
        current = [self._make_row("False Positive", "tid1 tid2")]
        prior = {"False Positive": self._make_decision("False Positive", "skip", {"tid1", "tid2"})}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(review), 0)
        self.assertEqual(auto[0]["prior_decision"], "skip")
        self.assertEqual(summary["auto_skip"], 1)

    def test_skip_subset_tinyids(self):
        """Prior skip + subset tinyIds → auto_skip."""
        current = [self._make_row("False Positive", "tid1")]
        prior = {"False Positive": self._make_decision("False Positive", "skip", {"tid1", "tid2"})}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(review), 0)
        self.assertEqual(summary["auto_skip"], 1)

    def test_skip_new_tinyids(self):
        """Prior skip + new tinyIds → needs_review."""
        current = [self._make_row("False Positive", "tid1 tid2 tid3")]
        prior = {"False Positive": self._make_decision("False Positive", "skip", {"tid1", "tid2"})}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 0)
        self.assertEqual(len(review), 1)
        self.assertIn("new tinyIds", review[0]["notes"])
        self.assertEqual(summary["changed_tinyids_skip"], 1)

    def test_modify_same_tinyids(self):
        """Prior modify + same tinyIds → auto_modify."""
        current = [self._make_row("PHQ-9 Score", "tid1 tid2")]
        prior = {"PHQ-9 Score": self._make_decision(
            "PHQ-9 Score", "modify", {"tid1", "tid2"}, modification="PHQ-9 Total"
        )}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(review), 0)
        self.assertEqual(auto[0]["prior_decision"], "modify")
        self.assertEqual(auto[0]["modification"], "PHQ-9 Total")
        self.assertEqual(summary["auto_modify"], 1)

    def test_modify_new_tinyids(self):
        """Prior modify + new tinyIds → needs_review."""
        current = [self._make_row("PHQ-9 Score", "tid1 tid2 tid3")]
        prior = {"PHQ-9 Score": self._make_decision(
            "PHQ-9 Score", "modify", {"tid1", "tid2"}, modification="PHQ-9 Total"
        )}
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(len(auto), 0)
        self.assertEqual(len(review), 1)
        self.assertIn("new tinyIds", review[0]["notes"])
        self.assertEqual(summary["changed_tinyids_modify"], 1)

    def test_mixed_patterns(self):
        """Multiple patterns with mixed classifications."""
        current = [
            self._make_row("Keep Me", "tid1 tid2"),
            self._make_row("Remove Me", "tid1"),
            self._make_row("Brand New", "tid5 tid6"),
            self._make_row("Changed Remove", "tid1 tid2 tid9"),
        ]
        prior = {
            "Keep Me": self._make_decision("Keep Me", "strip", {"tid1", "tid2"}),
            "Remove Me": self._make_decision("Remove Me", "skip", {"tid1", "tid2"}),
            "Changed Remove": self._make_decision("Changed Remove", "skip", {"tid1", "tid2"}),
        }
        auto, review, summary = classify_patterns(current, prior)
        self.assertEqual(summary["auto_strip"], 1)
        self.assertEqual(summary["auto_skip"], 1)
        self.assertEqual(summary["new_pattern"], 1)
        self.assertEqual(summary["changed_tinyids_skip"], 1)
        self.assertEqual(len(auto), 2)  # Keep Me + Remove Me
        self.assertEqual(len(review), 2)  # Brand New + Changed Remove

    def test_empty_prior(self):
        """No prior decisions → all patterns need review."""
        current = [
            self._make_row("Pattern A"),
            self._make_row("Pattern B"),
        ]
        auto, review, summary = classify_patterns(current, {})
        self.assertEqual(len(auto), 0)
        self.assertEqual(len(review), 2)
        self.assertEqual(summary["new_pattern"], 2)

    def test_empty_current(self):
        """No current patterns → nothing to classify."""
        prior = {"PHQ-9": self._make_decision("PHQ-9", "strip")}
        auto, review, summary = classify_patterns([], prior)
        self.assertEqual(len(auto), 0)
        self.assertEqual(len(review), 0)


class TestTinyIdsHash(unittest.TestCase):
    """Tests for tinyId hash computation."""

    def test_deterministic(self):
        """Same set in different order → same hash."""
        h1 = CurationLedger.compute_tinyids_hash(["c", "a", "b"])
        h2 = CurationLedger.compute_tinyids_hash(["b", "c", "a"])
        self.assertEqual(h1, h2)

    def test_different_sets(self):
        """Different sets → different hashes."""
        h1 = CurationLedger.compute_tinyids_hash(["a", "b"])
        h2 = CurationLedger.compute_tinyids_hash(["a", "c"])
        self.assertNotEqual(h1, h2)

    def test_dedup(self):
        """Duplicates are ignored."""
        h1 = CurationLedger.compute_tinyids_hash(["a", "b"])
        h2 = CurationLedger.compute_tinyids_hash(["a", "b", "a", "b"])
        self.assertEqual(h1, h2)


class TestLedgerRoundTrip(unittest.TestCase):
    """Tests for ledger save/load persistence."""

    def test_save_load(self):
        """Save and reload preserves all data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save
            ledger = CurationLedger(tmpdir)
            decisions = [
                CurationDecision(
                    pattern="PHQ-9",
                    decision="strip",
                    modification="",
                    tinyIds={"tid1", "tid2", "tid3"},
                    n_tinyIds=3,
                    decided_at="2026-01-01T10:00:00",
                    run_id="run_001",
                    notes="valid instrument",
                ),
                CurationDecision(
                    pattern="False Pos",
                    decision="skip",
                    modification="",
                    tinyIds={"tid4"},
                    n_tinyIds=1,
                    decided_at="2026-01-01T10:00:00",
                    run_id="run_001",
                    notes="sentence fragment",
                ),
                CurationDecision(
                    pattern="Typo Scale",
                    decision="modify",
                    modification="Corrected Scale",
                    tinyIds={"tid5", "tid6"},
                    n_tinyIds=2,
                    decided_at="2026-01-01T10:00:00",
                    run_id="run_001",
                    notes="typo fix",
                ),
            ]
            ledger.update_decisions("phase1", decisions)
            ledger.record_run(
                run_id="run_001",
                input_json="/data/cdes.json",
                n_cdes=100,
                tinyids_hash="abc123",
                phase="instrument",
            )
            ledger.save()

            # Verify files exist
            self.assertTrue((Path(tmpdir) / "ledger_meta.yaml").exists())
            self.assertTrue((Path(tmpdir) / "instrument_decisions.tsv").exists())

            # Reload
            ledger2 = CurationLedger(tmpdir)
            self.assertTrue(ledger2.load())

            loaded = ledger2.get_decisions("phase1")
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded["PHQ-9"].decision, "strip")
            self.assertEqual(loaded["PHQ-9"].tinyIds, {"tid1", "tid2", "tid3"})
            self.assertEqual(loaded["False Pos"].decision, "skip")
            self.assertEqual(loaded["Typo Scale"].decision, "modify")
            self.assertEqual(loaded["Typo Scale"].modification, "Corrected Scale")

    def test_has_same_tinyids(self):
        """Checks that tinyids_hash comparison works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = CurationLedger(tmpdir)
            ledger.record_run(
                run_id="run_001",
                input_json="/data/cdes.json",
                n_cdes=100,
                tinyids_hash="abc123",
                phase="instrument",
            )
            ledger.save()

            ledger2 = CurationLedger(tmpdir)
            ledger2.load()
            self.assertTrue(ledger2.has_same_tinyids("abc123"))
            self.assertFalse(ledger2.has_same_tinyids("different"))

    def test_update_overwrites(self):
        """Re-updating a pattern overwrites the prior decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = CurationLedger(tmpdir)
            ledger.update_decisions("phase1", [
                CurationDecision(
                    pattern="PHQ-9", decision="skip",
                    tinyIds={"tid1"}, n_tinyIds=1,
                ),
            ])
            ledger.update_decisions("phase1", [
                CurationDecision(
                    pattern="PHQ-9", decision="strip",
                    tinyIds={"tid1", "tid2"}, n_tinyIds=2,
                ),
            ])
            loaded = ledger.get_decisions("phase1")
            self.assertEqual(loaded["PHQ-9"].decision, "strip")
            self.assertEqual(loaded["PHQ-9"].tinyIds, {"tid1", "tid2"})

    def test_no_ledger_returns_false(self):
        """Loading from non-existent directory returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = CurationLedger(os.path.join(tmpdir, "nonexistent"))
            self.assertFalse(ledger.load())

    def test_phase_isolation(self):
        """Phase 1 and Phase 2 decisions are independent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = CurationLedger(tmpdir)
            ledger.update_decisions("phase1", [
                CurationDecision(pattern="Inst A", decision="strip",
                                 tinyIds={"t1"}, n_tinyIds=1),
            ])
            ledger.update_decisions("phase2", [
                CurationDecision(pattern="Phrase B", decision="skip",
                                 tinyIds={"t2"}, n_tinyIds=1),
            ])
            ledger.save()

            ledger2 = CurationLedger(tmpdir)
            ledger2.load()
            p1 = ledger2.get_decisions("phase1")
            p2 = ledger2.get_decisions("phase2")
            self.assertIn("Inst A", p1)
            self.assertNotIn("Phrase B", p1)
            self.assertIn("Phrase B", p2)
            self.assertNotIn("Inst A", p2)


if __name__ == "__main__":
    unittest.main()
