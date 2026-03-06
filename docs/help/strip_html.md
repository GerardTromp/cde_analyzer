# `strip_html` Command

Remove HTML markup from CDE field values.

## Overview

Parses CDE JSON and strips HTML tags from text fields, optionally converting HTML tables to JSON representations. Outputs clean JSON suitable for downstream analysis.

## Usage

```bash
cde-analyzer strip_html -i input.json -m CDE [--outdir DIR] [--output-format FORMAT]
```

## Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` INPUT [INPUT ...] | Input JSON file(s) with underscore tags fixed (required) |
| `--model`, `-m` MODEL | Model to use for validation: `CDE`, `Form`, `Embed`, `EmbedText` (required) |
| `--outdir` DIR | Directory for output files (default: `.`) |
| `--output-format` FORMAT | Output format: `json`, `yaml`, `csv` (default: `json`) |
| `--dry-run` | Do not write output files |
| `--verbosity`, `-v` | Increase verbosity level (`-vv` for debug) |
| `--logfile` FILE | Optional log file path |
| `--pretty` / `--no-pretty` | Produce pretty or minified JSON (default: pretty) |
| `--set-keys` / `--no-set-keys` | Save model with keys only represented if they are set — no null, None, or empty sets (default: on) |
| `--tables` / `--no-tables` | Convert HTML tables to JSON representation (`--tables`) or munged text (`--no-tables`) (default: tables) |
| `--colnames` | Use first row of table as column names. Only relevant if `--tables` |

## Example

```bash
# Strip HTML from CDE JSON
cde-analyzer strip_html -i raw_cdes.json -m CDE --outdir cleaned/

# Minified output, no table conversion
cde-analyzer strip_html -i raw.json -m CDE --no-pretty --no-tables -o cleaned/
```
