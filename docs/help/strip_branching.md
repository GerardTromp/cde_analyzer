# `strip_branching` Command

N-way branching strip producing all variants in a single pass.

## Overview

Replaces the 10-step `branching_strip.yaml` pipeline with a single-pass engine
that loads the CDE JSON once and produces all 7 variants simultaneously. This
avoids redundant JSON loading/parsing (the legacy pipeline loads the 22K-CDE
file multiple times) and shares intermediate results across variants.

## Usage

```bash
cde-analyzer strip_branching -i cdes.json -d output/ \
    --inst-full-patterns inst_full.tsv \
    --inst-sub-patterns inst_sub.tsv \
    --temporal-patterns temporal_expanded.tsv \
    --phrase-patterns curated_phrases.tsv
```

### Produce specific variants only

```bash
cde-analyzer strip_branching -i cdes.json -d output/ \
    --variants MTSFPT,MFSTPT \
    --inst-full-patterns inst_full.tsv \
    --inst-sub-patterns inst_sub.tsv \
    --temporal-patterns temporal_expanded.tsv \
    --phrase-patterns curated_phrases.tsv
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--input` | `-i` | (required) | Path to input CDE JSON file |
| `--output-dir` | `-d` | (required) | Output directory (writes `stripped_{CODE}.json` per variant) |
| `--model` | `-m` | `CDE` | Pydantic model name |
| `--inst-full-patterns` | | | Full instrument patterns TSV |
| `--inst-sub-patterns` | | | Sub-group instrument patterns TSV |
| `--temporal-patterns` | | | Expanded temporal patterns TSV |
| `--phrase-patterns` | | | Curated phrase patterns TSV |
| `--variants` | | all 7 | Comma-separated variant codes |
| `--workers` | `-w` | `0` (auto) | Parallel workers |
| `--clean-remnants` | | `false` | Post-strip cleanup |
| `--fields` | `-f` | definitions + designations | Field paths to strip |
| `--sort-order` | | `length` | Pattern processing order |

## Variant Codes

| Code | What is removed |
|------|-----------------|
| `MTSFPF` | Main instrument prefix removed |
| `MFSTPF` | Sub-instrument suffix removed |
| `MTSTPF` | Main prefix + sub suffix removed |
| `MFSFPT` | Curated phrases removed (no instruments) |
| `MTSFPT` | Main instrument + phrases |
| `MFSTPT` | Sub instrument + phrases |
| `MTSTPT` | Main + sub instrument + phrases |

The naming convention encodes which types are stripped (T) or kept (F):
`M`[ain]`S`[ub]`P`[hrase] — e.g., `MTSFPT` = Main stripped, Sub kept, Phrases stripped.

> **Field-aware splits**: `inst_full` and `inst_sub` operate on different text
> spans. For a pattern like "PROMIS - Anxiety", `inst_full` matches the group
> prefix ("PROMIS") while `inst_sub` matches the separator + suffix
> (" - Anxiety"). This makes all 7 variants genuinely distinct. Use
> `--analyze-instrument-splits` and `--generate-strip-patterns` (splits mode)
> to produce the separate pattern files.
>
> **Mixed separators**: Some groups use both dash and space separators.
> For example, the NIH Toolbox family has `NIH Toolbox - Anger` (sub = ` - Anger`)
> and `NIH Toolbox Anger` (sub = ` Anger`). The separator is detected per-pattern,
> so both forms are handled correctly. See the
> [Instrument Detection vignette](../vignettes/instrument-detection.md#7-field-aware-splits-for-branching-strip)
> for detailed examples.

## How It Works

The engine processes each CDE once, sharing intermediate results:

```
              ┌─ MTSFPF (inst_full only)
              │
              ├─ MFSTPF (inst_sub only)
              │
    original ─┼─ inst_full ─┬─ MTSFPT (+ temporal + phrase)
              │             │
              │             └─ inst_sub ─┬─ MTSTPF (full + sub)
              │                         │
              │                         └─ MTSTPT (+ temporal + phrase)
              │
              ├─ inst_sub ──── MFSTPT (+ temporal + phrase)
              │
              └─ temporal ──── MFSFPT (+ phrase)
```

Only the requested variants are computed. Stage results are reused — for example,
the `inst_full` result feeds MTSFPF, MTSFPT, MTSTPF, and MTSTPT without
recomputation.

## Stage Configuration

Each pattern file is treated as a separate stage with specific settings:

| Stage | Anchor expansion | Case-insensitive | Word boundary |
|-------|-----------------|------------------|---------------|
| `inst_full` | Yes | No | No |
| `inst_sub` | Yes | No | No |
| `temporal` | No | Yes | Yes |
| `phrase` | No | No | Yes |

These match the settings used in the legacy 10-step pipeline.

## Workflow Integration

Use via the `branching_strip_nway.yaml` workflow template:

```bash
cde-analyzer workflow run workflows/branching_strip_nway.yaml \
    --set input_json=/path/to/cdes.json \
    --set output_dir=/path/to/output \
    --set inst_patterns_base=/path/to/inst_patterns \
    --set phrase_patterns=/path/to/curated_phrases.tsv
```

Or configure for specific variants:

```bash
cde-analyzer workflow configure MTSFPT MFSTPT --nway
```

## Related Commands

- [strip_phrases](strip_phrases.md) — Single-pass phrase stripping (one variant)
- [workflow](workflow.md) — Workflow orchestration (templates, configure)
- [strip_discover](strip_discover.md) — Pattern discovery
