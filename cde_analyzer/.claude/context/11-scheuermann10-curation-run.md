# Scheuermann10: Full Curation Run with Knowledge Graph Grouping

> **Purpose**: Evaluate whether knowledge graph community detection has utility for
> human curation of phrase patterns. If successful, the `knowledge-graph` branch
> will be merged into `phrase-curator` and this document (with standalone script
> references replaced by integrated CLI commands) becomes a template for complex
> workflow setup documentation.

## Overview

Set up a new evaluation directory `scheuermann10` to run the complete instrument +
phrase curation pipeline on the scheuermann04 subset data (1148 CDEs). The run uses
knowledge graph analysis for curation grouping and produces 5 branching-strip outputs.

## Directory Structure

```
/mnt/d/GT/Professional/NLM_CDE/work_202601/cde_repository/scheuermann10/
├── cdes_subset.json              # copied from scheuermann04
├── cdes_subset_tinyids.csv       # copied from scheuermann04
├── phase1_output/                # instrument pipeline output
├── phase2_output/                # phrase pipeline output (stops at checkpoint)
├── curation/                     # KG grouping script + curation files
│   ├── pattern_graph.py          # copied from knowledge-graph branch
│   ├── group_for_curation.py     # standalone script: builds graphs, outputs grouped TSV
│   └── grouped_patterns.tsv      # output: patterns with community/cluster columns
├── branching_output/             # 5-way strip output (after curation)
└── run_pipeline.sh               # orchestration script
```

## Pipeline Phases

### Phase 1 — Instrument Detection (from scratch)

Runs the full instrument pipeline on raw subset data. Mines instrument names,
discovers abbreviation-based patterns, expands verbatim variants, and coalesces.

```bash
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
  --set input_json=$BASE/cdes_subset.json \
  --set output_dir=$BASE/phase1_output
```

**Checkpoint**: Review `phase1_output/coalesced.tsv`, save as `phase1_output/curated.tsv`.
Resume to strip instruments → produces `phase1_output/inst_stripped.json`.

### Phase 2 — Phrase Mining

Runs phrase pipeline on instrument-stripped JSON. Mines k-mer phrases, discovers
verbatim occurrences, coalesces, and enriches with field distribution analysis.

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
  --set input_json=$BASE/phase1_output/inst_stripped.json \
  --set output_dir=$BASE/phase2_output \
  --set MIN_FIELD_COUNT=6 \
  --set MIN_TOKENS=3
```

**Checkpoint**: Stops after field analysis. Produces `phase2_output/coalesced_fields.tsv`
with `def_count`, `desig_count`, `field_profile` columns, filtered by min thresholds.

### Curation Helper — Knowledge Graph Grouping

Standalone script that builds knowledge graphs from the field-analyzed patterns and
outputs a grouped TSV for human review. This is the step being evaluated.

```bash
python $BASE/curation/group_for_curation.py \
  $BASE/phase2_output/coalesced_fields.tsv \
  -o $BASE/curation/grouped_patterns.tsv \
  --export-graphml $BASE/curation/
```

**Graph types built**:

- **Co-occurrence graph**: Patterns sharing tinyIds, weighted by Jaccard similarity.
  Community detection groups related patterns together.
- **Subsumption DAG**: Directed edges from longer patterns containing shorter ones.
  Identifies root patterns and hierarchy depth.
- **Edit distance graph**: Token-level Jaccard similarity catches near-duplicates.
- **Semantic similarity graph**: Sentence-transformer cosine similarity (optional,
  requires `sentence-transformers` package).

**Output columns added**: `community_id`, `dag_depth`, `is_root`, `parent_pattern`,
`semantic_cluster`.

### Phase 3 — Branching Strip (after curation)

After manual curation produces `curated.tsv` files, generate strip patterns and
run the 5-way branching strip.

```bash
# Generate instrument strip pattern files (full and sub-group variants)
cde-analyzer pattern_util --generate-strip-patterns \
  $BASE/phase1_output/curated.tsv \
  -o $BASE/phase1_output/strip_patterns

# Run 5-way branching strip
cde-analyzer workflow run workflows/branching_strip.yaml \
  --set input_json=$BASE/cdes_subset.json \
  --set output_dir=$BASE/branching_output \
  --set inst_patterns_base=$BASE/phase1_output/strip_patterns \
  --set phrase_patterns=$BASE/phase2_output/curated.tsv
```

**Produces 5 outputs**:

1. `inst_full_stripped.json` — instruments fully removed
2. `inst_sub_stripped.json` — instrument group prefix removed, suffix retained
3. `phrase_stripped.json` — phrases removed (no instrument stripping)
4. `both_full_stripped.json` — full instrument + phrase removal
5. `both_sub_stripped.json` — sub-group instrument + phrase removal

## Curation Workflow (Human Steps)

1. Run Phase 1 → review `phase1_output/coalesced.tsv` → save as `curated.tsv`
2. Resume Phase 1 → produces `inst_stripped.json`
3. Run Phase 2 → produces `coalesced_fields.tsv` at checkpoint
4. Run KG grouping → produces `grouped_patterns.tsv`
5. Open grouped TSV in spreadsheet, curate by community, save as `phase2_output/curated.tsv`
6. Run Phase 3 → 5 branching-strip outputs

## Evaluation Criteria

The knowledge graph grouping is considered useful if:

- Communities group semantically related patterns (temporal phrases together,
  instrument residuals together, scale/rating patterns together)
- Root patterns in the subsumption DAG identify the "canonical" form to keep
- The grouped view reduces curation effort compared to flat alphabetical review
- Near-duplicate detection (edit distance) catches patterns that should be merged

## Future Integration (if evaluation succeeds)

If KG grouping proves useful:

1. Merge `knowledge-graph` branch into `phrase-curator`
2. Add `--build-graph` subcommand to `pattern_util` CLI
3. Replace standalone `group_for_curation.py` with integrated workflow step
4. Update `phrase_pipeline.yaml` to include graph grouping before checkpoint
5. This document becomes documentation template (minus standalone script references)

## Files Created

| File                                           | Description                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------- |
| `scheuermann10/curation/pattern_graph.py`      | Copied from `knowledge-graph` branch                              |
| `scheuermann10/curation/group_for_curation.py` | Loads TSV, builds graphs, detects communities, writes grouped TSV |
| `scheuermann10/run_pipeline.sh`                | Orchestration with phase detection and checkpoints                |
