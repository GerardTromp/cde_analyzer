# `subset` Command

Extract a subset of CDE records matching specified criteria.

> **Status**: This command is currently a stub under development.

## Overview

The `subset` command filters CDE records based on specified criteria (such as a list of tinyIds) and outputs a smaller, compliant JSON file. This is useful for:

- Creating focused datasets for specific analyses
- Reducing file size for faster processing
- Isolating records of interest from large CDE exports

## Planned Usage

```bash
cde_analyzer subset -i INPUT [OPTIONS]
```

## Current Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Input JSON file |

## Planned Features

The following features are planned for implementation:

### Filter by tinyId List

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    --tinyid-file selected_ids.txt
```

Or inline:

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    --tinyids abc123 def456 ghi789
```

### Filter by Field Value

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    --path "stewardship.organization" \
    --value "NCI"
```

### Filter by Regex

```bash
cde_analyzer subset \
    -i cdes_full.json \
    -o cdes_subset.json \
    --path "designations.*.designation" \
    --regex "cancer|oncology"
```

## Expected Output

- **Subset JSON**: Records matching the filter criteria
- **Validation**: Output validated against CDE Pydantic models to ensure schema compliance

## Planned Arguments

| Argument | Description |
|----------|-------------|
| `-i, --input` | Input JSON file |
| `-o, --output` | Output JSON file |
| `-m, --model` | Pydantic model (CDEItem, CDEForm) |
| `--tinyids` | List of tinyIds to include |
| `--tinyid-file` | File containing tinyIds (one per line) |
| `--exclude` | Exclude matching records instead of including |
| `--path` | Pydantic path to filter on |
| `--value` | Exact value to match |
| `--regex` | Regex pattern to match |

## Use Cases

1. **Extract specific CDEs**: Given a list of tinyIds from a study, extract only those records
2. **Organization-specific subsets**: Filter by stewardship organization
3. **Topic-based filtering**: Use regex to find CDEs related to specific domains
4. **Exclusion filtering**: Remove known problematic records from a dataset

## Notes

- This command is under development
- Schema compliance is ensured via Pydantic model validation
- Contributions welcome to expand filtering capabilities
