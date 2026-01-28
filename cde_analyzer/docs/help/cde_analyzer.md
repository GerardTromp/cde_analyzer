# `cde-analyzer` Launcher

The `cde-analyzer` command is the main entry point for all CDE Analyzer commands. It is a **launcher** that dispatches to specialized action modules - it does not perform any analysis itself.

## Usage

```bash
# List all available commands
cde-analyzer --help

# Get help for a specific command
cde-analyzer <command> --help

# Run a command
cde-analyzer <command> [options]
```

## Available Commands

| Command | Description |
|---------|-------------|
| `phrase-miner` | Advanced k-mer phrase mining with iterative detection |
| `phrase` | Original phrase detection using n-gram counting |
| `phrase-builder` | K-mer analysis for phrase identification |
| `strip-phrases` | Remove curated phrases from CDE documents |
| `count` | Count structural elements and field occurrences |
| `strip-html` | Remove HTML markup from CDE fields |
| `fix-underscores` | Fix Pydantic-incompatible field names |
| `extract-embed` | Extract fields for transformer embeddings |
| `lemma-fasta` | Create pseudo-FASTA format for genomic tools |
| `subset` | Extract subsets by tinyId with Pydantic validation |

> **Note**: Command names use **hyphens** on the command line (e.g., `phrase-miner`) following pip/CLI convention. Python module names use underscores internally. Both forms are accepted by argparse.

## Architecture

The launcher uses a **lazy loading** pattern for fast startup:

1. Only the command registry is loaded at startup
2. When a command is invoked, its action module is dynamically imported
3. Each action module contains:
   - `cli.py` - Argument parser registration
   - `run.py` - Command orchestration

This design, inspired by git/pip, enables adding new commands without impacting startup performance.

## Examples

```bash
# Detect repeated phrases in CDE data
cde-analyzer phrase-miner -i cdes.json -o output/

# Extract subset of records
cde-analyzer subset -i cdes.json -o subset.json -m CDE --id-file ids.txt

# Strip HTML from fields
cde-analyzer strip-html --input raw.json --output clean.json -m CDE
```

## See Also

- [CLI Reference](all-commands.md) - Complete command reference
- [Commands Overview](../commands/index.md) - Categorized command guide
