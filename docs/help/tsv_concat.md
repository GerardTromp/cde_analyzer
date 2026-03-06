# `tsv_concat` Command

Selective column concatenation producing 2-column id+text TSV.

## Overview

Reads a TSV/CSV file and concatenates selected columns into a single text column, producing a simple 2-column output (ID + text). Useful for preparing embedding input from multi-column pattern or CDE data.

## Usage

```bash
# Concatenate specific columns (whitelist)
cde-analyzer tsv_concat -i data.tsv -o output.tsv --concat col1 col2 col3

# Concatenate all columns except some (blacklist)
cde-analyzer tsv_concat -i data.tsv -o output.tsv --drop tinyId status notes

# Custom separator and header
cde-analyzer tsv_concat -i data.tsv -o output.tsv \
    --concat definition designation \
    --separator " [SEP] " --output-header text
```

## Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` INPUT | Path to input TSV/CSV file (required) |
| `--output`, `-o` OUTPUT | Path to output 2-column TSV (required) |
| `--id-column` COL | Column to use as ID (default: `tinyId`) |
| `--concat` COL [COL ...] | Columns to concatenate (whitelist). Others are dropped. Mutually exclusive with `--drop` |
| `--drop` COL [COL ...] | Columns to exclude (blacklist). Others are concatenated. Mutually exclusive with `--concat` |
| `--separator`, `-s` SEP | Separator between concatenated values (default: ` \| `) |
| `--output-header` NAME | Header name for the concatenated column (default: `embed_text`) |
| `--skip-empty` | Omit rows where concatenated text is empty |

## Output Format

The output is always a 2-column TSV:

```
{id_column}	{output_header}
abc123	value1 | value2 | value3
def456	value1 | value2
```

## Related Commands

- [extract_embed](extract_embed.md) — Extract and concatenate fields from CDE JSON (with Pydantic parsing)
- [lemma_fasta](lemma_fasta.md) — Export lemmatized text
