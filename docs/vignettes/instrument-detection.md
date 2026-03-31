# Vignette: Instrument Detection (Phase 1)

A deep dive into the instrument detection pipeline — how it works, what to
look for during curation, and how to handle edge cases.

## What This Vignette Covers

CDE records frequently reference standardized assessment instruments
(PHQ-9, PROMIS Pain Interference, Neuro-QOL, etc.) in their designations
and definitions. Phase 1 detects these instrument names, presents them for
human curation, and strips them to produce cleaner text for downstream
analysis.

This vignette covers:

- Running the instrument pipeline and interpreting its output
- Curation decisions: what to strip, skip, and investigate
- Iterative harvesting to catch instruments missed in the first pass
- Supplementary pattern management
- Tuning parameters and troubleshooting common issues

**Prerequisites**: A JSON file of CDE records and familiarity with the
[Quickstart](quickstart.md) walkthrough.

**Related documentation**:

- [instrument_miner reference](../help/instrument_miner.md) — mining command details
- [pattern_util reference](../help/pattern_util.md) — coalescing, enrichment, hierarchy
- [Curation Guide](../curation-guide.md) — general curation decision framework
- [Parameter Tuning](parameter-tuning.md) — dataset-size-specific settings

---

## 1. What the Instrument Pipeline Does

The `instrument_pipeline.yaml` workflow runs 9 steps:

```
mine_instruments → discover_abbreviations → discover_verbatim
    → coalesce_patterns → validate_subsumption → enrich_fields
    → [CHECKPOINT: curator_review]
    → strip_instruments → sanity_check
```

| Step | What it does | Key output |
|------|-------------|------------|
| mine_instruments | Regex + NLP extraction of instrument names | `instruments.tsv`, `mined_patterns.tsv` |
| discover_abbreviations | Finds abbreviation expansions (PHQ → Patient Health Questionnaire) | `abbrev_patterns.tsv` |
| discover_verbatim | Searches CDE text for exact + variant matches of all patterns | `discovered.tsv` |
| coalesce_patterns | Prefix trie subsumption + reverse subsumption with NP-continuity | `coalesced.tsv` |
| validate_subsumption | Empirical check: do shorter patterns actually cover more CDEs? | `validated.tsv` |
| enrich_fields | Adds def_count, desig_count, field_profile, example columns | `coalesced_fields.tsv` |
| **curator_review** | **Human checkpoint** | |
| strip_instruments | Removes curated patterns from CDE JSON | `inst_stripped.json` |
| sanity_check | Scans stripped output for remaining instrument-like text | `sanity_check.tsv` |

---

## 2. Running Phase 1

### Via scaffold script

```bash
./run_pipeline.sh phase1
```

### Via workflow directly

```bash
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
    --set "input_json=/data/cdes.json" \
    --set "output_dir=/data/phase1_output" \
    --set "workers=4"
```

### Via config file (persistent overrides)

Create `phase1_output/instrument_stripping_config.yaml`:

```yaml
input_json: /data/cdes.json
workers: 4
```

Then run without `--set`:

```bash
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
    --set "output_dir=/data/phase1_output"
```

The config file is auto-loaded from the output directory. See
[Pipeline Orchestration](pipeline-orchestration.md) for the full variable
resolution chain.

---

## 3. Understanding the Output

After the pipeline reaches the checkpoint, open `coalesced_fields.tsv` in the
built-in browser-based TSV editor:

```bash
cde-analyzer pattern_util --edit phase1_output/coalesced_fields.tsv
```

This is the file you will curate. When you are done, use **Save As** to write
the reviewed file as `phase1_output/curated.tsv`, then press Ctrl-C to stop
the server.

### Column reference

| Column | Description | Example |
|--------|-------------|---------|
| `pattern` | The matched text string | `Patient Health Questionnaire (PHQ-9)` |
| `tinyIds` | Pipe-separated CDE identifiers containing this pattern | `abc123\|def456\|ghi789` |
| `tinyid_count` | Number of unique CDEs containing this pattern | `3` |
| `type` | Detection source | `instrument`, `abbreviation`, `verbatim` |
| `source_pattern` | Original pattern before variant expansion | `Patient Health Questionnaire` |
| `example_name` | First matching CDE's primary designation (truncated to 120 chars) | `PHQ-9 Total Score` |
| `example_context` | Actual field containing the pattern, prefixed with source tag | `[des N] PHQ-9 Total Score` |
| `def_count` | Number of CDEs where pattern appears in definitions | `12` |
| `desig_count` | Number of CDEs where pattern appears in designations | `45` |
| `field_profile` | Which fields contain this pattern | `definition+designation` |

### What the counts tell you

- **High def_count + high desig_count**: Strong instrument signal — appears in
  both definitions and designations consistently. Almost always a true positive.
- **High desig_count, zero def_count**: Pattern appears only in designations
  (item text). Could be an instrument prefix or a sentence fragment.
- **Low counts (< 3)**: Rare pattern. May be noise unless it is a known
  instrument. Check the `example_*` columns.

---

## 4. Curation Decisions

### True instruments — strip

```tsv
Patient Health Questionnaire (PHQ-9)       abc|def|ghi     12    45    definition+designation
Neuro-QOL Positive Affect and Well-Being   jkl|mno          8    22    definition+designation
Berg Balance Scale                         pqr|stu          5    18    definition+designation
```

These are recognized assessment instruments. The example columns confirm they
appear in instrument-related context. Strip them.

### Verb fragments — skip

```tsv
think about         uvw|xyz     0     3     designation_only
mentally tired      aaa|bbb     0     2     designation_only
my sexual           ccc|ddd     0     4     designation_only
to your             eee|fff     0     5     designation_only
```

These contain verbs or pronouns (`think`, `tired`, `my`, `your`) and are
sentence fragments, not instrument names. They have zero definition counts
and low designation counts. Skip them.

!!! tip "Quick filter for verb fragments"
    Sort by `def_count` ascending. Patterns with `def_count=0` and
    `field_profile=designation_only` are the most likely false positives.
    Check the `example_context` column to confirm they are sentence fragments.

### Sub-domain families — strip both

```tsv
Neuro-QOL                                  jkl|mno|pqr     15    60    definition+designation
Neuro-QOL Positive Affect and Well-Being   jkl|mno          8    22    definition+designation
Neuro-QOL Sleep Disturbance                stu|vwx          6    19    definition+designation
```

The coalescer preserves both the family name (`Neuro-QOL`) and its sub-domain
variants (`Neuro-QOL Positive Affect and Well-Being`, etc.) thanks to the
NP-continuity guard. Both are valid — the family name catches CDEs that
reference the instrument generically, while sub-domain patterns catch
specific subscales.

### Partial names — investigate

```tsv
the Studies-Depression (CES-D)     ghi|jkl     3    0    definition_only
```

This looks like a fragment of "Center for Epidemiologic Studies-Depression
(CES-D)" where the prefix was lost during variant expansion. Check the
`source_pattern` column and the `coalesce_report.tsv` for subsumption details.

If the full name is already present as a separate pattern, you can safely
remove the fragment. If not, edit the pattern to restore the full name.

---

## 5. Supplementary Patterns

The instrument miner discovers patterns from CDE text. Some instruments may
be missed if they use unusual naming conventions. You can add them manually
through supplementary patterns.

### Global supplementary patterns

The file `config/supplementary_patterns.yaml` ships with the tool and
contains curated instrument names organized by section:

```yaml
clinical_instruments:
  - name: "Mini-Mental State Examination"
    acronym: "MMSE"
  - name: "Glasgow Coma Scale"
    acronym: "GCS"
```

### Local supplementary patterns

For project-specific additions, create `./supplementary_patterns.yaml` in
your working directory. The instrument miner loads both global and local files.

### Auto-harvesting from sanity check

After Phase 1 completes, `sanity_check.tsv` lists remaining instrument-like
text. You can auto-ingest these into your local supplementary file:

```bash
cde-analyzer pattern_util --harvest-to-supplementary sanity_check.tsv
```

This auto-generates names and acronyms, classifies into sections, and
deduplicates against existing patterns. A truncation guard rejects fragments
that start with a lowercase word or end with a single letter.

To promote local patterns to the global config:

```bash
cde-analyzer pattern_util --promote-supplementary
```

---

## 6. Iterative Harvesting

A single Phase 1 pass may not catch all instruments. The iterative
harvesting loop strips with current patterns, diagnoses residuals, harvests
new patterns, and repeats:

```
strip → diagnose → harvest → merge → [curate] → repeat
```

### Running iteration

With the scaffold script:

```bash
./run_pipeline.sh phase1_iterate       # default: 3 rounds
./run_pipeline.sh phase1_iterate 5     # up to 5 rounds
```

Or manually:

```bash
# Round 1: strip with curated patterns
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o iter_1_stripped.json \
    --patterns curated.tsv,pattern --workers 4

# Diagnose residuals
cde-analyzer diagnose_strip \
    -i iter_1_stripped.json -m CDE -o iter_1_sanity.tsv \
    --min-count 11 --suggest-patterns --emit-tinyids

# Harvest into supplementary
cde-analyzer pattern_util --harvest-to-supplementary iter_1_sanity.tsv

# Merge curated + harvested
cde-analyzer pattern_util --merge-patterns curated.tsv iter_1_sanity.tsv -o iter_1_merged.tsv
```

Review `iter_1_merged.tsv`, remove false positives, save as `curated.tsv`,
and repeat.

### Example progression (allcde01, 22,743 CDEs)

| Round | Curated patterns | Residuals | Notes |
|-------|-----------------|-----------|-------|
| Initial | 399 | 33 | First curation pass |
| Round 1 | 432 | 14 | +33 harvested, 0 removed |
| Round 2 | 444 | 13 | +12 harvested, 2 removed |
| Final | 444 | 13 | Remaining residuals are NIH Toolbox sub-domains (NP-continuity edge case) |

### Dynamic min-count

The scaffold script calculates `min_count` dynamically based on corpus size:

```
min_count = max(round(N * 0.0005), 5)
```

For allcde01 (N=22,743): `min_count=11`. For a 1,148-CDE dataset: `min_count=5`.
This filters low-frequency noise while retaining real instruments.

---

## 7. Field-Aware Splits for Branching Strip

After curation, the branching strip (Phase 3) needs separate **inst_full** and
**inst_sub** pattern files to produce all 7 strip variants. The
`--analyze-instrument-splits` command prepares a curation TSV that proposes how
to split each curated instrument pattern into a group prefix (inst_full) and a
separator+suffix (inst_sub).

### How separators are detected

The hierarchy grouper identifies groups of patterns sharing a common prefix.
The separator between prefix and suffix varies by instrument family:

| Pattern | Group | proposed_full | proposed_sub | Separator |
|---------|-------|--------------|-------------|-----------|
| `PROMIS - Anxiety` | PROMIS | `PROMIS` | ` - Anxiety` | ` - ` |
| `PROMIS - Depression` | PROMIS | `PROMIS` | ` - Depression` | ` - ` |
| `NIH Toolbox - Flanker` | NIH Toolbox | `NIH Toolbox` | ` - Flanker` | ` - ` |
| `NIH Toolbox Anger` | NIH Toolbox | `NIH Toolbox` | ` Anger` | ` ` (space) |
| `NIH Toolbox Cognitive Battery` | NIH Toolbox | `NIH Toolbox` | ` Cognitive Battery` | ` ` (space) |

The separator is always included as prefix to `proposed_sub`. This ensures that
when both inst_full and inst_sub are applied (MTSTPF/MTSTPT), the complete
pattern text is fully consumed with no dangling separator.

### Mixed separators within a group

Some instrument families use **both** dash-separated and space-separated naming.
The NIH Toolbox group illustrates this:

- `NIH Toolbox - Anger` → sub = ` - Anger` (dash separator)
- `NIH Toolbox Anger` → sub = ` Anger` (space separator)

Both are valid group members with the same `proposed_full = "NIH Toolbox"`.
The splits approach handles this naturally because the separator is detected
per-pattern, not per-group.

### Why this matters for stripping

Consider a definition field containing:

> "..., as part of the NIH Toolbox Anger Physical Aggression"

The curated pattern is `NIH Toolbox Anger` (the longest match the miner found).
With field-aware splits:

- **MTSFPF** (inst_full only): removes `NIH Toolbox` → `" Anger Physical Aggression"`
- **MFSTPF** (inst_sub only): removes ` Anger` → `"NIH Toolbox Physical Aggression"`
- **MTSTPF** (both): removes `NIH Toolbox` + ` Anger` → `" Physical Aggression"`

The remaining text ("Physical Aggression") was never part of the curated
instrument pattern — it is CDE-specific content that should be preserved.
Each variant produces a genuinely different result, which is the goal of
field-aware splits.

### Singletons

Patterns that are not part of any group (193 in allcde03) are classified as
**singletons**. They go into inst_full only (the complete match) with nothing
in inst_sub. For singletons, MTSFPF and MTSTPF produce the same output — this
is expected and correct, since there is no sub-component to strip independently.

### Three-component decomposition

Each curated instrument pattern is decomposed into up to three components:

| Component | Description | Example |
|-----------|-------------|---------|
| **Full** (inst_full) | Group prefix — the instrument family name | `PROMIS` |
| **Sub** (inst_sub) | Separator + suffix — the sub-domain identifier | ` - Anxiety` |
| **Abbreviation** | Parenthesized acronym (future use) | `(PHQ-9)` |

For **singletons** (patterns not part of any group), the complete match goes
into inst_full with nothing in inst_sub. For **group bases** (e.g., `PROMIS`
itself), similarly only inst_full is populated.

The separator (` - `, ` `, etc.) is always included as prefix to the sub
component. This ensures that applying both inst_full and inst_sub fully
consumes the original pattern text with no dangling separator.

### Group-scoped re-matching

When generating strip patterns, sub-pattern texts are re-matched against CDE
fields to find all CDEs where they appear. A critical constraint: **sub-patterns
are only matched against CDEs within their instrument group's tinyId scope**.

Without this scoping, a bare-word sub-pattern like `Assessment` (from the group
`Vineland Adaptive Behavior Scales Assessment`) would match hundreds of unrelated
CDEs containing the common word "Assessment". This cross-instrument contamination
causes stripping artifacts (double-space gaps) in CDEs that should not be affected.

The group-scoped approach builds a `sub_text_scopes` dict mapping each proposed_sub
text to the union of tinyIds from its instrument group(s). During re-matching,
each sub-pattern text is only scanned against CDEs in its scope, not the full
corpus.

**QC validation** (allcde03, v3 strip patterns): Group-scoped re-matching reduced
double-space artifacts from 20 (v2, unscoped) to 0 (v3, scoped) across all 7
branching strip variants.

### Workflow

```bash
# 1. Analyze splits from curated instruments
cde-analyzer pattern_util --analyze-instrument-splits curated.tsv \
    --input cdes.json -o instrument_splits.tsv

# 2. Curate in TSV editor (review group_member rows)
cde-analyzer pattern_util --edit instrument_splits.tsv

# 3. Generate separate inst_full and inst_sub pattern files
#    (--input enables group-scoped re-matching for sub-patterns)
cde-analyzer pattern_util --generate-strip-patterns instrument_splits.tsv \
    --input cdes.json -o inst_patterns
# → produces inst_patterns_full.tsv and inst_patterns_sub.tsv

# 4. Run 7-way branching strip
cde-analyzer strip_branching -i cdes.json -d output/ \
    --inst-full-patterns inst_patterns_full.tsv \
    --inst-sub-patterns inst_patterns_sub.tsv \
    --temporal-patterns temporal_expanded.tsv \
    --phrase-patterns curated_phrases.tsv
```

### Curation decisions for semantic retention

During instrument split curation, some patterns require **substitute** or
**modify** decisions to preserve semantic content:

- **Substitute**: When deleting the matched text would leave broken grammar or
  lose meaning, replace it with a shorter semantically equivalent phrase. For
  example, substituting a full instrument preamble with just the instrument
  abbreviation preserves the reference without the boilerplate.

- **Modify**: When the detected pattern boundaries are wrong — the match is too
  long or too short. Correct the boundaries so that only the true boilerplate
  is stripped.

The key principle: stripping should remove **noise** (repeated instrument names,
boilerplate preambles) without destroying **signal** (clinical content, semantic
meaning). When in doubt, use substitute to replace rather than delete.

---

## 9. Tuning Parameters

| Parameter | Default | When to change |
|-----------|---------|---------------|
| `workers` | 0 (auto) | Set to 4-8 for large datasets; 0 is fine for <5K CDEs |
| `extract_supplementary` | `true` | Must be `true` in YAML for supplementary patterns to work |
| `min_prefix_tinyids` | 2 | Coalescer prefix threshold; rarely needs changing |
| `min_count` (diagnose) | 2 | Use dynamic formula for iteration; raise for large corpora |

See [Parameter Tuning](parameter-tuning.md) for comprehensive guidance on
dataset-size-specific settings.

---

## 10. Common Issues

### Trailing-punctuation trie truncation

**Symptom**: A pattern like `Neuro-QOL Positive Affect and Well-Being` gets
truncated to `Neuro-QOL Positive Affect and`.

**Cause**: The Phase 2 prefix trie split `Well-Being` and `Well-Being.`
(with trailing period) into separate branches.

**Fix**: This was fixed in v0.5.12. If you see truncated patterns, ensure
you are running the latest version.

### NP-continuity false drops

**Symptom**: Sub-domain patterns like `NIH Toolbox Cognitive Battery` are
dropped during reverse subsumption, leaving only the short form `NIH Toolbox`.

**Cause**: The NP-continuity guard checks whether the extension tail is
noun-phrase-like (80%+ Title Case words). Some edge cases fail this heuristic.

**Workaround**: Manually add the dropped pattern back during curation.
The empirical subsumption validation step (`validate_subsumption`) catches
most of these, but a few may slip through.

### Definition-form variant residuals

**Symptom**: After stripping, residual articles appear in the output:
`the`, `the and`, `a`.

**Cause**: When "Center for Epidemiologic Studies-Depression (CES-D) -" is
stripped from a designation, and "Center for Epidemiologic Studies-Depression
(CES-D)" is stripped from a definition starting with "the Center for...",
the leading article remains.

**Resolution**: These are expected artifacts. The Phase 3 `--clean-remnants`
flag handles most of them automatically. See
[Lessons Learned](../appendix/lessons_learned_20260129.md#5-sanity-check-residuals-are-diagnostic-not-failures)
for details.
