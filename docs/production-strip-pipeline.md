# Production Strip Pipeline — Configuration Summary

> **Version**: 1.5.1 &nbsp;|&nbsp; **Curation baseline**: Curator B &nbsp;|&nbsp; **Validated**: 2026-04-16 (22,743 CDEs, 0 diff vs reference)

## Purpose

Normalize CDE text fields by removing instrument names, boilerplate phrases,
temporal prefixes, and recurring non-semantic patterns. Produces embedding-ready
text artifacts from raw NLM CDE repository JSON.

## Pipeline Overview

```
allcde.json
    │
    ├─[1] Phrase substitutions (7 patterns)
    ├─[2] Boilerplate substitutions (231 patterns)
    ├─[3] Temporal pattern expansion (25 seeds → 2,100 variants)
    ├─[4] N-way branching strip (451 inst_full + 451 inst_sub + 2,100 temporal + 395 phrase)
    ├─[5] Quality report (remnant scan + instrument leakage check)
    └─[6] Embed extraction (batch: TSV + CSV per variant)
            │
            ├── embed_MTSFPT.tsv   ← embedding substrate
            ├── embed_MTSFPT.csv   ← cluster annotation
            ├── embed_MTSTPT.tsv
            └── embed_MTSTPT.csv
```

## Pattern Inventory

| Stage | File | Patterns | Scope |
|-------|------|----------|-------|
| Phrase substitutions | `substitute_patterns.tsv` | 7 | Text replacements (e.g., "Indicator of whether" → "Indicator of") |
| Boilerplate substitutions | `boilerplate_substitutes.tsv` | 231 | Long boilerplate → condensed summary (tinyId-scoped) |
| Instrument full | `inst_patterns_full.tsv` | 451 | Instrument group prefixes (e.g., "PROMIS", "Neuro-QOL") |
| Instrument sub | `inst_patterns_sub.tsv` | 451 | Instrument suffixes (e.g., " - Anxiety", " - Pain Interference") |
| Temporal | auto-expanded from `temporal_seed_patterns.yaml` | 2,100 | Temporal prefixes (e.g., "In the past 7 days", "During the last 4 weeks") |
| Phrase | `phrase_patterns.tsv` | 395 | Recurring non-semantic phrases (Curator B curation baseline) |

**Total**: 3,635 unique strip/substitute patterns across all stages.

## Output Variants

| Code | Main Inst | Sub Inst | Phrases | Temporal | Use case |
|------|:---------:|:--------:|:-------:|:--------:|----------|
| **MTSFPT** | ✓ | — | ✓ | ✓ | Default: main instrument + phrases removed |
| **MTSTPT** | ✓ | ✓ | ✓ | ✓ | Maximum: all instrument components + phrases removed |

All variants include temporal stripping. Additional variants (MTSFPF, MFSTPF, etc.) available via `--set variants=...`.

## Output Artifacts

| File | Format | Columns | Downstream use |
|------|--------|---------|----------------|
| `stripped_{VARIANT}.json` | JSON | Full CDE schema | Intermediate; input to embed extraction |
| `embed_{VARIANT}.tsv` | TSV | `tinyId`, `embed_text` | Text embedding models (concatenated with ` :--: `) |
| `embed_{VARIANT}.csv` | CSV | `tinyId`, `Name`, `Question`, `Definition` | Cluster visualization annotation |
| `strip_report.md` | Markdown | — | Quality audit (remnants, leakage) |

### Embed Text Schema (NQD)

| Column | Pydantic path | CDE field |
|--------|---------------|-----------|
| Name | `designations.0.designation` | Primary name / formal title |
| Question | `designations.1.designation` | Question or alternate designation |
| Definition | `definitions.0.definition` | Textual definition |

TSV concatenation: `Name :--: Question :--: Definition`

## Curation Provenance

| Phase | Curator | Decision counts | Affected CDEs |
|-------|---------|-----------------|---------------|
| Instrument | Shared (all curators) | 458 keep | — |
| Phrase | Curator B baseline | 395 strip, 3,658 skip, 5 substitute | 11,936 |
| Boilerplate | Shared | 231 substitute | 231 |
| Temporal | Automated (seed expansion) | 2,100 patterns | — |

Curator B selected after comparative evaluation of three independent curators (A/B/C).
Strip rate: 24% of phrase patterns (Curator A: 8%, Curator C: 64%).

---

## Integration as an External Pipeline Task

### Minimal invocation

```bash
cde-analyzer workflow run workflows/production_strip.yaml \
    --set input_json=<INPUT> \
    --set output_dir=<OUTPUT>
```

**Inputs**: Single JSON file (NLM CDE repository export, array of CDE objects).
**Outputs**: `embed_MTSFPT.{tsv,csv}` and `embed_MTSTPT.{tsv,csv}` in `<OUTPUT>/`.
**Exit code**: 0 on success.
**Runtime**: ~90 seconds for 22,743 CDEs on 20-core machine.

### Requirements

- Python 3.13+ with `cde_analyzer` dependencies installed
- Working directory: `cde_analyzer/` package root (or installed via pip)
- No external services, databases, or network access required

### Nextflow / workflow manager integration

```groovy
process strip_cdes {
    input:
        path cde_json

    output:
        path "output/embed_MTSFPT.tsv", emit: embed_tsv
        path "output/embed_MTSFPT.csv", emit: embed_csv
        path "output/embed_MTSTPT.tsv", emit: embed_mtstpt_tsv
        path "output/embed_MTSTPT.csv", emit: embed_mtstpt_csv

    script:
    """
    cde-analyzer workflow run workflows/production_strip.yaml \
        --set input_json=${cde_json} \
        --set output_dir=output
    """
}
```

### Environment variables (optional overrides)

| Variable | Effect |
|----------|--------|
| `INPUT_JSON` | Alternative to `--set input_json=` |
| `OUTPUT_DIR` | Alternative to `--set output_dir=` |
| `VARIANTS` | Override variant selection (default: `MTSFPT,MTSTPT`) |
| `PATTERNS_DIR` | Use local patterns instead of bundled reference ledger |
| `EMBED_PATH_SCHEMA` | Use alternative field extraction schema |

### Connecting to downstream tasks

```
strip_cdes ──→ embed_MTSFPT.tsv ──→ [embedding model] ──→ vectors.npy
                                                              │
             embed_MTSFPT.csv ──→ [clustering] ──→ labeled_clusters.csv
                                       ↑
                                  vectors.npy
```

The TSV feeds the embedding model (each row = one CDE, `embed_text` column is the input string).
The CSV provides human-readable annotation columns joined back to cluster assignments by `tinyId`.
