# Interim Checkpoint — Curator Strategy Analysis (2026-04-10)

## Summary

Interim checkpoint marking completion of the GT/ML/MD curator strategy
comparison report. Report documents three distinct conceptual approaches to
phrase curation, identifies four key divergence axes, and proposes an
idealized CDE design with structured Pydantic model extensions and
parameterized CDE bundles. Pending: individual curator narratives to be
added to their strategy sections before collation.

## Context

User investigated MTSTPT residues reported by a collaborator (gds, hdrs,
psqi, libcsp, nhexas, wj-iii) — confirmed collaborator was using pre-v7
data; all 6 abbreviations are fully stripped in current test_v7 output.
"Story recall" survives stripping due to curator strategy difference (not
a bug).

This led into the broader curator strategy analysis: locate where strategies
live (`.curation_ledger/` for merged, `phrase_curation2/phrase_needs_review_high_*.tsv`
for per-curator decisions, `comparison/curator_patterns/` for strip-only
filtered patterns), then produce a formal comparative analysis.

## Deliverable

**Report**: `phrase_curation3/reports/curator_strategy_analysis.md`

Structure:
- §1 Executive summary with decision distribution table
- §2 Curator profiles (GT minimalist 8%, ML moderate 24%, MD aggressive 64%)
- §3 Four divergence points with side-by-side Original/GT/ML/MD tables
  - §3.1 Subject reference language (143 of 218 GT-conservative patterns)
  - §3.2 Measurement framing (The scale which represents / Indicator of whether)
  - §3.3 Domain-specific recurring terms (540 MD-only strip patterns)
  - §3.4 Modify granularity (surgical vs boundary-trim vs aggressive)
- §4 Substitution strategies (shared + curator-unique)
- §5 Conclusion:
  - §5.1 Proposed `StructuredDefinition` Pydantic model with
    `MeasurementType` enum, `InstrumentReference`, `RecallPeriod`
  - §5.2 Three idealized CDE examples:
    - Pain Interference: 29 words → 7, instrument decomposed
    - Residential History: 5 age-span CDEs → 1 parameterized
    - ASSIST Fail Frequency: 9 substance CDEs → 1 parameterized
  - §5.3 CDE bundle design table (age span, substance, body part, time
    period, severity/frequency)
  - §5.4 ML as recommended baseline strategy (5 concrete rules)

Appendices: shared substitution patterns, inter-rater stats reference.

## Curator Strategy Distributions

| Curator | Strip | Skip | Modify | Substitute | Strip % | Strip tinyIds |
|---------|------:|-----:|-------:|-----------:|--------:|--------------:|
| GT      |    38 | 1,231|     60 |          2 |      8% |         5,001 |
| ML      |   205 |  998 |    117 |          0 |     24% |        11,936 |
| MD      |   756 |  478 |     85 |          1 |     64% |        16,133 |

Agreement zones (1,320 patterns in 2+ curators):
- Consensus strip: 59
- Consensus skip: 425
- 2-strip/1-skip (majority strip): 247 (GT dissents 218, ML 25, MD 4)
- 1-strip/2-skip: 589 (MD-only 540, ML-only 41, GT-only 8)

## Key Findings

1. **Subject references** (`participant/subject`, `his or her`) are the
   single largest disagreement axis — GT preserves, ML/MD strip.
2. **Measurement framing** (`The scale which represents`) — GT keeps, ML
   trims to skeleton, MD strips aggressively.
3. **Domain terms** (`Adverse Event`, `Cardiac MRI`, `Brain atrophy`) —
   MD strips 540 of these as non-differentiating; GT/ML preserve as
   clinical content. This is MD's most distinctive strategy divergence.
4. **Modify granularity** — ML's boundary-trimming is the most consistent
   across similar patterns; GT's surgical cuts leave orphaned fragments;
   MD's deep truncation occasionally removes meaningful context.

## Next Steps

- [ ] Each curator adds narrative to their strategy section (§2.1, §2.2, §2.3)
- [ ] Curator commentary on divergence examples in §3
- [ ] Collation of curator narratives
- [ ] Possible additional sections per user review
- [ ] After finalization: integrate ML strategy recommendations into
      production pipeline defaults

## Pipeline State

Unchanged since v1.5.1 R7 checkpoint (2026-04-06). No code changes in this
session — analysis and documentation only. Report lives under
`phrase_curation3/reports/` in the analysis workspace, not in the
cde_analyzer repo (data separation principle).

## File Locations Referenced

- `phrase_curation2/phrase_needs_review_high_{GT,MLEACH,MD}.tsv` — raw per-curator decisions
- `phrase_curation3/.curation_ledger/` — merged consensus ledger
- `phrase_curation3/comparison/curator_patterns/phrase_patterns_*.tsv` — strip-only per-curator patterns
- `phrase_curation3/comparison/substitute_patterns/substitute_*.tsv` — per-curator substitute patterns
- `phrase_curation3/embed_text/embed_MTSTPT{,_ML,_MD}.csv` — per-curator stripped embed text
- `phrase_curation3/test_v7/stripped_MTSTPT.json` — current GT/ML/MD strip outputs
- `phrase_curation3/reports/curator_strategy_analysis.md` — **this deliverable**
