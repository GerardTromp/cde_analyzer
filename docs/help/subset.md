# `subset` Command

Extract a subset of CDE records by tinyId or text content with Pydantic validation.

## Overview

The `subset` command filters CDE records and outputs a smaller, schema-compliant JSON file. All output records are validated against the specified Pydantic model to ensure data integrity.

**Two Filtering Modes:**

1. **tinyId filtering** - Include/exclude records by tinyId list
2. **Text filtering** - Include/exclude records containing specific text (NEW)

**Use Cases:**

- Creating focused datasets for specific analyses
- Reducing file size for faster processing
- Isolating records of interest from large CDE exports
- Excluding known problematic records from a dataset
- Extracting records containing specific abbreviations or keywords

## Usage

```bash
# tinyId filtering
cde-analyzer subset -i INPUT -o OUTPUT -m MODEL --id-list ID1 ID2 ...
cde-analyzer subset -i INPUT -o OUTPUT -m MODEL --id-file ids.txt

# Text filtering (NEW)
cde-analyzer subset -i INPUT -o OUTPUT -m MODEL --text-filter "PROMIS"
cde-analyzer subset -i INPUT -o OUTPUT -m MODEL --text-filter "PHQ-\d+" --regex
```

## Arguments

### Required

| Argument | Description |
|----------|-------------|
| `-i, --input` | Path to input JSON file |
| `-o, --output` | Path to output file |
| `-m, --model` | Pydantic model for validation: `CDE`, `Form`, `EmbedText` |

### tinyId Filtering

| Argument | Description |
|----------|-------------|
| `--id-list`, `-l` | List of tinyIds on command line |
| `--id-file`, `-L` | File containing tinyIds (JSON, CSV, or TSV) |

### Text Filtering (NEW)

| Argument | Default | Description |
|----------|---------|-------------|
| `--text-filter`, `-t` | - | Text pattern to search for in specified fields |
| `--fields, -f` | `designation definition` | Fields to search |
| `--case-sensitive` | `false` | Enable case-sensitive matching |
| `--regex` | `false` | Treat `--text-filter` as a regular expression |

**Supported fields:** `designation`, `definition`, `valueMeaningName`, `valueMeaningDefinition`

### Pattern File Filtering

| Argument | Description |
|----------|-------------|
| `--pattern-file`, `-F` FILE | File containing regex patterns (one per line). Like `grep -E -f`, matches records against any pattern. Format: `pattern` or `pattern<TAB>label` for grouping |
| `--match-report` FILE | Output file for detailed match report (TSV with tinyId, matched patterns, labels) |
| `--tinyid-report` FILE | Output file listing matched tinyIds only (one per line, for pipeline chaining) |

### Options

| Argument | Description |
|----------|-------------|
| `--output-format` | Output format: `json` (default), `csv`, `tsv` |
| `--exclude`, `-x` | Exclude matching records instead of including |
| `--no-exclude` | Include matching records (default) |

## Examples

### tinyId Filtering

```bash
# Include specific records from command line
cde-analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    -m CDE \
    --id-list abc123 def456 ghi789

# Include from file
cde-analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    -m CDE \
    --id-file selected_ids.txt

# Exclude specific records
cde-analyzer subset \
    -i cdes_full.json \
    -o cdes_cleaned.json \
    -m CDE \
    --id-file problematic_ids.txt \
    --exclude
```

### Text Filtering (NEW)

```bash
# Find all CDEs containing "PROMIS"
cde-analyzer subset \
    -i cdes.json \
    -o promis_subset.json \
    -m CDE \
    --text-filter "PROMIS"

# Search only in definitions
cde-analyzer subset \
    -i cdes.json \
    -o results.json \
    -m CDE \
    --text-filter "Patient Health Questionnaire" \
    --fields definition

# Case-sensitive search
cde-analyzer subset \
    -i cdes.json \
    -o results.json \
    -m CDE \
    --text-filter "PHQ-9" \
    --case-sensitive

# Regex: find PHQ variants (PHQ-9, PHQ-2, PHQ-15)
cde-analyzer subset \
    -i cdes.json \
    -o phq_subset.json \
    -m CDE \
    --text-filter "PHQ-\d+" \
    --regex

# Exclude CDEs containing certain text
cde-analyzer subset \
    -i cdes.json \
    -o no_promis.json \
    -m CDE \
    --text-filter "PROMIS" \
    --exclude

# Search in permissible values
cde-analyzer subset \
    -i cdes.json \
    -o results.json \
    -m CDE \
    --text-filter "Not applicable" \
    --fields valueMeaningName valueMeaningDefinition
```

### Output Formats

```bash
# Output to TSV
cde-analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.tsv \
    -m CDE \
    --text-filter "SF-36" \
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

## Text Filtering Details

The text filter searches for the pattern in the specified fields:

- **designation**: Searches `designations[*].designation` (CDE names/questions)
- **definition**: Searches `definitions[*].definition` (CDE descriptions)
- **valueMeaningName**: Searches `valueDomain.permissibleValues[*].valueMeaningName`
- **valueMeaningDefinition**: Searches `valueDomain.permissibleValues[*].valueMeaningDefinition`

**Performance:** Text filtering operates on raw dictionaries before Pydantic validation, making it fast for large files. Only matching records undergo full validation.

## Validation

All records in the subset are validated against the specified Pydantic model:

- Records that fail validation are logged with error details
- Successfully validated records are included in the output
- This ensures output files are always schema-compliant

## See Also

- [`batch_expand_abbreviations`](batch_expand_abbreviations.md) - Batch expand abbreviations using text filtering
- [`extract_embed`](extract_embed.md) - Extract specific fields for embedding
- [`strip_phrases`](strip_phrases.md) - Remove phrases from records
- [`phrase_miner`](phrase_miner.md) - Detect repeated phrases
