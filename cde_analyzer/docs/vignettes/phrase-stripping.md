# Vignette: Phrase Stripping

A step-by-step tutorial for removing boilerplate phrases from CDE text fields.

## What This Vignette Covers

CDE records often contain repeated boilerplate text — instrument names, temporal
frames ("in the past 7 days"), response prompts, and definition templates — that
obscures the underlying semantic content. The phrase stripping pipeline detects
these patterns and removes them, producing cleaner text for embedding and
clustering.

This vignette walks through **six progressively complex scenarios**, from a
minimal single-command strip to a full production pipeline with temporal
grouping. Each scenario builds on the previous one.

**Prerequisites**: A JSON file of CDE records and a Python environment with
`cde-analyzer` installed. All examples assume you are running from the
`cde_analyzer/` directory.

**Related documentation**:

- [strip_phrases reference](../help/strip_phrases.md) — complete flag reference
- [pattern_util reference](../help/pattern_util.md) — TSV manipulation utilities
- [strip_discover reference](../help/strip_discover.md) — pattern discovery
- [Curation Guide](../curation-guide.md) — decision guidelines for human review
- [Full Workflow](../workflows/instrument-phrase-stripping-workflow.md) — multi-phase overview

---

## Scenario 1: Minimal Strip (One Command)

**Goal**: You already have a curated patterns TSV and want to strip it from
your CDE JSON in a single command.

**When to use**: Quick experiments, re-running a previously curated strip,
or applying someone else's curated patterns to your dataset.

### Input files

- `cdes.json` — CDE records (array of JSON objects)
- `patterns.tsv` — Two-column TSV with `pattern` and `tinyIds` headers

```tsv
pattern	tinyIds
Patient Health Questionnaire	abc123|def456|ghi789
in the past 7 days	xyz111|xyz222|xyz333
```

### Command

```bash
cde-analyzer strip_phrases \
    -i cdes.json \
    -m CDE \
    -o cdes_stripped.json \
    --patterns patterns.tsv
```

### What happens

1. Loads all CDE records and validates them against the `CDE` Pydantic model
2. Reads patterns from the TSV — each pattern is an exact string to remove
3. Sorts patterns longest-first (default `--sort-order length`) so that
   `Patient Health Questionnaire (PHQ-9)` is matched before `Patient Health
   Questionnaire`
4. For each CDE, scans `definitions.*.definition` and
   `designations.*.designation` (the default fields)
5. Replaces matched text with empty string, normalizes whitespace
6. Writes cleaned output to `cdes_stripped.json`

### Checking the result

Add `--diff --color --summary` to see what changed:

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o cdes_stripped.json \
    --patterns patterns.tsv \
    --diff --color --summary
```

This prints a colorized diff showing every modification, plus a summary line
count. To save the diff to a file instead:

```bash
    --diff-output strip_diff.txt
```

---

## Scenario 2: Strip with Cleanup and Diagnostics

**Goal**: Strip patterns and automatically clean up the mess left behind
(orphan articles, dangling punctuation), then produce an audit trail.

**When to use**: Production stripping where you need clean output and want
to verify what was removed.

### The remnant problem

Stripping a phrase from the middle of a sentence often leaves artifacts:

```
Before: "The total score as part of the Patient Health Questionnaire was computed."
After:  "The total score as part of the  was computed."
                         ^^^^^^^^^^^^     ← orphan "as part of the"
```

The `--clean-remnants` flag applies iterative normalization to fix these.

### Command

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o cdes_clean.json \
    --patterns patterns.tsv \
    --clean-remnants \
    --remnant-report remnants.tsv \
    --match-log matches.tsv \
    --match-summary match_summary.tsv
```

### What each flag does

| Flag | Purpose |
|------|---------|
| `--clean-remnants` | After stripping, iteratively remove orphan articles ("the", "a"), floating punctuation, empty parentheses, dangling prepositions |
| `--remnant-report FILE` | Write any *remaining* artifacts to a TSV (runs after cleanup, so this measures residual issues) |
| `--match-log FILE` | Full audit trail: every match with tinyId, matched pattern, source pattern, verbatim text |
| `--match-summary FILE` | Aggregated counts: how many times each pattern was stripped across how many records |

### Reading the match summary

The `match_summary.tsv` shows you which patterns are doing the most work:

```tsv
source_pattern              match_count  unique_records
Patient Health Questionnaire    47          23
in the past 7 days              31          31
```

If a pattern has `match_count=0`, it exists in your patterns file but never
matched anything — either it was already stripped in a prior pass, or the
tinyIds don't overlap with your input records.

### Reading the remnant report

The `remnants.tsv` lists any artifacts that survived cleanup:

```tsv
tinyId    field       remnant_type         snippet
abc123    definition  orphan_article       "...the  was computed..."
```

In testing on 22,743 CDEs, `--clean-remnants` reduced 7,652 remnants to 6
(99.9% reduction). The residual report helps you decide if manual fixes are
needed for the remaining few.

---

## Scenario 3: Discover-Then-Strip Workflow

**Goal**: You don't have a curated patterns file yet. Start from raw phrase
mining output and work through discovery, coalescing, and filtering before
stripping.

**When to use**: First-time analysis of a new dataset. This is the standard
production workflow.

### Step 1: Mine phrases

Find repeated multi-word phrases in your CDE text:

```bash
cde-analyzer phrase_miner \
    -i cdes.json \
    -o mining_output/ \
    --enable-subsumption
```

**Output**: `mining_output/verbatim_phrases.tsv` — raw phrases with
`verbatim_text`, `lemma_text`, `tinyIds` columns.

This uses k-mer analysis to find repeated substrings (default: 3–25 tokens).
The `--enable-subsumption` flag removes shorter phrases that are always found
inside longer ones. If your data contains phrases longer than 25 words, add
`--k-max 35` — see [Extending k-mer range](#example-extending-k-mer-range-for-long-phrases)
in Scenario 5.

### Step 2: Discover verbatim patterns

The miner finds lemmatized phrases. Now find their exact surface forms in the
CDE text:

```bash
cde-analyzer strip_discover \
    -i cdes.json -m CDE \
    -o discovered.tsv \
    --pattern-list mining_output/verbatim_phrases.tsv,verbatim_text \
    --expand-variants \
    --parent-column lemma_text \
    --workers 0
```

**Key flags**:

- `--pattern-list FILE,COLUMN` — reads patterns from the `verbatim_text`
  column of the mining output
- `--expand-variants` — generates spelling/punctuation variants (with/without
  hyphens, different spacing) to catch all surface forms
- `--parent-column lemma_text` — tracks which generic (lemmatized) phrase each
  verbatim form belongs to (used for downstream filtering)
- `--workers 0` — auto-detect CPU count for parallel processing

**Output**: `discovered.tsv` — every verbatim occurrence with `pattern`,
`tinyIds`, `type`, `source_pattern` columns.

### Step 3: Coalesce redundant patterns

Many discovered patterns overlap. Coalescing removes shorter patterns that are
subsumed by longer ones:

```bash
cde-analyzer pattern_util --coalesce-variants discovered.tsv \
    -o coalesced.tsv \
    --coalesce-report subsumption_report.tsv \
    --min-prefix-tinyids 2 \
    --min-parent-tinyids 20
```

**What coalescing does**:

1. **Text subsumption**: If "past 7 days" is always found inside "in the past
   7 days" (same tinyIds), the shorter pattern is removed
2. **Prefix extraction**: Groups like "Neuro-QOL Lower Extremity Function" and
   "Neuro-QOL Upper Extremity Function" are merged into the common prefix
   "Neuro-QOL" if it covers enough tinyIds (`--min-prefix-tinyids`)
3. **Anchor trimming** (on by default): Strips "as part of the...", "based on
   the..." prefixes to get bare instrument names
4. **Parent filtering**: Drops patterns whose parent phrase appears on fewer than
   `--min-parent-tinyids` CDEs (noise reduction). The default of 20 works for
   large datasets; lower it (e.g., to 10) for smaller subsets — see
   [Tuning a conservative threshold](#example-tuning-a-conservative-threshold)
   in Scenario 5

**Review the report**: Open `subsumption_report.tsv` to see which patterns were
removed and why. This is your audit trail for the coalescing decisions.

### Step 4: Enrich with field analysis and filter

Add per-field counts and apply automated filters:

```bash
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i cdes.json -m CDE \
    -o coalesced_fields.tsv \
    --min-field-count 6 \
    --min-tokens 3
```

**New columns added**: `definition_count`, `designation_count`, `field_profile`.

**Filters applied**:

- `--min-field-count 6` — drop patterns that appear in fewer than 6 CDEs in
  *both* fields (if it appears in 10 definitions but 2 designations, it survives)
- `--min-tokens 3` — drop patterns with fewer than 3 words (high false positive
  risk for 1-2 word patterns)

**The field_profile column** tells you where each pattern lives:

| Value | Meaning |
|-------|---------|
| `def-only` | Only in definition fields |
| `desig-only` | Only in designation fields |
| `both-all` | In both fields — strongest stripping candidate |
| `mixed` | In both but inconsistently — review manually |

### Step 5: Human curation (checkpoint)

Open `coalesced_fields.tsv` in a spreadsheet. This is the most important step.

**Review checklist**:

1. **Remove false positives** — patterns that carry semantic meaning (disease
   names, measurement concepts) that shouldn't be stripped
2. **Check short patterns** — anything with 3-4 tokens deserves extra scrutiny
3. **Verify temporal grouping** — "in the past 7 days" and "in the past 30
   days" should both be present (or grouped)
4. **Send instrument residuals back** — if you find missed instruments, add
   them to `config/supplementary_patterns.yaml` and re-run the instrument
   pipeline first
5. **Check field profiles** — `def-only` patterns might be definition templates
   worth stripping; `desig-only` might be naming conventions

Save the reviewed file as `curated.tsv`.

### Step 6: Strip

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o cdes_stripped.json \
    --patterns curated.tsv \
    --clean-remnants \
    --remnant-report remnants.tsv \
    --match-log match_log.tsv \
    --match-summary match_summary.tsv \
    --workers 0
```

### Step 7: Verify

Generate a discovery report for a pipeline summary:

```bash
cde-analyzer discovery_report \
    --output-dir ./ \
    --pipeline phrase \
    --input-json cdes.json \
    -o discovery_report.md
```

---

## Scenario 4: Field-Aware Two-Pass Stripping

**Goal**: Strip different patterns from different fields, or strip in two
passes (long patterns first, then short fragments).

**When to use**: When your field analysis shows that some patterns are
definition-only or designation-only, or when you have both long instrument
patterns and short generic fragments.

### Why two passes?

Long instrument patterns (e.g., "Patient Health Questionnaire (PHQ-9) - ") must
be stripped before short fragments (e.g., "total score"). If you strip "total
score" first, the instrument pattern changes shape and may not match.

### Pass 1: Strip long patterns from all fields

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o pass1.json \
    --patterns long_patterns.tsv \
    --clean-remnants \
    --match-log pass1_matches.tsv \
    --workers 0
```

### Pass 2: Strip short fragments

```bash
cde-analyzer strip_phrases \
    -i pass1.json -m CDE -o pass2.json \
    --patterns short_patterns.tsv \
    --clean-remnants \
    --match-log pass2_matches.tsv \
    --workers 0
```

### Generating tiered pattern files

The `--split-tiers` flag on coalesce splits patterns by token count:

```bash
cde-analyzer pattern_util --coalesce-variants discovered.tsv \
    -o coalesced.tsv \
    --split-tiers 4
```

This produces:
- `coalesced.tsv` — tier-1 patterns with >= 4 tokens
- `coalesced_short.tsv` — tier-2 patterns with < 4 tokens

### Field-specific stripping

To strip patterns only from definitions:

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o cdes_def_stripped.json \
    --patterns def_only_patterns.tsv \
    --fields definitions.*.definition
```

To strip only from designations:

```bash
cde-analyzer strip_phrases \
    -i cdes_def_stripped.json -m CDE -o cdes_fully_stripped.json \
    --patterns desig_only_patterns.tsv \
    --fields designations.*.designation
```

---

## Scenario 5: Using the Workflow Engine

**Goal**: Run the entire discover-coalesce-curate-strip pipeline as a
single automated workflow, with a checkpoint for human review.

**When to use**: Repeatable production runs, especially when you want to
standardize parameters across team members.

### The phrase pipeline workflow

The project includes a pre-built workflow definition at
`workflows/phrase_pipeline.yaml` that encodes Scenarios 3-4 as a single
pipeline:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=cdes_no_instruments.json \
    --set output_dir=./phase2_output
```

### What the workflow does

| Step | Action | What it produces |
|------|--------|------------------|
| 1 | `phrase_miner` | `verbatim_phrases.tsv` |
| 2 | `strip_discover` | `discovered.tsv` |
| 3 | `pattern_util --coalesce-variants` | `coalesced.tsv` |
| 4 | `pattern_util --field-analysis` | `coalesced_fields.tsv` |
| 5 | **CHECKPOINT** — human review | `curated.tsv` (you create this) |
| 6 | `strip_phrases` | `final_stripped.json` |
| 7 | `discovery_report` | `discovery_report.md` |

The workflow pauses at the checkpoint step and prints instructions. After you
curate and save `curated.tsv`, resume with:

```bash
cde-analyzer workflow resume \
    --state-file ./phase2_output/.workflow_state.json
```

### Customizing parameters

Override any variable at invocation time with `--set`:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=cdes.json \
    --set output_dir=./output \
    --set min_field_count=3 \
    --set min_tokens=2 \
    --set workers=4
```

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `k_max` | 25 | Maximum k-mer length (tokens) for phrase mining |
| `k_min` | 3 | Minimum k-mer length (tokens) for phrase mining |
| `min_parent_tinyids` | 20 | Parent phrase coverage threshold for coalescing |
| `min_field_count` | 6 | Minimum CDEs per field for a pattern to survive |
| `min_tokens` | 3 | Minimum words in a pattern |
| `workers` | 0 (auto) | Parallel worker count |
| `exclude_patterns` | (none) | Path to exclusion list |

### Variable resolution order

The workflow engine resolves each variable in three steps:

1. **`--set` overrides** (highest priority) — from the command line
2. **Environment variables** — e.g., `export MIN_PARENT_TINYIDS=10`
3. **YAML defaults** — the `:-` fallback in the workflow file

For example, the phrase pipeline YAML defines:

```yaml
variables:
  min_parent_tinyids: "${MIN_PARENT_TINYIDS:-20}"
```

This means: use `--set min_parent_tinyids=N` if provided, then check for a
`MIN_PARENT_TINYIDS` environment variable, then fall back to `20`.

### Example: Tuning a conservative threshold

The default `min_parent_tinyids=20` drops any pattern whose parent phrase
(the lemmatized form that spawned the verbatim variants) appears on fewer
than 20 CDEs. This works well for large datasets but can be too aggressive
for smaller subsets — some valid patterns with 10-15 CDE occurrences get
silently dropped during coalescing.

**Symptom**: You inspect `coalesced.tsv` and notice that patterns you
expected are missing. The `coalesce_report.tsv` shows them filtered by
the parent threshold.

**Fix**: Lower the threshold at invocation time:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=inst_stripped.json \
    --set output_dir=./phase2_output \
    --set min_parent_tinyids=10
```

Or via environment variable (useful in a shell script):

```bash
export MIN_PARENT_TINYIDS=10
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=inst_stripped.json \
    --set output_dir=./phase2_output
```

### Example: Extending k-mer range for long phrases

The phrase miner scans k-mers from `k_max` down to `k_min` tokens. The
default `k_max=25` means phrases longer than 25 words are never detected
as a single unit — the miner sees them only as overlapping 25-word fragments
that may or may not reassemble via de Bruijn extension.

**Symptom**: You know your data contains long instrument descriptions or
definition templates exceeding 25 words, but `verbatim_phrases.tsv` shows
them truncated or split into multiple shorter phrases.

**Fix**: Raise `k_max` to cover the longest expected phrases:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=inst_stripped.json \
    --set output_dir=./phase2_output \
    --set k_max=35
```

> **Performance note**: Higher `k_max` increases mining time because more
> k-mer bins are scanned. The cost is linear in `k_max - k_min`, so raising
> from 25 to 35 adds ~40% more bins. For most datasets this is negligible.

### Example: Detecting abbreviated designation patterns

After stripping, always inspect the output for residual patterns that the
automated pipeline didn't catch. A common gap: CDEs whose **designations use
an abbreviated form** of the instrument name, different from the full name
that the miner detected.

**Symptom**: You search `inst_stripped.json` for a known instrument prefix
and find CDEs where the designation still contains it:

```
Quality of Life - Depression assessment past week scale
Quality of Life - Emotional exhaustion assessment past week scale
```

These 24 CDEs use the shortened designation "Quality of Life - [subscale]"
instead of the full name "Quality of Life in Neurological Disorders
(Neuro-Qol) -" that the miner found on 19 *other* CDEs.

**Why the miner missed them**: The instrument miner relies on parenthetical
acronyms (e.g., "(Neuro-Qol)") to identify instrument names. The shortened
"Quality of Life -" has no acronym and is too generic to auto-detect. These
are effectively two separate CDE populations:

| CDE set | Designation format | Miner result |
|---------|-------------------|--------------|
| 19 CDEs | `Quality of Life in Neurological Disorders (Neuro-Qol) - ...` | Detected |
| 24 CDEs | `Quality of Life - [subscale]` | **Not detected** |

**Fix**: Add the abbreviated pattern to `curated.tsv` **with tinyId
restrictions** to prevent false positives:

```
Quality of Life -	<24 tinyIds>
Quality of Life	<24 tinyIds>
```

The tinyId column limits stripping to these specific CDEs, which is
important because "Quality of Life" appears as meaningful content in other
definitions. Without tinyId restriction, the bare phrase would be stripped
everywhere.

**General rule**: After each stripping phase, grep the output for known
instrument prefixes. If residuals appear on CDEs with abbreviated
designations, add them manually with tinyId restrictions rather than
relying on the automated miner.

### Persistent overrides: project config file

For ongoing work on a specific dataset, create a config file in your output
directory. The workflow engine auto-discovers it by convention:

```
{output_dir}/{workflow_name}_config.yaml
```

For the phrase pipeline (`name: phrase_stripping`), this means:

```
phase2_output/phrase_stripping_config.yaml
```

**Create the config file** with just the variables you want to override:

```yaml
# phase2_output/phrase_stripping_config.yaml
# Project-specific overrides — only list what differs from defaults
k_max: 35
min_parent_tinyids: 10
```

**Run the workflow** — the config is loaded automatically:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set input_json=inst_stripped.json \
    --set output_dir=./phase2_output
```

The engine logs which config file was loaded and which values were overridden.

**Variable resolution order** (lowest → highest priority):

| Priority | Source | Example |
|----------|--------|---------|
| 1 (lowest) | Workflow YAML defaults | `min_parent_tinyids: "${MIN_PARENT_TINYIDS:-20}"` |
| 2 | Project config file | `phrase_stripping_config.yaml` |
| 3 (highest) | `--set` CLI overrides | `--set min_parent_tinyids=5` |

This means `--set` always wins — you can use it for one-off experiments
on top of your project config without editing the file.

**Key behaviors**:

- **No config file?** Silent no-op — workflow uses YAML defaults as before
- **Resume after checkpoint**: Uses the resolved values from the initial run
  (config is not re-read on resume, preventing mid-pipeline inconsistency)
- **Config file name**: Derived from the workflow's `name:` field, not the
  YAML filename. Check `name:` at the top of the workflow YAML

**Separating invocation from configuration**: With a config file, your
run script stays clean — it only sets paths, while tuning parameters
live in the phase directory alongside the data they govern:

```bash
# run_pipeline.sh — paths only
cde_run workflow run "$WORKFLOWS/phrase_pipeline.yaml" \
    --set "input_json=$PHASE1_DIR/inst_stripped.json" \
    --set "output_dir=$PHASE2_DIR"

# phase2_output/phrase_stripping_config.yaml — tuning parameters
# k_max: 35
# min_parent_tinyids: 10
# min_field_count: 6
```

### Alternative: ad-hoc YAML copy

For quick experiments without a project config file, copy the built-in
workflow and edit it directly:

```bash
cde-analyzer workflow copy phrase_pipeline --as ./my_phrase_pipeline.yaml
# Edit defaults in the copy, then run it explicitly:
cde-analyzer workflow run ./my_phrase_pipeline.yaml \
    --set input_json=inst_stripped.json \
    --set output_dir=./phase2_output
```

Note: the workflow engine reads exactly one YAML — the path you pass to
`workflow run`. A copied YAML in your directory is not discovered
automatically; you must point to it.

---

## Scenario 6: Temporal Pattern Grouping

**Goal**: Automatically detect and group temporal boilerplate phrases
("in the past 7 days", "over the last 4 weeks") that vary only by number
or time unit.

**When to use**: After coalescing, when you have many temporal variants that
should be treated as a single family.

### Semantic grouping with SpaCy

```bash
cde-analyzer pattern_util --group-semantic coalesced.tsv \
    -o grouped.tsv \
    --min-group-size 2 \
    --min-prefix-words 2
```

This uses SpaCy POS tagging to find shared prefixes and group patterns:

```
Input patterns:
  "in the past 7 days"
  "in the past 30 days"
  "in the past 4 weeks"
  "in the past 6 months"

Grouped output:
  temporal_group: "in the past"
  group_prefix:   "in the past"
  Patterns:       4 patterns, covering 120 tinyIds
```

### Implied temporal variants

By default, `--group-semantic` also generates "implied-ONE" forms — singular
versions of temporal patterns that may exist on different CDEs:

```
Explicit:  "in the past 7 days"
Implied:   "in the past day"       ← generated automatically
```

Disable with `--no-temporal-implied` if you don't want these.

### Hierarchy-based grouping (alternative)

For simpler prefix-based grouping without SpaCy:

```bash
cde-analyzer pattern_util --group-hierarchy coalesced.tsv \
    -o grouped.tsv \
    --min-tinyids 3
```

Then generate strip-ready files from the hierarchy:

```bash
cde-analyzer pattern_util --generate-strip-patterns grouped.tsv \
    -o strip_patterns
```

This produces:
- `strip_patterns_full.tsv` — full pattern removal
- `strip_patterns_sub.tsv` — group prefix removed, suffix retained
  (via `replace_with` column)

---

## Common Recipes

### Excluding known false positives

Create an exclusion file (one pattern per line or TSV with `pattern` column):

```
total score
self-report
```

Apply during field analysis:

```bash
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i cdes.json -m CDE -o filtered.tsv \
    --exclude-patterns exclusions.txt
```

### Merging patterns from multiple sources

When you have patterns from different pipeline stages:

```bash
# Normalize each to minimal format
cde-analyzer pattern_util --to-minimal coalesced.tsv -o a_min.tsv
cde-analyzer pattern_util --to-minimal abbrev_patterns.tsv -o b_min.tsv

# Concatenate (Unix)
head -1 a_min.tsv > combined.tsv
tail -n +2 a_min.tsv >> combined.tsv
tail -n +2 b_min.tsv >> combined.tsv

# Concatenate (PowerShell)
# Get-Content a_min.tsv | Select-Object -First 1 | Set-Content combined.tsv
# Get-Content a_min.tsv | Select-Object -Skip 1 | Add-Content combined.tsv
# Get-Content b_min.tsv | Select-Object -Skip 1 | Add-Content combined.tsv

# Merge duplicates
cde-analyzer pattern_util --merge-patterns combined.tsv -o merged.tsv
```

### Controlling pattern match order

The default `--sort-order length` (longest-first) handles most cases. Two
alternatives:

```bash
# Curator-defined order: patterns are tried in TSV file order
cde-analyzer strip_phrases ... --sort-order file

# Alphabetical: deterministic ordering for reproducibility
cde-analyzer strip_phrases ... --sort-order alpha
```

Use `--sort-order file` when you've carefully ordered patterns in your
curated TSV and want that order respected.

### Disabling anchor expansion

By default, `strip_phrases` expands patterns with anchor prefixes ("as part
of the...") to match longer context. If this causes false matches:

```bash
cde-analyzer strip_phrases ... --no-expand-anchors
```

### Disabling verbatim config patterns

By default, patterns from `config/verbatim_strip_patterns.yaml` are merged
with your patterns file. To strip only your curated patterns:

```bash
cde-analyzer strip_phrases ... --no-verbatim-patterns
```

### Debugging: why didn't my pattern match?

Use `--trace-matching` for detailed per-match logging:

```bash
cde-analyzer strip_phrases \
    -i cdes.json -m CDE -o output.json \
    --patterns patterns.tsv \
    --trace-matching trace.tsv
```

The trace file logs every pattern tested against every record, showing which
matched and which didn't. Note: this forces `--workers 1` (sequential mode)
and produces large output.

---

## Decision Flowchart

```
Start: You have CDE JSON and want to strip boilerplate
  │
  ├── Do you already have a curated patterns TSV?
  │     ├── YES → Scenario 1 (or 2 with cleanup)
  │     └── NO  → Continue below
  │
  ├── Is this a one-time analysis or a repeatable pipeline?
  │     ├── ONE-TIME → Scenario 3 (manual steps)
  │     └── REPEATABLE → Scenario 5 (workflow engine)
  │
  ├── Do you need field-specific stripping?
  │     ├── YES → Scenario 4 (two-pass or field-aware)
  │     └── NO  → Scenario 3 is sufficient
  │
  └── Do you have many temporal phrases?
        ├── YES → Add Scenario 6 (grouping) before stripping
        └── NO  → Proceed directly to strip
```

---

## Glossary

| Term | Meaning |
|------|---------|
| **pattern** | An exact text string to find and remove from CDE fields |
| **tinyId** | Unique identifier for a CDE record |
| **coalescing** | Removing shorter patterns that are subsumed by longer ones |
| **anchor phrase** | Introductory text like "as part of the..." that precedes an instrument name |
| **remnant** | Artifact left after stripping (orphan article, dangling punctuation) |
| **field profile** | Whether a pattern appears in definitions, designations, or both |
| **verbatim pattern** | The exact surface form of a phrase as it appears in the text |
| **subsumption** | When a shorter pattern's tinyIds are fully covered by longer patterns |
| **tier splitting** | Dividing patterns into long (tier-1) and short (tier-2) for ordered stripping |
