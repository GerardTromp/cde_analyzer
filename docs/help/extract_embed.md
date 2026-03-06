# `extract_embed` Command

Extract subset of fields from model for embedding text.

## Overview

Flexible extraction of nested Pydantic values and export to format compatible with 'transformers'. Supports field selection via path files, ID filtering, and concatenation of fields into a single embedding column.

## Usage

```bash
# Extract fields to JSON
cde-analyzer extract_embed -i cdes.json -m CDE --path-file paths.txt -o output.json

# Extract and concatenate for embedding
cde-analyzer extract_embed -i cdes.json -m CDE --path-file paths.txt \
    --concatenate " [SEP] " -o output.tsv

# Extract specific IDs only
cde-analyzer extract_embed -i cdes.json -m CDE --path-file paths.txt \
    --id-file ids.csv:tinyId --no-exclude -o subset.json
```

## Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` INPUT | Input JSON file (required) |
| `-m`, `--model` MODEL | Pydantic model appropriate for input file (required). Choices: `CDE`, `Form`, `Embed`, `EmbedText` |
| `--path-file` FILE | File with paths of interest and new name (as `name:path`) for extracted data |
| `-o`, `--output` FILE | Path to store results |
| `--output-format` FORMAT | Output format: `json`, `csv`, `tsv` (default: `json`) |
| `--id-list` ID [ID ...] | List of item IDs (tinyId) to exclude or extract |
| `--id-file` FILE | File containing tinyIds. Use `file:column` format to specify column (e.g., `data.csv:tinyId`). Cells can contain multiple tinyIds (pipe, comma, or space separated) |
| `--id-type` TYPE | The type of ID, e.g., `tinyId` |
| `--exclude` / `--no-exclude` | Exclude (`--exclude`, default) or include (`--no-exclude`) IDs in list |
| `-c`, `--collapse` / `--no-collapse` | Collapse repeated "None;" in list items (default: on) |
| `-s`, `--simplify-permissible` / `--no-simplify-permissible` | Process limited set of permissibleValues fields using heuristic (default: on) |
| `--concatenate` SEP | Concatenate all non-tinyId fields into a single `embed_text` column using SEP as the joining string (e.g., `' \| '` or `' [SEP] '`). Forces output format to csv or tsv |

## Concatenate Mode

The `--concatenate SEP` option merges all extracted fields (except tinyId) into a single `embed_text` column, separated by the given string. This produces a 2-column output (tinyId + embed_text) suitable for embedding pipelines.

```bash
# Produce tinyId + embed_text TSV with pipe separator
cde-analyzer extract_embed -i cdes.json -m CDE --path-file paths.txt \
    --concatenate " | " -o embeddings.tsv
```

## Related Commands

- [tsv_concat](tsv_concat.md) — Concatenate columns from any TSV/CSV (no JSON parsing)
- [lemma_fasta](lemma_fasta.md) — Export lemmatized text for sequence analysis
- [subset](subset.md) — Filter CDE records by ID or text
