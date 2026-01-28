# Commands Overview

CDE Analyzer provides a suite of CLI commands for processing and analyzing Common Data Elements.

## Instrument Extraction

| Command | Description | Status |
|---------|-------------|--------|
| [instrument_miner](../help/instrument_miner.md) | Extract measurement instruments from CDE text using anchor detection | Stable |

## Phrase Detection & Analysis

| Command | Description | Status |
|---------|-------------|--------|
| [phrase_miner](../help/phrase_miner.md) | Advanced k-mer phrase mining with iterative detection | Stable |
| [phrase_grouper](../help/phrase_grouper.md) | Bottom-up k-mer analysis for phrase family discovery | New |
| [phrase](../help/phrase.md) | Original phrase detection using n-gram counting | Stable |
| [phrase_builder](../help/phrase_builder.md) | K-mer analysis for phrase identification | Stable |

## Pattern Stripping

| Command | Description | Status |
|---------|-------------|--------|
| [strip_discover](../help/strip_discover.md) | Flexible regex discovery for pattern curation workflow | Stable |
| [strip_phrases](../help/strip_phrases.md) | Remove detected phrases using exact string replacement | Stable |
| [diagnose_strip](../help/diagnose_strip.md) | Diagnose remaining patterns after stripping | Stable |

## Data Cleaning

| Command | Description | Status |
|---------|-------------|--------|
| [fix_underscores](../help/fix_underscores.md) | Fix Pydantic-incompatible field names (underscore prefix) | Stable |
| [strip_html](../help/strip.md) | Remove HTML markup from CDE fields | Stable |

## Analysis

| Command | Description | Status |
|---------|-------------|--------|
| [count](../help/count.md) | Count structural elements and field occurrences | Stable |
| [extract_embed](../help/extract_embed.md) | Extract fields for transformer embeddings | Stable |

## Export & Filtering

| Command | Description | Status |
|---------|-------------|--------|
| [lemma_fasta](../help/lemma_fasta.md) | Create FASTA format from lemma sequences | Stable |
| [subset](../help/subset.md) | Extract subsets by tinyId with Pydantic validation | Stable |

## LLM-Assisted Classification

!!! info "External API Required"
    These commands require API keys for LLM providers. See [LLM Configuration](../llm/configuration.md).

| Command | Description | Status |
|---------|-------------|--------|
| [llm_classify](../llm/llm_classify.md) | Multi-LLM phrase classification with confidence aggregation | New |

**Available Modules**:

- **instrument**: Detect measurement instruments, devices, assessment tools
- **temporal**: Identify temporal patterns (recency, age ranges, durations)

See the [LLM Classification](../llm/index.md) section for comprehensive documentation.

## Usage Pattern

All commands follow the same basic pattern:

```bash
cde-analyzer <command> --input <file.json> [options]
```

## Getting Help

```bash
# List all commands
cde-analyzer --help

# Get help for a specific command
cde-analyzer <command> --help

# Example
cde-analyzer phrase_miner --help
```

## Common Options

Most commands share these common options:

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input JSON file |
| `--output`, `-o` | Output file or directory |
| `--output-format` | Output format (json, csv, tsv) |
| `--fields`, `-f` | Field names to process |

## Workflow Examples

### Typical Data Processing Pipeline

```bash
# 1. Fix field names for Pydantic compatibility
cde-analyzer fix_underscores --input raw_data.json --output fixed.json

# 2. Strip HTML markup
cde-analyzer strip_html --input fixed.json --output cleaned.json --model CDE

# 3. Find repeated phrases
cde-analyzer phrase_miner --input cleaned.json --output-dir phrases

# 4. Analyze results
cde-analyzer count --input cleaned.json --fields designation --output counts.json
```

### Phrase Detection Comparison

```bash
# Original phrase detection (n-gram based)
cde-analyzer phrase --input data.json --fields designation --output phrases.json

# NEW: Advanced k-mer mining (longest-first with masking)
cde-analyzer phrase_miner --input data.json --output-dir phrase_output
```

### Subsetting Records

```bash
# Extract specific CDEs by tinyId list
cde-analyzer subset -i cdes_full.json -o subset.json -m CDE --id-file ids.txt

# Exclude problematic records
cde-analyzer subset -i cdes.json -o cleaned.json -m CDE --id-list bad1 bad2 --exclude
```

### LLM-Assisted Classification

```bash
# 1. Extract phrases
cde-analyzer phrase_miner --input cdes.json --output-dir phrase_output

# 2. Classify with LLMs (requires API keys)
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument \
  --providers claude openai

# 3. Review high-confidence results
grep "highly_likely" llm_output/classified_instrument.tsv
```
