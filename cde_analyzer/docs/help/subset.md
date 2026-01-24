# `subset` Command

Extract a subset of CDE records by tinyId with Pydantic validation.

## Overview

The `subset` command filters CDE records based on a list of tinyIds and outputs a smaller, schema-compliant JSON file. All output records are validated against the specified Pydantic model to ensure data integrity.

**Use Cases:**

- Creating focused datasets for specific analyses
- Reducing file size for faster processing
- Isolating records of interest from large CDE exports
- Excluding known problematic records from a dataset

## Usage

```bash
cde_analyzer subset -i INPUT -o OUTPUT -m MODEL [OPTIONS]
```

## Arguments

### Required

| Argument | Description |
|----------|-------------|
| `-i, --input` | Path to input JSON file |
| `-o, --output` | Path to output file |
| `-m, --model` | Pydantic model for validation: `CDE`, `Form`, `EmbedText` |

### tinyId Filtering

At least one of these is required:

| Argument | Description |
|----------|-------------|
| `--id-list` | List of tinyIds on command line |
| `--id-file` | File containing tinyIds (JSON, CSV, or TSV) |

### Options

| Argument | Description |
|----------|-------------|
| `--output-format` | Output format: `json` (default), `csv`, `tsv` |
| `--exclude` | Exclude matching tinyIds instead of including |
| `--no-exclude` | Include matching tinyIds (default) |

## Examples

### Include specific records

```bash
# From command line list
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    -m CDE \
    --id-list abc123 def456 ghi789

# From file
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    -m CDE \
    --id-file selected_ids.txt
```

### Exclude specific records

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_cleaned.json \
    -m CDE \
    --id-file problematic_ids.txt \
    --exclude
```

### Output to TSV

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.tsv \
    -m CDE \
    --id-file ids.txt \
    --output-format tsv
```

## tinyId File Formats

The `--id-file` option supports multiple formats:

### JSON

```json
{
  "tinyId": ["abc123", "def456", "ghi789"]
}
```

### CSV

```csv
tinyId
abc123
def456
ghi789
```

### TSV

```tsv
tinyId
abc123
def456
ghi789
```

Column names can be any of: `tinyId`, `ID`, `Id`, `tinyID`, `IDs`, `Ids`

## Available Models

| Model | Description |
|-------|-------------|
| `CDE` | Full CDE Item schema (CDEItem) |
| `Form` | CDE Form schema (CDEForm) |
| `EmbedText` | Simplified embedding model with tinyId, Name, Question, Definition, PermissibleValues |

### EmbedText Model

The `EmbedText` model is a simplified schema for text embedding workflows:

| Field | Required | Description |
|-------|----------|-------------|
| `tinyId` | Yes | Record identifier |
| `Name` | Yes | CDE name/title |
| `Question` | No | Question text |
| `Definition` | No | CDE definition |
| `PermissibleValues` | No | Permissible values as string |

## Validation

All records in the subset are validated against the specified Pydantic model:

- Records that fail validation are logged with error details
- Successfully validated records are included in the output
- This ensures output files are always schema-compliant

## See Also

- [`extract_embed`](extract_embed.md) - Extract specific fields for embedding
- [`strip_phrases`](strip_phrases.md) - Remove phrases from records
- [`phrase_miner`](../commands/phrase_miner.md) - Detect repeated phrases
