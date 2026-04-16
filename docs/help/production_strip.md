# production_strip — Production Strip Pipeline

## Synopsis

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output
```

## Description

End-to-end pipeline from raw CDE JSON to embed-ready artifacts using
the Curator B curation baseline. Pre-curated patterns from the reference ledger
are applied automatically — no curation steps required.

Produces for each variant:

| File | Columns | Purpose |
|------|---------|---------|
| `stripped_{VARIANT}.json` | Full CDE schema | Normalized CDE JSON |
| `embed_{VARIANT}.tsv` | tinyId, embed_text | Embedding substrate |
| `embed_{VARIANT}.csv` | tinyId, Name, Question, Definition | Cluster annotation |

Default variants: **MTSFPT** and **MTSTPT**.

## Pipeline Steps

| # | Step | Action | Description |
|---|------|--------|-------------|
| 1 | apply_phrase_substitutions | strip_phrases | Phrase substitutions (5 patterns) |
| 2 | apply_boilerplate_substitutions | strip_phrases | Boilerplate text replacements (231 patterns) |
| 3 | expand_temporal | pattern_util | Generate ~2100 temporal variants from 25 seeds |
| 4 | branching_strip | strip_branching | N-way strip producing selected variants |
| 5 | quality_report | strip_report | Scan for remnants, leakage, detritus |
| 6 | extract_embed | extract_embed | Batch extraction → TSV + CSV per variant |
| 7 | pipeline_complete | checkpoint | Summary of output artifacts |

## Required Arguments

| Argument | Description |
|----------|-------------|
| `input_json` | Path to raw CDE JSON file (e.g., `allcde.json`) |
| `output_dir` | Directory for all output artifacts |

## Optional Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `variants` | `MTSFPT,MTSTPT` | Comma-separated variant codes |
| `patterns_dir` | Reference ledger | Directory with pattern TSV files |
| `embed_path_schema` | `config/embed_path_schemas/NQD.csv` | Pydantic path schema for extraction |
| `workers` | auto-detect | Number of parallel workers (0 = auto) |

## Examples

### Minimal (production defaults)

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output
```

### Single variant only

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output \
    --set variants=MTSFPT
```

### All 7 variants

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output \
    --set variants=MTSFPF,MFSTPF,MTSTPF,MFSFPT,MTSFPT,MFSTPT,MTSTPT
```

### Custom pattern directory

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output \
    --set patterns_dir=/path/to/my_patterns
```

### Dry run (verify variable resolution)

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=/path/to/allcde.json \
    --set output_dir=/path/to/output \
    --dry-run
```

## Variant Codes

| Code | Main Inst | Sub Inst | Phrases | Description |
|------|-----------|----------|---------|-------------|
| MTSFPF | stripped | — | — | Main instrument only |
| MFSTPF | — | stripped | — | Sub instrument only |
| MTSTPF | stripped | stripped | — | Both instruments |
| MFSFPT | — | — | stripped | Phrases only |
| **MTSFPT** | stripped | — | stripped | **Main inst + phrases (default)** |
| MFSTPT | — | stripped | stripped | Sub inst + phrases |
| **MTSTPT** | stripped | stripped | stripped | **All stripped (default)** |

All variants include temporal stripping as a built-in stage.

## Path Schemas

Available in `config/embed_path_schemas/`:

| File | Fields | Use case |
|------|--------|----------|
| `NQD.csv` | Name, Question, Definition | Production default |
| `NQDP.csv` | + PermissibleValues | Extended with PV |
| `full_designations.csv` | All 6 designation slots + Def + PV | Research |

## Reference Ledger

Production patterns are in `data/reference_ledger/production_patterns/`:

| File | Patterns | Source |
|------|----------|--------|
| `inst_patterns_full.tsv` | 451 | Phase 1 instrument curation |
| `inst_patterns_sub.tsv` | 451 | Phase 1 instrument curation |
| `phrase_patterns.tsv` | 496 | Curator B baseline |
| `substitute_patterns.tsv` | 5 | Phrase substitutions |
| `boilerplate_substitutes.tsv` | 231 | Combined boilerplate replacements |

## See Also

- `workflow run` — Workflow engine documentation
- `strip_branching` — N-way branching strip engine
- `extract_embed` — Field extraction with batch mode
