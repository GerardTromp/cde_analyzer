# `strip_phrases` Command

Remove curated phrases from specific paths in CDE JSON documents.

## Overview

The `strip_phrases` command processes CDE data and removes or replaces specified phrases at designated paths within the JSON structure. This is essential for cleaning CDE text fields before embedding or clustering operations, where certain repeated phrases (e.g., boilerplate text, standardized prefixes) may interfere with semantic analysis.

## Usage

```bash
cde-analyzer strip_phrases -i INPUT -m MODEL -p PHRASES -o OUTPUT [OPTIONS]
```

## Required Arguments

| Argument | Description |
|----------|-------------|
| `-i, --input` | Path to input JSON file containing CDE records |
| `-m, --model` | Pydantic model name (e.g., `CDEItem`, `CDEForm`) |
| `-p, --phrases` | Path to phrases file (JSON, CSV, or TSV) |
| `-o, --output` | Path to output JSON file |

## Optional Arguments

| Argument | Description |
|----------|-------------|
| `-d, --diff` | Show diff between original and cleaned JSON |
| `--diff-output FILE` | Write diff information to a file |
| `-c, --color` | Colorize diff output |
| `--summary` | Show summary of changed lines |
| `-C, --context N` | Number of context lines before/after changes (default: 3) |

## Phrases File Format

The phrases file specifies which phrases to remove and from where. Supports JSON, CSV, or TSV formats.

### JSON Format

```json
[
  {
    "path": "designations.*.designation",
    "phrase": "This is a repeated phrase",
    "replace": "",
    "tinyIds": ["abc123", "def456"]
  },
  {
    "path": "definitions.*.definition",
    "phrase": "Standard boilerplate: ",
    "replace": ""
  }
]
```

### TSV/CSV Format

```
path	phrase	replace	tinyIds
designations.*.designation	This is a repeated phrase		abc123 def456
definitions.*.definition	Standard boilerplate:
```

### Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| `path` | Yes | Dot-separated path with wildcard support (e.g., `definitions.*.definition`) |
| `phrase` | Yes | Exact phrase to match and remove/replace |
| `replace` | No | Replacement text (default: empty string for deletion) |
| `tinyIds` | No | Space-separated list of tinyIds to apply this rule to (if omitted, applies to all) |

## Path Syntax

Paths use dot notation with wildcard support:

- `designations.*.designation` - All designation fields
- `definitions[0].definition` - First definition only
- `valueDomain.permissibleValues.*.permissibleValue` - Nested arrays

## Examples

### Basic Usage

Remove phrases from all CDE records:

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json \
    -m CDEItem \
    -p phrases_to_remove.tsv \
    -o cdes_cleaned.json
```

### With Diff Output

See what changed:

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json \
    -m CDEItem \
    -p phrases_to_remove.json \
    -o cdes_cleaned.json \
    --diff --color --summary
```

### Save Diff to File

```bash
cde-analyzer strip_phrases \
    -i cdes_raw.json \
    -m CDEItem \
    -p phrases_to_remove.tsv \
    -o cdes_cleaned.json \
    --diff-output changes.diff \
    --context 5
```

## Workflow Integration

This command is typically used after phrase detection:

1. **Detect phrases** using `phrase_miner` or `phrase` commands
2. **Curate phrase list** - manually review and select phrases for removal
3. **Strip phrases** using this command
4. **Validate output** - use `--diff` to verify changes
5. **Use cleaned data** for embedding or clustering

## Output

The command produces:

- **Output JSON**: Cleaned CDE records in the same format as input
- **Diff output** (optional): Shows all modifications made

## Notes

- Phrase matching is exact (verbatim) - no regex support in phrases
- Multiple spaces are normalized after phrase removal
- Empty strings after stripping are preserved (not deleted)
- The command validates output against the Pydantic model to ensure schema compliance
