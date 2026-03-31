# allcde03 Branching Strip Run — 2026-03-09

Temporary record of the first full 5-way branching strip run on the allcde03 corpus.

## Corpus

- **Input**: 22,743 CDEs (`allcde03/cdes.json`)
- **Instrument-stripped**: `phase1_output/inst_stripped.json` (Phase 1 complete)
- **Phase 2 curation**: 4,006 patterns reviewed → 273 curated + 7 substitute

## Pattern Inventory

| Category | Count | Source |
|----------|------:|--------|
| Instrument (full) | 458 | `inst_patterns_full.tsv` |
| Instrument (sub) | 458 | `inst_patterns_sub.tsv` (0 with suffix retention) |
| Curated phrases | 273 | `phase2_output/curated.tsv` |
| Substitute patterns | 7 | `phase2_output/substitute_patterns.tsv` |
| Verbatim strip | 39 | `config/verbatim_strip_patterns.yaml` |
| Temporal expanded | 2,100 | Expanded from 25 seeds |

### Substitute Patterns (7)

Applied as a pre-pass before branching strip:

| Pattern | Replace With | tinyIds |
|---------|-------------|--------:|
| Indicator of whether | Indicator of | 480 |
| (+ 6 others) | | |

## Execution

- **Engine**: N-way single-pass (`strip_branching` via `branching_strip_nway.yaml`)
- **Variants**: All 5 (MTSFPF, MFSTPF, MFSFPT, MTSFPT, MFSTPT)
- **Runtime**: 104 seconds for 22,743 CDEs x 5 variants

> **Note**: MT+ST combinations (MTSTPF, MTSTPT) were removed because full instrument
> removal deletes the entire pattern text, leaving nothing for sub-instrument removal
> to match — making them functionally equivalent to MTSFPF and MTSFPT respectively.
- **Output**: `allcde03/branching_output_nway/stripped_{CODE}.json`

## Quality Report Summary

Source: `branching_output_nway/strip_report.md`

### Remnants

- **6 trailing_article remnants** per variant (same 6 CDEs across all 5 variants)
- These are edge cases where an orphaned article ("a", "the") remains after stripping

### Temporal Phrases

- 56 unique temporal phrases found in instrument-only variants (MTSFPF, MFSTPF)
- 720 total occurrences — expected, since phrases are not stripped in PF variants
- Zero temporal phrases in PT variants — confirms temporal stripping is working

## Residue Analysis (MTSFPT — Maximum Strip)

MTSFPT is the most aggressive variant (full instruments + all phrases removed).

### Field Retention Distribution

| Retention Band | % of Fields |
|---------------|------------:|
| 90-100% | 84.2% |
| 100% (unchanged) | 78.2% |
| 50-89% | 10.1% |
| 10-49% | 4.2% |
| 1-9% | 1.2% |
| 0% (empty) | 0.3% |

### Hollowed-Out CDEs

- **33 CDEs** (0.1%) completely hollowed out — all fields empty after stripping
- All are designation-only CDEs with boilerplate content:
  - "If other, please specify" (most common)
  - "Question is reversed scored"
  - Similar formulaic text that is entirely pattern-matched

### Empty Definitions

- **17 empty definitions** in MTSFPT
- All originally contained only "Question is reversed scored" — correctly removed

### Near-Empty Fields

- **26.2% of CDEs** have at least one field reduced to 3 words or fewer
- These are content-word residues after removing temporal/instrument framing
- Expected behavior for maximally stripped variant — the remaining words are the semantic core

## Decision Summary (Phase 2 Curation)

From 4,006 patterns in `needs_review.tsv`:

| Decision | Count |
|----------|------:|
| skip | 3,743 |
| strip | 171 |
| modify | 102 |
| substitute | 7 |
| **Total** | **4,023** |

(17 patterns from original gate not present in curated review file — removed during dedup.)

## Files Produced

```
allcde03/branching_output_nway/
  stripped_MTSFPF.json    (~146.8 MB)
  stripped_MFSTPF.json    (~146.7 MB)
  stripped_MFSFPT.json    (~146.8 MB)
  stripped_MTSFPT.json    (~146.6 MB)
  stripped_MFSTPT.json    (~146.6 MB)
  temporal_expanded.tsv
  strip_report.md
```

## Notes

- Verbatim patterns merged into inst_full stage via `--verbatim-patterns` (default: enabled)
- Substitute pre-pass applied before branching strip (7 patterns, 39 verbatim merged)
- Quality is excellent: the 6 trailing_article remnants are a known edge case
