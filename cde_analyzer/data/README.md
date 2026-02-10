# Test Data — Pipeline Reference Records

Representative CDE records from scheuermann08 pipeline run (2026-01-29).
Source: scheuermann04/cdes_subset.json (1,148 CDEs).

## Files

| File | Description |
|------|-------------|
| `test_records.json` | Subset of CDE records (one per category) |
| `ground_truth.tsv` | Per-tinyId category, status, and notes |

## Categories

| Category | Status | Count | Description |
|----------|--------|------:|-------------|
| `promis_clean` | works_perfectly | 5 | PROMIS instrument fully stripped |
| `hdrs_clean` | works_perfectly | 3 | HDRS instrument fully stripped |
| `cesd_instrument` | works_mostly | 5 | CES-D instrument — some residual fragments |
| `cesd_residual` | partial | 3 | CES-D residual text in stripped output |
| `neuroqol_residual` | partial | 3 | Neuro-QoL residual text in stripped output |
| `orphan_the` | artifact | 3 | Orphan article left after def-variant stripping |
| `verb_false_positive` | false_positive | 6 | Verb-containing pattern incorrectly matched as instrument |
| `no_instrument` | no_match | 5 | No instrument or phrase patterns detected |
| `phrase_stripped` | phrase_stripped | 5 | No instrument match but Phase 2 phrases stripped |

**Total**: 38 records

## Status Legend

| Status | Meaning |
|--------|---------|
| `works_perfectly` | Pattern fully detected and stripped |
| `works_mostly` | Pattern detected but minor residuals possible |
| `partial` | Significant residual text remains after stripping |
| `artifact` | Side-effect of stripping (orphan articles) |
| `false_positive` | Pattern incorrectly identified (verb phrase) |
| `no_match` | No patterns detected for this CDE |
| `phrase_stripped` | No instrument match but Phase 2 phrases stripped |
