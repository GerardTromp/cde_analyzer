# CDE Pattern Mining & Stripping Workflow

Two-phase iterative pipeline for extracting and removing repeated patterns from CDE text fields.

---

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INPUT: Raw CDE JSON                               │
│                         (fix_underscores + strip_html)                      │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 1: INSTRUMENT PATTERN STRIPPING                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Mine         instrument_miner -i cdes.json -o inst_output/       │   │
│  │                 --detect-families --family-summary                   │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ instruments.tsv                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ╔══════════════════════════════════════╗               │   │
│  │              ║    PATTERN CURATION SUB-WORKFLOW     ║               │   │
│  │              ║         (see expanded below)         ║               │   │
│  │              ╚══════════════════════════════════════╝               │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ curated_instruments.tsv                 │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 5. Strip       strip_phrases -i cdes.json -m CDE                    │   │
│  │                -o inst_stripped.json --patterns curated.tsv         │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │ inst_stripped.json
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2: GENERIC PHRASE STRIPPING                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Mine         phrase_miner -i inst_stripped.json -o phrase_out/   │   │
│  │                 --enable-subsumption --analyze-phrase-families      │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ verbatim_phrases.tsv                    │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ╔══════════════════════════════════════╗               │   │
│  │              ║    PATTERN CURATION SUB-WORKFLOW     ║               │   │
│  │              ║         (see expanded below)         ║               │   │
│  │              ╚══════════════════════════════════════╝               │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ curated_phrases.tsv                     │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 5. Strip       strip_phrases -i inst_stripped.json -m CDE           │   │
│  │                -o final_stripped.json --patterns curated.tsv        │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OUTPUT: Cleaned CDE JSON                               │
│                    (instruments & phrases removed)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pattern Curation Sub-Workflow (Expanded)

This sub-workflow is used in both Phase 1 (instruments) and Phase 2 (phrases).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PATTERN CURATION SUB-WORKFLOW                           │
│                                                                             │
│   Input: Raw patterns from mining (instruments.tsv or verbatim_phrases.tsv) │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 2. Discover     strip_discover -i cdes.json -m CDE                  │   │
│  │    Verbatim     -o discovered.tsv -p mined_patterns.tsv             │   │
│  │                 --expand-variants --discover-bare-names             │   │
│  │                                                                     │   │
│  │    Variant expansion includes:                                      │   │
│  │    • Spacing around parentheses: "(X)" ↔ "( X )"                    │   │
│  │    • Trailing punctuation: "X" ↔ "X:" ↔ "X - " ↔ "X: "              │   │
│  │    • Possessives: "Parkinson" ↔ "Parkinson's"                       │   │
│  │    • Number words: "7" ↔ "seven", "30" ↔ "thirty"                   │   │
│  │    • Bare names: extracts name without "as part of" prefix          │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ discovered.tsv (expanded)               │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3. Coalesce     strip_discover --coalesce-variants discovered.tsv   │   │
│  │    Variants     -o coalesced.tsv --coalesce-report report.tsv       │   │
│  │                                                                     │   │
│  │    TinyId-aware subsumption removes redundant patterns:             │   │
│  │    • "in the past 7 days" subsumed by "in the past 7 days:"        │   │
│  │      if all tinyIds are covered by longer patterns                  │   │
│  │    • Reduces pattern count while preserving coverage                │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ coalesced.tsv                           │
│                                   ▼                                         │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│  │ 4. CURATOR      Manual review of coalesced.tsv                      │   │
│  │    REVIEW       • Remove false positives                            │   │
│  │    (human)      • Add missing patterns                              │   │
│  │                 • Verify tinyId coverage                            │   │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┬ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   │
│                                   │ curated.tsv                             │
│                                   ▼                                         │
│   Output: Curated patterns ready for strip_phrases                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Iterative Improvement Loop (False Negative Recovery)

After stripping, some patterns may remain. This loop recovers them:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FALSE NEGATIVE RECOVERY LOOP                            │
│                                                                             │
│       ┌─────────────────────────────────────────────────────────┐          │
│       │ Stripped JSON (inst_stripped.json or final_stripped.json)│          │
│       └─────────────────────────┬───────────────────────────────┘          │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ A. Diagnose     diagnose_strip -i stripped.json -m CDE              │   │
│  │    Remaining    -o remaining.tsv --suggest-patterns                 │   │
│  │                                                                     │   │
│  │    OR                                                               │   │
│  │                                                                     │   │
│  │                 strip_discover -i stripped.json                     │   │
│  │                 --analyze-false-negatives -o false_neg.tsv          │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ remaining patterns TSV                  │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ A2. Search for  (Instrument phase only)                             │   │
│  │     Known       grep -E '\[(PROMIS|Neuro-QOL|MDS-UPDRS|...)\]'      │   │
│  │     Abbrevs     grep -E '(PROMIS|Neuro-QOL|...) - '                 │   │
│  │                                                                     │   │
│  │     Catches short bracketed patterns [PROMIS] and " - " separators  │   │
│  │     missed by k-mer mining (patterns below minimum k-mer length)    │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│  │ B. CURATOR      Review false_neg.tsv AND grep results               │   │
│  │    REVIEW       Set 'include' column to 'yes' for valid patterns    │   │
│  │    (human)      Add 'name' column with canonical names              │   │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┬ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   │
│                                   │ curated false negatives                 │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ C. Import to    strip_discover --add-to-supplementary curated.tsv   │   │
│  │    Config       (adds to config/supplementary_patterns.yaml)        │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ D. Re-mine      instrument_miner ... --extract-supplementary        │   │
│  │    with new     (picks up newly added patterns)                     │   │
│  │    patterns                                                         │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                       ┌───────────┴───────────┐                            │
│                       │  Repeat until          │                            │
│                       │  false negatives       │                            │
│                       │  are acceptable        │                            │
│                       └───────────────────────┘                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Command Quick Reference

### Phase 1: Instrument Mining & Stripping

```bash
# 1. Mine instruments
cde-analyzer instrument_miner -i cdes.json -o inst_output/ \
    --detect-families --family-summary

# 1b. Discover abbreviation-based patterns (catches [PROMIS], PROMIS - , etc.)
cde-analyzer strip_discover --discover-abbreviations inst_output/instruments.tsv \
    -i cdes.json -o inst_output/abbrev_patterns.tsv

# 2. Discover verbatim occurrences with variants
cde-analyzer strip_discover -i cdes.json -m CDE \
    -o discovered_inst.tsv -p inst_output/instruments.tsv \
    --additional-patterns inst_output/abbrev_patterns.tsv \
    --expand-variants --discover-bare-names

# 3. Coalesce redundant variants
cde-analyzer strip_discover --coalesce-variants discovered_inst.tsv \
    -o coalesced_inst.tsv --coalesce-report coalesce_report.tsv

# 4. [CURATOR REVIEW: edit coalesced_inst.tsv]

# 5. Strip instruments from CDE JSON
cde-analyzer strip_phrases -i cdes.json -m CDE \
    -o inst_stripped.json --patterns coalesced_inst.tsv
```

### Phase 2: Generic Phrase Mining & Stripping

```bash
# 1. Mine phrases from instrument-stripped data
cde-analyzer phrase_miner -i inst_stripped.json -o phrase_output/ \
    --enable-subsumption --analyze-phrase-families

# 2. Discover verbatim occurrences with variants
cde-analyzer strip_discover -i inst_stripped.json -m CDE \
    -o discovered_phrases.tsv -p phrase_output/verbatim_phrases.tsv \
    --expand-variants

# 3. Coalesce redundant variants
cde-analyzer strip_discover --coalesce-variants discovered_phrases.tsv \
    -o coalesced_phrases.tsv --coalesce-report phrase_coalesce.tsv

# 4. [CURATOR REVIEW: edit coalesced_phrases.tsv]

# 5. Strip phrases from CDE JSON
cde-analyzer strip_phrases -i inst_stripped.json -m CDE \
    -o final_stripped.json --patterns coalesced_phrases.tsv
```

### False Negative Recovery

```bash
# A. Diagnose remaining patterns
cde-analyzer diagnose_strip -i final_stripped.json -m CDE \
    -o remaining.tsv --suggest-patterns

# OR analyze false negatives directly
cde-analyzer strip_discover -i final_stripped.json \
    --analyze-false-negatives -o false_neg.tsv

# A2. Search for known abbreviations (instruments only)
# Catches short bracketed patterns and " - " separators missed by k-mer mining
grep -E '\[(PROMIS|Neuro-QOL|MDS-UPDRS|PHQ|GAD|SF-36|HADS)\]' inst_stripped.json
grep -E '(PROMIS|Neuro-QOL|MDS-UPDRS|PHQ|GAD) - ' inst_stripped.json

# B. [CURATOR REVIEW: combine results, mark valid patterns]

# C. After curator review, import to supplementary config
cde-analyzer strip_discover --add-to-supplementary curated_fn.tsv

# D. Re-mine with supplementary patterns
cde-analyzer instrument_miner -i cdes.json -o inst_output/ \
    --extract-supplementary
```

---

## Key Files in Workflow

| Stage | Input | Output | Description |
|-------|-------|--------|-------------|
| Preprocessing | raw.json | cdes.json | fix_underscores + strip_html |
| Instrument Mine | cdes.json | instruments.tsv | Raw instrument patterns |
| Discover (inst) | instruments.tsv | discovered_inst.tsv | Verbatim with variants |
| Coalesce (inst) | discovered_inst.tsv | coalesced_inst.tsv | Deduplicated patterns |
| Strip (inst) | cdes.json + patterns | inst_stripped.json | Instrument-free JSON |
| Phrase Mine | inst_stripped.json | verbatim_phrases.tsv | Raw phrase patterns |
| Discover (phrase) | verbatim_phrases.tsv | discovered_phrases.tsv | Verbatim with variants |
| Coalesce (phrase) | discovered_phrases.tsv | coalesced_phrases.tsv | Deduplicated patterns |
| Strip (phrase) | inst_stripped.json + patterns | final_stripped.json | Fully cleaned JSON |

---

## Notes

- **Why two phases?** Instruments ("as part of X") are domain-specific noise that obscures general phrases. Removing them first reveals underlying patterns.

- **Why expand then coalesce?** Expansion catches all surface-form variants (punctuation, spacing, numbers). Coalescing removes redundant short patterns covered by longer ones, reducing curator review burden.

- **Why curator review?** Automated mining includes false positives (accidental patterns). Human review ensures only meaningful patterns are stripped.

- **Iterative improvement**: After each strip phase, remaining patterns can be recovered and added to supplementary config for the next round.

- **Why search for abbreviations?** K-mer mining has a minimum length threshold, so short patterns like `[PROMIS]` or `[Neuro-QOL]` may be missed. Additionally, patterns with ` - ` separators (e.g., `PROMIS - Pain Interference`) may have been missed if that variant form wasn't implemented at mining time. Grepping for known abbreviations catches these edge cases.
