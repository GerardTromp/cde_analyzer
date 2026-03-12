# Vignette: Full Pipeline Quickstart

A walkthrough of the complete CDE Analyzer pipeline — from raw CDE JSON
through instrument detection, phrase mining, and branching strip — producing
five cleaned output variants.

## What This Vignette Covers

The CDE Analyzer pipeline has three phases:

| Phase | Purpose | Output |
|-------|---------|--------|
| 1. Instrument Detection | Find and remove instrument names (PHQ-9, PROMIS, etc.) | `inst_stripped.json` |
| 2. Phrase Mining | Find and remove boilerplate phrases ("in the past 7 days", etc.) | `curated.tsv` |
| 3. Branching Strip | Apply curated patterns in 5 combinations | 5 stripped JSON files |

Each phase has a human curation checkpoint where you review and approve
discovered patterns before stripping.

**Prerequisites**: A Python environment with `cde-analyzer` installed and a
JSON file of CDE records. All examples use `cdes.json` as input.

**Related vignettes**:

- [Instrument Detection](instrument-detection.md) — deep dive into Phase 1 curation
- [Pipeline Orchestration](pipeline-orchestration.md) — workflow engine, config files, scaffold details
- [Parameter Tuning](parameter-tuning.md) — adjusting for small vs large datasets
- [Phrase Stripping](phrase-stripping.md) — advanced Phase 2 scenarios

---

## Step 1: Generate a Pipeline Script

The `workflow scaffold` command creates a project-specific bash script that
wires together all three phases:

```bash
cde-analyzer workflow scaffold myproject \
    -i /data/cdes.json \
    -d /data/myproject_output \
    --with-iterate
```

This generates `/data/myproject_output/run_pipeline.sh` with:

- **PARAMETERS** section — paths and tuning variables you can edit
- **Phase functions** — `phase1()`, `phase2()`, `phase3()`, plus helpers
- **Dispatch** — run individual phases or the full pipeline

```
Generated pipeline script: /data/myproject_output/run_pipeline.sh
  Project: myproject
  Phases: [1, 2, 3]
  Includes: iterative residual harvesting

Next steps:
  1. Review and customize parameters in run_pipeline.sh
  2. Run: ./run_pipeline.sh phase1
```

!!! tip "Edit before running"
    Open `run_pipeline.sh` and review the `PARAMETERS` section. At minimum,
    confirm that `INPUT_JSON`, `BASE`, and `WORKFLOWS` point to the right
    locations. For small datasets (<2,000 CDEs), see
    [Parameter Tuning](parameter-tuning.md) for recommended overrides.

---

## Step 2: Phase 1 — Instrument Detection

```bash
./run_pipeline.sh phase1
```

This runs `instrument_pipeline.yaml`, which:

1. **Mines instrument names** from CDE text fields (regex + NLP extraction)
2. **Discovers abbreviation patterns** (e.g., PHQ → Patient Health Questionnaire)
3. **Discovers verbatim occurrences** across all CDEs with variant expansion
4. **Coalesces redundant patterns** via prefix trie + reverse subsumption
5. **Validates subsumption** empirically against source text
6. **Enriches with field counts** (tinyid_count, def_count, desig_count, field_profile)

Then it stops at a **checkpoint**:

```
╔══════════════════════════════════════════════════════════════════════╗
║  Phase 1: Instrument Detection
╚══════════════════════════════════════════════════════════════════════╝

Step 6/9: enrich_fields ... done (4.2s)

>>> CHECKPOINT: Instrument pattern curation required.
>>>   Review: phase1_output/coalesced_fields.tsv
>>>   Save as: phase1_output/curated.tsv
```

### Curating Phase 1 output

Open `coalesced_fields.tsv` in the built-in browser-based TSV editor:

```bash
cde-analyzer pattern_util --edit phase1_output/coalesced_fields.tsv
```

This launches a local web server and opens an interactive editor in your browser
where you can review, sort, filter, and edit patterns. **Click any column header
to sort** ascending/descending — useful for sorting by `tinyid_count` to
prioritize high-impact patterns. When you are done, use **Save As** to write
the reviewed file as `phase1_output/curated.tsv`, then press Ctrl-C in the
terminal to stop the server.

You will see columns like:

```tsv
pattern                                    tinyIds          tinyid_count  def_count  desig_count  field_profile
Patient Health Questionnaire (PHQ-9)       abc|def|ghi      3             12         45           definition+designation
Neuro-QOL Positive Affect and Well-Being   jkl|mno          2             8          22           definition+designation
think about                                pqr|stu          2             0          3            designation_only
```

**Keep**: Recognized instrument names — `Patient Health Questionnaire (PHQ-9)`.

**Remove**: Sentence fragments — `think about`, `my sexual`, `mentally tired`.
These contain verbs or pronouns and are not instrument names.

**Keep both**: Family patterns and their sub-domains — `Neuro-QOL` alongside
`Neuro-QOL Positive Affect and Well-Being`. Both are valid instruments.

Then resume the pipeline:

```bash
cde-analyzer workflow resume \
    --state-file phase1_output/.workflow_state.json
```

This completes Phase 1 by stripping curated patterns and running a sanity check.

---

## Step 3: Prepare Strip Patterns (Inter-Phase)

Before Phase 3 can branch the stripping, instrument patterns need hierarchy
and full/sub-group splitting:

```bash
./run_pipeline.sh prepare_strip
```

This runs two `pattern_util` commands:

1. `--group-hierarchy` — assigns group/suffix columns to each pattern
2. `--generate-strip-patterns` — produces `strip_patterns_full.tsv` and
   `strip_patterns_sub.tsv`

```
Generated:
  phase1_output/strip_patterns_full.tsv  (full instrument removal)
  phase1_output/strip_patterns_sub.tsv   (sub-group prefix removal)
```

---

## Step 4: Phase 2 — Phrase Mining

```bash
./run_pipeline.sh phase2
```

This runs `phrase_pipeline.yaml` on the instrument-stripped JSON from Phase 1.
It uses k-mer mining (descending from `k_max` to `k_min`) to find shared
boilerplate phrases:

```
Step 1/9: mine_phrases ... done (32.1s)
  Mined 13,640 k-mer phrases
Step 2/9: discover_verbatim ... done (18.4s)
Step 3/9: coalesce_patterns ... done (2.1s)
Step 4/9: field_analysis ... done (5.6s)

>>> CHECKPOINT: Phrase pattern curation required.
>>>   Review: phase2_output/coalesced_fields.tsv
>>>   Save as: phase2_output/curated.tsv
```

### Curating Phase 2 output

Phase 2 patterns look different from Phase 1 — these are repeated text
fragments, not instrument names:

```tsv
pattern                                       tinyIds       tinyid_count  def_count  desig_count
in the past 7 days                           aaa|bbb|ccc    3             89         0
Please respond to each item                  ddd|eee        2             0          45
For each of the following statements         fff|ggg        2             0          38
```

These are typically boilerplate that should be removed. Open the file in the
browser-based editor to review:

```bash
cde-analyzer pattern_util --edit phase2_output/coalesced_fields.tsv
```

Remove false positives (patterns that look boilerplate but carry real meaning),
then use **Save As** to write `phase2_output/curated.tsv` and Ctrl-C to stop
the server. Then resume:

```bash
cde-analyzer workflow resume \
    --state-file phase2_output/.workflow_state.json
```

---

## Step 5: Phase 3 — Branching Strip

```bash
./run_pipeline.sh phase3
```

This runs `branching_strip.yaml`, which produces **five stripped variants**
from the original (un-stripped) CDE JSON:

| Code | Main inst | Sub inst | Phrases | Description |
|------|:-:|:-:|:-:|---|
| MTSFPF | Stripped | - | - | Full instrument removal only |
| MFSTPF | - | Stripped | - | Sub-group removal only |
| MFSFPT | - | - | Stripped | Phrases only |
| MTSFPT | Stripped | - | Stripped | Full instruments + phrases |
| MFSTPT | - | Stripped | Stripped | Sub instruments + phrases |

> **Note — MT+ST equivalence**: Combinations with both Main and Sub stripped
> (MTSTPF, MTSTPT) are omitted because full instrument removal (`inst_full`)
> deletes the entire pattern text, leaving nothing for sub-instrument removal
> (`inst_sub`) to match. They are functionally identical to MTSFPF and MTSFPT.

Temporal patterns (e.g., "in the past 7 days") are automatically expanded
from seed patterns and stripped case-insensitively before curated phrases are
applied case-sensitively.

### Checking the results

Phase 3 generates a quality report automatically. A typical summary
(from a 22,743-CDE corpus):

| Code | Characters removed |
|------|-------------------|
| MTSFPF | -515K |
| MFSTPF | -415K |
| MFSFPT | -105K |
| MTSFPT | -553K |
| MFSTPT | -449K |

```
Phase 3 complete. Outputs:
  branching_output/stripped_MTSFPF.json
  branching_output/stripped_MFSTPF.json
  branching_output/stripped_MFSFPT.json
  branching_output/stripped_MTSFPT.json
  branching_output/stripped_MFSTPT.json
```

!!! tip "Production: run only the variants you need"
    The full pipeline produces all 5 variants. For production, use
    `workflow configure` to generate a minimal pipeline:

        cde-analyzer workflow configure MTSFPT -o production_strip.yaml

    Or use the N-way single-pass engine for faster execution (loads JSON once):

        cde-analyzer workflow configure MTSFPT --nway -o production_strip.yaml

---

## Alternative: Running Without Scaffold

If you prefer direct workflow commands over the generated script:

```bash
# Phase 1
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
    --set "input_json=/data/cdes.json" \
    --set "output_dir=/data/phase1_output"

# (curate, then resume)

# Prepare strip patterns
cde-analyzer pattern_util -g phase1_output/curated.tsv -o phase1_output/hierarchy.tsv
cde-analyzer pattern_util -G phase1_output/hierarchy.tsv -o phase1_output/strip_patterns

# Phase 2
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=/data/phase1_output/inst_stripped.json" \
    --set "output_dir=/data/phase2_output"

# (curate, then resume)

# Phase 3
cde-analyzer workflow run workflows/branching_strip.yaml \
    --set "input_json=/data/cdes.json" \
    --set "output_dir=/data/branching_output" \
    --set "inst_patterns_base=/data/phase1_output/strip_patterns" \
    --set "phrase_patterns=/data/phase2_output/curated.tsv"
```

!!! note "Phase 3 input is the original JSON"
    `branching_strip.yaml` takes the **original un-stripped JSON** as input,
    not the instrument-stripped output. It applies instrument and phrase
    patterns independently to produce 5 distinct combinations.

---

## What's Next

- **Tune parameters** for your dataset size: [Parameter Tuning](parameter-tuning.md)
- **Iterate on Phase 1** to catch more instruments: [Instrument Detection](instrument-detection.md) (iterative harvesting)
- **Advanced Phase 2** scenarios: [Phrase Stripping](phrase-stripping.md)
- **Understand the workflow engine**: [Pipeline Orchestration](pipeline-orchestration.md)
