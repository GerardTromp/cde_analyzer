# Session Notes (read after compacting)

## Current Work: Instrument Detection Pipeline Enhancements

### Working Directory
```
/mnt/d/GT/Professional/NLM_CDE/work_202601/cde_repository/scheuerman01
```

### Key Files
- **Subset JSON**: `cdes_subset.json` (1148 CDEs from curated_domains_1148_firstcategory.csv)
- **Source JSON**: `../cde_all_04_20260105_no-phrases.json` (22743 CDEs)
- **Output dir**: `phase1_output/`
- **Test patterns**: `test_patterns.txt` (7 regex patterns with labels)
- **Recall report TSV**: `recall_report_v1.tsv` (metrics per family)
- **Recall report MD**: `recall_analysis_report.md` (human-readable with version history)
- **False negatives**: `false_negatives_v1.txt` (missing tinyIds by family)

### Current Recall Results (v1)
**Overall Recall: 83.3%** (110/132 captured)

| Family | Source | Captured | Missing | Recall | Status |
|--------|-------:|--------:|--------:|-------:|--------|
| HAM-A | 1 | 1 | 0 | 100% | ✓ Complete |
| HDRS | 19 | 19 | 0 | 100% | ✓ Complete |
| PROMIS | 22 | 22 | 0 | 100% | ✓ Complete |
| PROMIS-EDD | 28 | 28 | 0 | 100% | ✓ Complete |
| CES-D | 21 | 20 | 1 | 95.2% | ○ Good |
| GDS | 33 | 18 | 15 | 54.5% | ✗ Low |
| PHQ | 8 | 2 | 6 | 25.0% | ✗ Low |

**Next Steps**: Investigate GDS (15 missing) and PHQ (6 missing) false negatives

---

## Recall Analysis: GDS/PHQ Root Cause (In Progress)

### Key Finding
**100% of missing CDEs (22 total) lack the "as part of" anchor pattern.**

All missing CDEs have instrument names directly in the **designation** without the "as part of" anchor:
- GDS (15): `Geriatric Depression Scale (GDS) Long Form - <Item>`
- PHQ (6): `Patient Health Questionnaire (PHQ-9) ...` variants
- CES-D (1): `Center for Epidemiologic Studies Depression Scale (CES-D) - total score`

### Pipeline Has `discover_bare_names: true`

The workflow (line 176) enables bare name discovery, which SHOULD find these CDEs. However:

1. **PHQ Issue**: Bare name `"Patient Health Questionnaire (PHQ)"` generates regex `Patient\s+Health\s+Questionnaire\s*\(PHQ\)` which does NOT match `(PHQ-9)` or `(PHQ-2)` - the parenthetical content is matched literally.

2. **GDS Issue**: Bare name `"Geriatric Depression Scale"` DOES match `"Geriatric Depression Scale (GDS) Long Form"` as a prefix. Need to verify why these tinyIds aren't in pipeline output.

### Enhanced Patterns Solution

Created `enhanced_patterns.txt` with explicit patterns:
```
Geriatric[ -]Depression[ -]Scale[ -]\(GDS\)[ -]Long[ -]Form	GDS-LF
Patient[ -]Health[ -]Questionnaire[ -]\(PHQ-9\)	PHQ-9
Patient[ -]Health[ -]Questionnaire[ -]\(PHQ-2\)	PHQ-2
Patient[ -]Health[ -]Questionnaire[ -]Depression[ -]\(PHQ\)	PHQ
Patient[ -]Health[ -]Questionnaire[ -]\d+[ -]item	PHQ
Center[ -]for[ -]Epidemiologic[ -]Studies[ -]Depression[ -]Scale[ -]\(CES-D\)	CES-D
```

**Tested**: All 22 missing CDEs captured (44 total matches including overlaps).

### Verification: discover_bare_names Won't Help

**Checked workflow state**: Pipeline paused at Phase 1 checkpoint (step 4). Discovery step (step 5 with `discover_bare_names: true`) hasn't run yet.

**Examined instruments_verbatim.tsv full_match patterns:**
- GDS: `"as part of the Geriatric Depression Scale Long Form"` → bare name: "Geriatric Depression Scale Long Form"
- PHQ: `"as part of the Patient Health Questionnaire (PHQ)"` → bare name: "Patient Health Questionnaire (PHQ)"

**Why running discovery won't help:**
1. **GDS**: Bare name "Geriatric Depression Scale Long Form" generates regex expecting "Scale Long" adjacency, but missing CDEs have `(GDS)` in between: "Scale (GDS) Long Form"
2. **PHQ**: Bare name with `(PHQ)` generates regex requiring literal `(PHQ)`, won't match `(PHQ-9)` or `(PHQ-2)`

**Conclusion**: The enhanced_patterns.txt solution is necessary - the pipeline's `discover_bare_names` feature cannot handle embedded abbreviation parentheticals.

### Recommended Solutions
1. **Immediate**: Add enhanced_patterns.txt patterns to curated.tsv for next discovery run
2. **Future Enhancement**: Modify `make_flexible_regex()` to handle `(ABBREV-N)` variants:
   - Convert `(PHQ)` to `(PHQ(?:-\d+)?)`
   - Insert optional `\s*\([A-Z]+(?:-\d+)?\)\s*` between words

### TODO: Pipeline Enhancements

**TODO 1: Automated Enhanced Pattern Discovery**
When recall report shows high false negatives, automate the discovery of enhanced patterns programmatically (no LLM):
- Analyze false negative designations to extract common prefix patterns
- Detect embedded abbreviation parentheticals `(ABBREV)` or `(ABBREV-N)` in designations
- Generate candidate patterns by:
  1. Tokenizing designation prefixes up to first delimiter (hyphen, colon, score indicator)
  2. Identifying abbreviation patterns: `\([A-Z]+-?\d*\)`
  3. Building flexible regex that accounts for embedded abbreviations
- Add as new action: `pattern_suggest` or integrate into `recall_analyze --suggest-patterns`
- Trigger automatically when family recall < threshold (e.g., 70%)

**TODO 2: Enhance `make_flexible_regex()` in `utils/flexible_pattern_matcher.py`**
Modify to handle abbreviation parenthetical variants:
- When pattern contains `(ABBREV)`, convert to `(ABBREV(?:-\d+)?)`
- Option to insert optional abbreviation placeholder between words: `\s*(?:\([A-Z]+(?:-\d+)?\)\s*)?`
- Add parameter: `allow_embedded_abbrev: bool = False`
- Example: "Patient Health Questionnaire (PHQ)" → matches "Patient Health Questionnaire (PHQ-9)"

**TODO 3: Markdown Recall Reports in Pipeline Phases**
Integrate markdown report generation into the workflow for non-technical audience presentation:
- **Per-Phase Reports**: Each pipeline phase should generate a versioned markdown recall report
  - Phase 1 (Mining): Initial instrument patterns discovered
  - Phase 2 (Discovery/Coalesce): Verbatim patterns with subsumption analysis
  - Phase 3 (Family Analysis): Family groupings and re-discovery results
  - Phase 4 (Stripping): Final stripped output with sanity check summary
- **Versioned History**: Each report tracks iteration history (v1, v2, etc.)
- **Final Summary Report**: Pipeline completion generates consolidated summary markdown:
  - Executive summary with overall metrics
  - Phase-by-phase progression table
  - Recall improvement trajectory
  - Quality assurance notes (sanity check findings)
  - Recommendations for next steps
- **Implementation**:
  - Add `--phase-report` option to relevant actions or workflow steps
  - Workflow variables: `${phase1_report_md}`, `${phase2_report_md}`, etc.
  - Final step generates `pipeline_summary.md` combining all phase data
- **Target Audience**: Curators, domain experts, stakeholders (non-technical)

### Analysis Files Created
- `recall_improvement_analysis.md` - Full analysis document
- `enhanced_patterns.txt` - Patterns to capture missing CDEs
- `test_bare_names.py` - Test bare name extraction/matching
- `test_phq_matching.py` - Test PHQ regex matching

---

## Four-Step Enhancement Plan - ALL COMPLETED

### Step 1: Subset Tool Enhancement ✓
**Files Modified:**
- `actions/subset/cli.py` - Added `--pattern-file`, `--match-report`, `--tinyid-report`
- `actions/subset/run.py` - Added pattern file handling branch
- `logic/subset.py` - Added `subset_by_pattern_file()`, `load_patterns_from_file()`, `write_match_report()`, `write_tinyid_report()`

**Pattern File Format:**
```
# Comments start with #
pattern<TAB>label
Hamilton[ -]Anxiety[ -]Rating[ -]Scale	HAM-A
Geriatric[ -]Depression[ -]Scale	GDS
```

### Step 2: Recall Analyze Action ✓
**New Action Created:** `recall_analyze`
- `actions/recall_analyze/__init__.py`
- `actions/recall_analyze/cli.py`
- `actions/recall_analyze/run.py`
- Registered in `cde_analyzer.py`

**Features:**
- Compares source pattern matches against pipeline output
- Groups results by instrument family
- Reports recall metrics (source_count, pipeline_count, missing_count, recall)
- Outputs false negatives grouped by family for curation

**Test Results**: See "Current Recall Results" section above

### Step 3: Stopping Criterion ✓
**Added to recall_analyze:**
- `--previous-report` - Compare with previous iteration
- `--stopping-threshold` - Marginal gain threshold (default: 2)

**Features:**
- Computes delta CDEs between iterations
- Shows per-family gains
- Flags when stopping criterion met (marginal gain <= threshold)

### Step 4: Markdown Report ✓
**Added to recall_analyze:**
- `--markdown-report` - Path to output markdown report
- `--report-version` - Version label (e.g., "v1", "iteration-2")
- `--report-title` - Custom report title

**Report Structure:**
1. **Summary** - Overall metrics table, families at 100%, below threshold
2. **Iteration Status** - Stopping criterion message, comparison reference
3. **Recall by Family** - Sorted table with status indicators (✓ ○ △ ✗)
4. **Iteration Gains** - Delta table when comparing versions
5. **Details by Family** - Per-family sections with patterns and missing tinyIds
6. **Version History** - Accumulated across runs with date, recall, notes

**Status Indicators:**
- ✓ Complete (100%)
- ○ Good (≥90%)
- △ Needs Work (≥70%)
- ✗ Low (<70%)

---

## Example Commands

```bash
# Pattern file subset
cde-analyzer subset -i cdes_subset.json -m CDE -o matched.json \
    --pattern-file patterns.txt \
    --match-report match_report.tsv

# Recall analysis with markdown report
cde-analyzer recall_analyze -i cdes_subset.json -m CDE \
    --pattern-file test_patterns.txt \
    --pipeline-output phase1_output/instruments.tsv \
    --pipeline-tinyid-column tinyids \
    -o recall_report.tsv \
    --false-negatives-file false_negatives.txt \
    --markdown-report recall_report.md \
    --report-version v1 \
    --min-recall 0.9

# Subsequent iteration with version history
cde-analyzer recall_analyze -i cdes_subset.json -m CDE \
    --pattern-file test_patterns.txt \
    --pipeline-output phase1_output/instruments.tsv \
    --pipeline-tinyid-column tinyids \
    -o recall_report_v2.tsv \
    --markdown-report recall_report.md \
    --report-version v2 \
    --previous-report recall_report.tsv \
    --stopping-threshold 2
```

---

## Workflow Updates ✓

### instrument_detection.yaml - Updated
Added recall analysis variables and documentation:
- `recall_patterns` - Ground truth pattern file (optional)
- `recall_tinyid_column` - Column name for tinyIds (default: tinyids)
- `recall_report_tsv` - TSV output path
- `recall_report_md` - Markdown report path

**Completion checkpoint** now includes recall analysis instructions:
```bash
cde-analyzer recall_analyze -i ${input_json} -m CDE \
    --pattern-file <ground_truth_patterns.txt> \
    --pipeline-output ${final_coalesced} \
    --pipeline-tinyid-column tinyids \
    -o ${recall_report_tsv} \
    --markdown-report ${recall_report_md} \
    --report-version final \
    --min-recall 0.9
```

**TODO**: Update other workflows (instrument_pipeline.yaml, phrase_pipeline.yaml, etc.) with markdown report documentation when fully tested.

---

## Semantic Grouping & Boundary Detection Architecture

### Overview

`pattern_util --group-semantic` annotates a patterns TSV with group membership based on shared prefix spans, using SpaCy NLP to prevent overshooting into content-bearing tokens.

**Module**: `logic/span_boundary.py` (algorithm) + `actions/pattern_util/{cli,run}.py` (CLI integration)

### Four-Stage Pipeline

```
Input patterns TSV (pattern + tinyIds columns)
  │
  ├─ Stage 1: Word-level prefix grouping
  │    Lexicographic sort → adjacent LCP computation → greedy group extension
  │    Parameters: --min-group-size (default 2), --min-prefix-words (default 2)
  │
  ├─ Stage 2: SpaCy POS-based boundary trimming
  │    For each group prefix, parse in context of the longest pattern (avoids
  │    fragment mis-parsing). Trim trailing function words right-to-left:
  │      PRON, DET, CCONJ, SCONJ, PART, PUNCT → always trim
  │      ADP → trim only if no content children within prefix
  │      NOUN, VERB, NUM, ADJ, PROPN, ADV → stop
  │    Example: "in the past 7 days I" → "in the past 7 days"
  │    Groups that collapse to the same trimmed prefix are merged.
  │
  ├─ Stage 3: SemanticGroup assembly
  │    Build SemanticGroup(trimmed_prefix, patterns, merged_tinyids)
  │    Dedup patterns, merge tinyId sets across merged groups.
  │
  └─ Stage 4: Semantic classification
       classify_group() checks each prefix against known semantic types.
       Currently supports: "temporal" (temporal frame boilerplate).
       Classified groups get super_group label and normalized temporal label
       (e.g., "in the past N days") for cross-quantifier grouping.
```

### Temporal Detection Design

**Challenge**: Temporal frames like "In the past 7 days" and "In the past 30 days" share boilerplate but differ in quantifier. They should group together as a super-group.

**Regex**: `_TEMPORAL_FRAME_RE` matches `[prep] the [past|last] [N] [time_unit]` where N is an arabic numeral, number word, or absent (implied-one). Supports prepositions: in, over, during, for, within.

**Classification thresholds**: The `classify_group()` function uses two confidence levels:
- **Direct match** (prefix is a full temporal frame): always classified
- **Partial match with "past"/"last" in prefix**: 50% threshold (high confidence from keywords)
- **Partial match without "past"/"last"** (e.g., "in the"): 90% threshold (ambiguous — could be locative)

This 90% threshold was validated against test data where "in the" (7 patterns, ~71% temporal) was correctly excluded as non-temporal, while "In the past" and "In the last" groups were correctly classified.

**Normalization**: `normalize_temporal_prefix()` replaces the quantifier with "N" and lowercases, so "In the past 7 days" and "In the past 30 days" collapse to "in the past N days". Handles partial prefixes by extracting the full frame from a representative pattern.

### Implied-ONE Heuristic (No-Quantifier Variants)

**Problem**: A 1/20th subset discovers temporal frames with specific quantifiers (e.g., "In the past 7 days") but misses the singular/implied-ONE form ("In the past day", "In the past week") that exists on different CDE records.

**Solution** (`generate_temporal_no_quantifier()`): For each discovered quantified temporal frame, generate the implied-ONE form by stripping the numeric quantifier and singularizing the time unit:
- "In the past 7 days" → "In the past day"
- "Over the last 2 weeks" → "Over the last week"

**Key insight**: Implied-ONE variants exist on *different* CDE records than their quantified counterparts. They cannot share tinyIds — they need separate unrestricted discovery. This was learned empirically: inheriting tinyIds from quantified frames caused a *decrease* in stripping coverage (81.9% vs 87.6%) because the tinyId restriction prevented matches on the correct records.

**Default behavior**: `--group-semantic` emits implied-ONE variants by default (marked with `implied=yes` column). Use `--no-temporal-implied` to suppress.

**Validation results** (scheuermann04 1/20th subset, 1148 CDEs):
- Without implied variants: 87.6% temporal removal (489/558)
- With implied variants (separate discovery): 97.3% temporal removal (543/558)
- Remaining 15 have specific quantifiers not in subset (12 months, 4 weeks, etc.)

### Output Format

TSV sorted: temporal groups first (by normalized label, then prefix, then pattern), then non-temporal groups, then ungrouped patterns.

Columns: `temporal_group | group_prefix | [original columns] | group_size | group_tinyid_count | implied`

Implied-ONE rows have `implied=yes`, empty tinyIds (need separate discovery pass), and inherit the temporal_group/group_prefix of their source group.

---

## Anchor Trimming & Group/Sub-Group Design (Phase 1 Instruments)

### Anchor Trimming — COMPLETED
Added `trim_anchors: bool = True` to `coalesce_variants_tsv()` (Phase 0, runs before subsumption).
- Default ON, disable with `--no-trim-anchors`
- Two-path extraction: prefix-only (`extract_bare_instrument_name()`) then mid-pattern regex
- Mid-pattern regex: `r'(?:^|.*?\b)(anchor)\s+'` finds anchors anywhere in pattern
- Strips optional leading article after anchor
- Merges tinyIds when bare name already exists, propagates parent info
- **Test results**: 333 → 111 patterns (110 anchor-trimmed, 91 subsumed, 53 prefix-extracted)
- Zero "as part of" patterns remain in output; `--no-trim-anchors` preserves 34

### Group / Sub-Group Hierarchy — COMPLETED
**Module**: `logic/group_hierarchy.py` + `--group-hierarchy` on `pattern_util`

**Algorithm**: Reuses `build_prefix_groups()` from span_boundary, strips trailing delimiters (`[-:;,.\s]+`) from group names, merges groups that collapse to the same cleaned name.

**Output columns**: `group`, `sub_group`, `suffix`, `group_size`, `group_tinyid_count`
- `group` = cleaned main instrument name (e.g., `PROMIS`)
- `sub_group` = full pattern (e.g., `PROMIS - Sleep Disturbance`)
- `suffix` = distinguishing part after prefix (e.g., `Sleep Disturbance`)

**Filtering**: `--min-tinyids N` drops patterns with < N tinyIds before grouping (noise removal).

**Test results** (111 coalesced patterns, no filter):
- 4 groups, 13 grouped, 98 ungrouped
- PROMIS (4 sub-groups, 36 tinyIds), Scale related to (3, 45), The scale (3, 31), Indicates how often (3, 20)

**Test results** (with `--min-tinyids 3`):
- Filtered 63 noise patterns, 4 groups remain, 12 grouped, 36 ungrouped

**Substitution strategies this enables**:
1. **Sub-group**: Replace with specific sub-instrument label
2. **Group**: Replace with main instrument label only
3. **Both**: Two-pass — sub-group first, then group catches remaining

**Future**: `detect_abbreviation_variants()` stub for abbreviation stem detection (e.g., PROMIS-SF, PROMIS-29 share stem PROMIS)

---

## Iterative Discovery Session: scheuermann06 (2026-01-29)

### Problem
After standard pipeline, many instrument names survive in Name/Definition fields.
Manual CSV inspection → identify surviving patterns → code fix → re-run → repeat.

### Iteration Log

| Iter | Change | Patterns | Paren Fields | Name Rows | Key Gains |
|------|--------|----------|--------------|-----------|-----------|
| 0 | Baseline (mine→expand→discover→coalesce) | 86 | 404 | 97 | — |
| 1 | Fix roll-down: min 2-word base | 86 | 354 | — | CES-D partial |
| 2 | Disable prefix extraction (min=9999) | 86 | 294 | 87 | CES-D full |
| 3 | Add `(ABBREV) -` discovery (known abbrevs) | 107 | 310 | ~80 | Neuro-Qol, HDRS, PIMS, MSQOL-54 |
| 4 | Fix rollup-subset: require substring match | 133 | 292 | ~80 | SCS(7), SWAL-QOL(2), SF-36(1) |
| 5 | Open `(ANYABBREV) -` scan (unknown abbrevs) | 137 | 236 | 22 | GDS(33→0), CHAT(15→0) |

### Code Changes Made
1. `utils/flexible_pattern_matcher.py` — roll-down min 2-word check (iter 1)
2. `utils/flexible_pattern_matcher.py` — rollup-subset requires substring match (iter 4)
3. `actions/strip_discover/run.py` — Pattern 3: `(ABBREV) -` for known abbreviations (iter 3)
4. `actions/strip_discover/run.py` — Pattern 4: open `(ANYABBREV) -` scan (iter 5)

### Gap Categories
1. **Code bugs**: Roll-down/rollup logic errors (iter 1, 4)
2. **Algorithm limitations**: Prefix extraction too aggressive (iter 2)
3. **Missing pattern types**: `(ABBREV) -` never searched (iter 3, 5)
4. **Edge cases** (remaining 22): `?` separator (ACE), name variants (NMSS), positional (PHQ-9)

### Remaining After Iter 5 (22 Name rows)
- NMSS(3): Name has "assessment Parkinson's Disease" but pattern has "assessment scale for Parkinson's Disease"
- PHQ-9(3): `(PHQ-9)` at start of string, no ` - ` separator
- ACE(2): Uses `?` not ` - ` as separator
- IVR(2), PHQ(2), SCAT3(2), WHOQOL-BREF(2): Not in instruments.tsv, < min_pattern_tinyids
- 14 singletons: Various instruments with 1 occurrence each

### Key Lesson
Discovery needs to be **semi-automated and iterative**. After each strip, a diagnostic scan reveals surviving patterns. This scan→fix→re-strip loop should be a first-class workflow step. See TODO.md for semi-automation plan.

---

## WSL Command Pattern
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```
