# Lessons Learned — Session 2026-01-29

## Pipeline Overview

The CDE Analyzer pipeline strips instrument names and generic phrases from NLM Common Data Elements, producing clean text suitable for semantic clustering. The pipeline runs in two major phases, each producing intermediate and final outputs.

### Workflow Architecture (Current State)

```
                        Input: cdes.json (1,148 CDEs)
                                  │
                    ══════════════╪══════════════
                    ║  PHASE 1: Instrument Detection  ║
                    ══════════════╪══════════════
                                  │
                    ┌─────────────┴─────────────┐
                    │  1. Mine instruments       │
                    │     (abbreviation-only +   │
                    │      supplementary)         │
                    ├───────────────────────────────┤
                    │  2. Batch expand abbreviations│
                    │     PROMIS → "Patient-        │
                    │     Reported Outcome..."      │
                    ├───────────────────────────────┤
                    │  3. Discover abbreviation      │
                    │     designation patterns       │
                    │     (PROMIS - ..., [PROMIS])   │
                    ├───────────────────────────────┤
                    │  ★ CHECKPOINT: Expansion review│
                    ├───────────────────────────────┤
                    │  4. Discover verbatim patterns │
                    │     (instruments + expanded    │
                    │      + abbrev patterns)        │
                    ├───────────────────────────────┤
                    │  5. Coalesce (subsumption +    │
                    │     prefix extraction)         │
                    ├───────────────────────────────┤
                    │  ★ CHECKPOINT: Curator review  │  → curated_instruments.tsv
                    ├───────────────────────────────┤
                    │  6. Family discovery           │
                    │  7. Re-discover abbreviations  │
                    │  8. Final discover + coalesce  │
                    │     (emit-def-variants,        │
                    │      split-tiers: 3)           │
                    ├───────────────────────────────┤
                    │  ★ CHECKPOINT: Final review    │
                    ├───────────────────────────────┤
                    │  9a. Strip tier-1 (≥3 tokens)  │  → tier1_stripped.json
                    │  9b. Strip tier-2 (<3 tokens)  │  → no_instruments.json  ← OUTPUT 1
                    ├───────────────────────────────┤
                    │  10. Sanity check              │  → sanity_check.tsv     ← OUTPUT 2
                    │  11. Discovery report          │  → discovery_report.md  ← OUTPUT 3
                    └───────────────────────────────┘
                                  │
                    ══════════════╪══════════════
                    ║  PHASE 2: Phrase Stripping      ║
                    ══════════════╪══════════════
                                  │
                    ┌─────────────┴─────────────┐
                    │  1. Mine phrases (k-mer)   │
                    │  2. Discover verbatim       │
                    │  3. Coalesce patterns       │
                    │  4. Field analysis          │
                    │     (enrich + filter)       │
                    ├───────────────────────────────┤
                    │  ★ CHECKPOINT: Curator review │  → curated.tsv
                    ├───────────────────────────────┤
                    │  5. Strip phrases             │  → final_stripped.json   ← OUTPUT 4
                    │  6. Discovery report          │  → discovery_report.md  ← OUTPUT 5
                    └───────────────────────────────┘
```

### Five Key Outputs

| # | File | Description |
|---|------|-------------|
| 1 | `no_instruments.json` | CDE JSON with instrument names removed |
| 2 | `sanity_check.tsv` | Remaining instrument-like patterns (quality gate) |
| 3 | `phase1_output/discovery_report.md` | Phase 1 pipeline metrics summary |
| 4 | `final_stripped.json` | CDE JSON with both instruments and phrases removed |
| 5 | `phase2_output/discovery_report.md` | Phase 2 pipeline metrics summary |

---

## Lessons Learned

### 1. Two-Pass Stripping Prevents Fragment Damage

**Problem**: Short fragment patterns like "Scale" or "past" can match inside longer instrument names (e.g., "Geriatric Depression **Scale** (GDS)"), destroying the instrument name before the longer pattern can match it.

**Solution**: Split coalesced patterns into tier-1 (≥3 tokens, long instrument names) and tier-2 (<3 tokens, fragments). Strip tier-1 first, then tier-2 from the tier-1 output.

**Implementation**: `--split-tiers 3` on `pattern_util --coalesce-variants` + sequential `strip_tier1`/`strip_tier2` workflow steps.

**Measured impact** (scheuermann08): 105 tier-1 + 31 tier-2 patterns. Without two-pass, tier-2 patterns would corrupt ~30 instrument names.

---

### 2. Definition-Form Variants Are Essential

**Problem**: Instrument patterns discovered from designations often end with ` - ` or ` -` (the separator between instrument name and item text). Definitions contain the same instrument name *without* this separator. Without variants, definitions go unstripped.

**Solution**: `--emit-def-variants` on coalesce emits each pattern both with and without its trailing separator.

**Measured impact** (scheuermann08): 29 definition-form variants added to the final coalesced output. Without them, ~20+ instrument references in definitions would survive.

**Side effect**: Stripping definition-form variants (which remove the instrument name but not the preceding article) leaves residual articles like "the" and "the and" in the output. This is a known artifact, not a bug — addressed in Remaining Problems #3.

---

### 3. `min_parent_tinyids` Threshold Is Dataset-Sensitive

**Problem**: The phrase pipeline's `min_parent_tinyids` parameter (default: 20) controls how aggressively parent phrase frequency filters coalesced patterns. With a 1,148-CDE dataset, this default removed 1,145 of 1,151 discovered patterns, leaving only 4 (then 2 after field analysis).

**Discovery**: Compared scheuermann07 (54 coalesced, run with manual override) to scheuermann08 initial run (4 coalesced, using default). Traced to the parent filter being too aggressive.

**Workaround**: Manually re-ran coalesce with `--min-parent-tinyids 2`, yielding 590 patterns (85 after field analysis).

**Recommendation**: Either lower the default or make it adaptive based on corpus size. A threshold of 2 worked well for ~1K CDEs. Larger corpora may need higher values.

---

### 4. Verb-Containing Phrases Are Recurring False Positives

**Problem**: Both Phase 1 (instruments) and Phase 2 (phrases) produce false positive patterns that contain verbs. Examples from scheuermann08 Phase 1:
- `mentally tired` (from "mentally tired after")
- `my sexual` (from "my sexual thoughts and")
- `think about` (from "think about sex")
- `to your` (from "to your ability to maintain...")

These are sentence fragments, not instrument or phrase names.

**Current workaround**: Manual identification and removal during curation checkpoints.

**Proposed automation**: POS-tag patterns and flag those containing verbs (VB, VBD, VBG, VBN, VBP, VBZ) or pronouns (PRP, PRP$) as likely false positives. The SpaCy infrastructure in `logic/span_boundary.py` already supports this analysis.

---

### 5. Sanity Check Residuals Are Diagnostic, Not Failures

**Problem**: After stripping, the sanity check (scheuermann08) found 17 remaining patterns, 194 total occurrences. Top survivors:
- `the` (89 occurrences) — residual article from definition-form variant stripping
- `the Studies-Depression (CES-D)` (20x) — partial instrument name fragment
- `the and` (18x) — article + conjunction residual
- `the Disorders (Neuro-Qol)` (17x) — partial instrument name fragment

**Analysis**: These are artifacts of the definition-form variant mechanism. When "Center for Epidemiologic Studies-Depression (CES-D) -" is stripped from a designation, but "Center for Epidemiologic Studies-Depression (CES-D)" is stripped from a definition that starts with "the Center for...", the leading "the" remains.

**Resolution**: Treat these as expected artifacts. Post-strip cleanup of residual articles is tracked as a follow-up enhancement.

---

### 6. WSL Path Mangling Requires Bash Wrapper

**Problem**: Running `wsl -d Ubuntu-22.04 -- ls /path` from Windows Git Bash causes path mangling — Git Bash converts `/path` to a Windows path before passing to WSL.

**Solution**: Always use the bash wrapper pattern:
```bash
wsl -d Ubuntu-22.04 -- bash -c "command with /unix/paths"
```

This is mandatory for all WSL invocations from Windows terminals.

---

### 7. Pipeline Resumption After Manual Override

**Problem**: When the workflow hits a checkpoint and the user manually re-runs intermediate steps with different parameters (e.g., lower `min_parent_tinyids`), the workflow state file still contains the original parameter values.

**What worked**: The manual re-runs overwrote the output files in place. When the workflow resumed, it proceeded from the checkpoint using the updated files regardless of the parameter mismatch in the state file.

**Risk**: The state file's parameter values don't reflect the actual parameters used. If the pipeline were to re-run skipped steps, it would use the original (wrong) parameters. This is a documentation issue, not a code bug — the workflow engine correctly treats completed steps as done.

---

### 8. Field Analysis Filters Work Well Together

**Problem**: After coalescing, many patterns are noise — appearing in too few CDEs or being too short to be meaningful phrases.

**Solution**: The `--field-analysis` subcommand applies three complementary filters:
1. `--min-field-count 6` — removes patterns appearing in fewer than 6 CDEs in any single field
2. `--min-tokens 3` — removes patterns with fewer than 3 words
3. `--exclude-patterns` — removes known false positives (e.g., instrument residuals)

**Measured impact** (scheuermann08 Phase 2): 590 coalesced → 85 after field analysis. The 505 removed patterns were genuinely noise (low-frequency or short fragments).

---

## Remaining Problems

### 1. Verb-Containing Phrase Detection

Automate identification of false positive patterns containing verbs. Patterns like "think about", "mentally tired", "my sexual" are sentence fragments, not meaningful phrases. SpaCy POS tagging can flag these. See Lesson #4.

### 2. Dataset-Adaptive `min_parent_tinyids`

The default of 20 is too aggressive for ~1K CDEs. Options: (a) lower the default to 2, (b) make it proportional to corpus size (e.g., `max(2, sqrt(N)/10)`), (c) require the user to set it explicitly. See Lesson #3.

### 3. Post-Strip Article Cleanup

After definition-form variant stripping, residual articles ("the", "the and", "and") appear in the output. A simple post-strip regex cleanup pass would remove these. Could be a new `strip_phrases` option or a standalone cleanup step. See Lesson #5.

### 4. Temporal Pattern Noise in Phase 2

Temporal patterns (e.g., "in the past 7 days") still contain noise after curation. The `--group-semantic` infrastructure exists in `logic/span_boundary.py` but isn't integrated into the phrase pipeline workflow. Temporal group detection and normalization should be a standard pre-curation step.

### 5. Workflow Parameter Mismatch After Manual Override

When users manually override intermediate steps, the workflow state file parameters diverge from actual execution. Consider adding a "parameter override" mechanism to the workflow engine, or logging actual parameters used in output file metadata headers.

---

## Run Summary: scheuermann08

| Metric | Phase 1 | Phase 2 |
|--------|---------|---------|
| Input CDEs | 1,148 | 1,148 (post-instrument-strip) |
| Mined patterns | 56 instruments | 857 phrases |
| Discovered patterns | 391 | 1,235 |
| Coalesced patterns | 104 → 100 (4 FP removed) | 590 → 85 (field analysis) |
| Final patterns | 136 (105 T1 + 31 T2) | 85 |
| tinyIds covered | ~890 | 535 |
| Sanity survivors | 17 (194 occurrences) | — |
| False positives removed | 4 (verb phrases) | 0 (accepted as-is) |
