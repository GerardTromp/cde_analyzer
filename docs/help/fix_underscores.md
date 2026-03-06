# `fix_underscores` Command

Fix leading underscores in JSON field names for Pydantic compatibility.

## Overview

Underscores are not permitted as leading characters in Pydantic name tags. This command prepends a configurable prefix character to field names that start with `_`, at any nesting depth in the JSON structure.

## Usage

```bash
cde-analyzer fix_underscores -i input.json [-o output.json] [--prefix x] [--depth N]
```

## Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` INPUT | Full path, including name, of input JSON file (required) |
| `--output`, `-o` OUTPUT | Full path, including name, of output JSON file. If omitted, prints to stdout |
| `--prefix` CHAR | Character to prepend on fields starting with an underscore (default: `x`) |
| `--depth` N | Maximum depth (JSON nesting) to process. `None` = unlimited (default: `None`) |

## Example

```bash
# Fix underscores in raw CDE export
cde-analyzer fix_underscores -i raw_cdes.json -o fixed_cdes.json

# Use custom prefix, limit depth
cde-analyzer fix_underscores -i raw.json -o fixed.json --prefix z --depth 5
```
