"""
Curation Ledger — persistent record of human curation decisions.

Tracks keep/remove/modify decisions across pipeline runs so that
re-runs with expanded CDE repositories only present genuinely new
patterns for curation.

Storage layout::

    {ledger_dir}/
        ledger_meta.yaml              # run history, tinyId set hashes
        instrument_decisions.tsv      # Phase 1 pattern decisions
        phrase_decisions.tsv          # Phase 2 pattern decisions

Decision rules for classify_patterns():

    Prior decision  | Current tinyIds vs prior  | Action
    ----------------+---------------------------+--------------------------
    (not in ledger) | —                         | needs_review (new)
    keep            | any                       | auto_keep
    remove          | same or subset            | auto_remove
    remove          | has new tinyIds           | needs_review
    modify          | same or subset            | auto_modify (apply mod)
    modify          | has new tinyIds           | needs_review
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CurationDecision:
    """A single curation decision for one pattern."""
    pattern: str
    decision: str          # "keep" | "remove" | "modify"
    modification: str = ""
    tinyIds: Set[str] = field(default_factory=set)
    n_tinyIds: int = 0
    decided_at: str = ""
    run_id: str = ""
    notes: str = ""


DECISION_TSV_HEADERS = [
    "pattern", "decision", "modification", "tinyIds",
    "n_tinyIds", "decided_at", "run_id", "notes",
]

PHASE_FILE = {
    "phase1": "instrument_decisions.tsv",
    "phase2": "phrase_decisions.tsv",
}


# ---------------------------------------------------------------------------
# CurationLedger
# ---------------------------------------------------------------------------

class CurationLedger:
    """Persistent curation decision store for one project."""

    def __init__(self, ledger_dir: str):
        self.ledger_dir = Path(ledger_dir)
        self.meta_path = self.ledger_dir / "ledger_meta.yaml"
        self.meta: Dict[str, Any] = {}
        self._decisions: Dict[str, Dict[str, CurationDecision]] = {}

    # -- persistence --------------------------------------------------------

    def load(self) -> bool:
        """Load metadata YAML + decision TSVs.  Returns True if ledger exists."""
        if not self.meta_path.exists():
            return False

        import yaml
        with open(self.meta_path, encoding="utf-8") as f:
            self.meta = yaml.safe_load(f) or {}

        for phase_key, filename in PHASE_FILE.items():
            tsv_path = self.ledger_dir / filename
            if tsv_path.exists():
                self._decisions[phase_key] = _load_decisions_tsv(tsv_path)

        return True

    def save(self) -> None:
        """Write meta YAML + decision TSVs."""
        import yaml

        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.meta["updated"] = datetime.now().isoformat()

        with open(self.meta_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.meta, f, default_flow_style=False,
                           sort_keys=False)

        for phase_key, decisions in self._decisions.items():
            filename = PHASE_FILE.get(phase_key)
            if filename and decisions:
                _save_decisions_tsv(self.ledger_dir / filename, decisions)

    # -- queries ------------------------------------------------------------

    def get_decisions(self, phase_key: str) -> Dict[str, CurationDecision]:
        """Return all decisions for a phase (empty dict if none)."""
        return dict(self._decisions.get(phase_key, {}))

    def has_same_tinyids(self, tinyids_hash: str) -> bool:
        """Check if the latest run had the same tinyIds set hash."""
        runs = self.meta.get("runs", [])
        if not runs:
            return False
        return runs[-1].get("tinyids_hash") == tinyids_hash

    # -- mutations ----------------------------------------------------------

    def update_decisions(
        self, phase_key: str, decisions: List[CurationDecision]
    ) -> None:
        """Insert or update decisions.  Overwrites existing by pattern key."""
        if phase_key not in self._decisions:
            self._decisions[phase_key] = {}
        store = self._decisions[phase_key]
        for d in decisions:
            store[d.pattern] = d

    def record_run(
        self,
        run_id: str,
        input_json: str,
        n_cdes: int,
        tinyids_hash: str,
        phase: str,
        summary: Optional[Dict[str, int]] = None,
    ) -> None:
        """Append a run record to metadata."""
        if "created" not in self.meta:
            self.meta["created"] = datetime.now().isoformat()
        if "runs" not in self.meta:
            self.meta["runs"] = []

        record: Dict[str, Any] = {
            "id": run_id,
            "timestamp": datetime.now().isoformat(),
            "input_json": str(input_json),
            "n_cdes": n_cdes,
            "tinyids_hash": tinyids_hash,
            "phase": phase,
        }
        if summary:
            record.update({
                "n_auto_kept": summary.get("auto_keep", 0),
                "n_auto_removed": summary.get("auto_remove", 0),
                "n_auto_modified": summary.get("auto_modify", 0),
                "n_new_reviewed": summary.get("new_pattern", 0)
                    + summary.get("changed_tinyids_remove", 0)
                    + summary.get("changed_tinyids_modify", 0),
            })

        self.meta["runs"].append(record)

    # -- static helpers -----------------------------------------------------

    @staticmethod
    def compute_tinyids_hash(tinyids: Iterable[str]) -> str:
        """SHA-256 of sorted tinyIds joined by newline."""
        sorted_ids = sorted(set(tinyids))
        return hashlib.sha256("\n".join(sorted_ids).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Classification algorithm
# ---------------------------------------------------------------------------

def classify_patterns(
    current_patterns: List[Dict[str, str]],
    prior_decisions: Dict[str, CurationDecision],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], Dict[str, int]]:
    """
    Classify each current pattern against prior curation decisions.

    Parameters
    ----------
    current_patterns : list of dicts
        Rows from the enriched TSV (must have 'pattern' and 'tinyIds' keys).
    prior_decisions : dict
        Mapping from pattern text to CurationDecision.

    Returns
    -------
    auto_resolved : list of dicts
        Patterns auto-resolved from prior decisions.  Each dict has all
        original columns plus ``prior_decision``, ``resolution_source``,
        and ``modification`` (for modify decisions).
    needs_review : list of dicts
        Patterns that need human curation.  Each dict has all original
        columns plus empty ``decision``, ``modification``, ``notes``.
    summary : dict
        Counts: auto_keep, auto_remove, auto_modify, new_pattern,
        changed_tinyids_remove, changed_tinyids_modify.
    """
    auto_resolved: List[Dict[str, str]] = []
    needs_review: List[Dict[str, str]] = []
    summary = {
        "auto_keep": 0,
        "auto_remove": 0,
        "auto_modify": 0,
        "new_pattern": 0,
        "changed_tinyids_remove": 0,
        "changed_tinyids_modify": 0,
    }

    for row in current_patterns:
        pattern = row.get("pattern", "")
        tinyids_str = row.get("tinyIds", "")
        current_tinyids = set(t for t in re.split(r"[\s|]+", tinyids_str) if t)

        prior = prior_decisions.get(pattern)

        if prior is None:
            # New pattern — not in ledger
            nr = dict(row)
            nr["decision"] = ""
            nr["modification"] = ""
            nr["notes"] = ""
            needs_review.append(nr)
            summary["new_pattern"] += 1
            continue

        has_new = _has_new_tinyids(current_tinyids, prior.tinyIds)

        if prior.decision == "keep":
            ar = dict(row)
            ar["prior_decision"] = "keep"
            ar["resolution_source"] = "ledger_auto_keep"
            ar["modification"] = ""
            auto_resolved.append(ar)
            summary["auto_keep"] += 1

        elif prior.decision == "remove":
            if has_new:
                nr = dict(row)
                nr["decision"] = ""
                nr["modification"] = ""
                nr["notes"] = f"Previously removed; new tinyIds detected"
                needs_review.append(nr)
                summary["changed_tinyids_remove"] += 1
            else:
                ar = dict(row)
                ar["prior_decision"] = "remove"
                ar["resolution_source"] = "ledger_auto_remove"
                ar["modification"] = ""
                auto_resolved.append(ar)
                summary["auto_remove"] += 1

        elif prior.decision == "modify":
            if has_new:
                nr = dict(row)
                nr["decision"] = ""
                nr["modification"] = prior.modification
                nr["notes"] = (
                    f"Previously modified to '{prior.modification}'; "
                    f"new tinyIds detected"
                )
                needs_review.append(nr)
                summary["changed_tinyids_modify"] += 1
            else:
                ar = dict(row)
                ar["prior_decision"] = "modify"
                ar["resolution_source"] = "ledger_auto_modify"
                ar["modification"] = prior.modification
                auto_resolved.append(ar)
                summary["auto_modify"] += 1

        else:
            # Unknown decision — treat as new
            nr = dict(row)
            nr["decision"] = ""
            nr["modification"] = ""
            nr["notes"] = f"Unknown prior decision: {prior.decision}"
            needs_review.append(nr)
            summary["new_pattern"] += 1

    return auto_resolved, needs_review, summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_new_tinyids(current: Set[str], prior: Set[str]) -> bool:
    """True if current contains any tinyId not in prior."""
    return bool(current - prior)


def _load_decisions_tsv(path: Path) -> Dict[str, CurationDecision]:
    """Load a decisions TSV into a pattern-keyed dict."""
    decisions: Dict[str, CurationDecision] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pattern = row.get("pattern", "").strip()
            if not pattern:
                continue
            tinyids_str = row.get("tinyIds", "")
            tinyids = set(t for t in re.split(r"[\s|]+", tinyids_str) if t)
            decisions[pattern] = CurationDecision(
                pattern=pattern,
                decision=row.get("decision", "keep"),
                modification=row.get("modification", ""),
                tinyIds=tinyids,
                n_tinyIds=len(tinyids),
                decided_at=row.get("decided_at", ""),
                run_id=row.get("run_id", ""),
                notes=row.get("notes", ""),
            )
    return decisions


def _save_decisions_tsv(
    path: Path, decisions: Dict[str, CurationDecision]
) -> None:
    """Write decisions dict as a TSV file."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=DECISION_TSV_HEADERS,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for pattern in sorted(decisions):
            d = decisions[pattern]
            writer.writerow({
                "pattern": d.pattern,
                "decision": d.decision,
                "modification": d.modification,
                "tinyIds": " ".join(sorted(d.tinyIds)),
                "n_tinyIds": len(d.tinyIds),
                "decided_at": d.decided_at,
                "run_id": d.run_id,
                "notes": d.notes,
            })
