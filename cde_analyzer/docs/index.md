# CDE Analyzer

**Version 0.5.1** | [Changelog](../CHANGELOG.md)

A Python CLI tool for parsing and analyzing Common Data Elements (CDEs) from the National Library of Medicine (NLM) at the National Institutes of Health.

**API Documentation**: [NLM CDE API](https://cde.nlm.nih.gov/api)

## Overview

CDE Analyzer provides a suite of commands for:

- **Phrase Detection**: Find repeated multi-word phrases across CDE records
- **Pattern Stripping**: Remove boilerplate phrases with automated remnant cleanup
- **Data Cleaning**: Fix field names, strip HTML markup
- **Analysis**: Count structural elements and field occurrences
- **Reporting**: Generate pipeline summary reports with remnant analysis
- **Export**: Extract fields for embedding models, generate FASTA format

## Quick Start

```bash
# Get help
python cde_analyzer.py --help

# List available commands
python cde_analyzer.py

# Get help for a specific command
python cde_analyzer.py phrase-miner --help
```

## Available Commands

> **Note**: Command names use **hyphens** on the command line (e.g., `phrase-miner`) following pip/CLI convention. Both hyphen and underscore forms work.

### Phrase Detection & Mining

| Command | Description |
|---------|-------------|
| [phrase-miner](help/phrase_miner.md) | Advanced k-mer phrase mining with iterative detection |
| [phrase](help/phrase.md) | Find repeated phrases (original implementation) |
| [phrase-builder](help/phrase_builder.md) | K-mer analysis for phrase identification |
| [phrase-grouper](help/phrase_grouper.md) | Group phrases by shared prefix with POS boundary detection |

### Pattern Stripping & Discovery

| Command | Description |
|---------|-------------|
| [strip-phrases](help/strip_phrases.md) | Remove curated phrases with remnant cleanup |
| [strip-discover](help/strip_discover.md) | Discover verbatim pattern occurrences in CDE text |
| [strip-analyze](help/strip_analyze.md) | Pattern conflict and false-negative analysis |
| [pattern-util](help/pattern_util.md) | TSV utilities: merge, coalesce, field analysis, import |
| [diagnose-strip](help/diagnose_strip.md) | Diagnose strip results and suggest patterns |

### Instrument Detection

| Command | Description |
|---------|-------------|
| [instrument-miner](help/instrument_miner.md) | Mine instrument patterns with family detection |

### Reporting & Analysis

| Command | Description |
|---------|-------------|
| [discovery-report](help/discovery_report.md) | Generate pipeline summary reports |
| [recall-analyze](help/recall_analyze.md) | Pattern recall analysis with ground truth comparison |
| [pipeline-report](help/pipeline_report.md) | Generate comprehensive pipeline reports |
| [strip-report](help/strip_report.md) | Quality report for stripped outputs (remnants, temporal phrases) |
| [count](help/count.md) | Count structural elements and field occurrences |

### Data Cleaning & Export

| Command | Description |
|---------|-------------|
| [strip-html](help/strip.md) | Remove HTML markup from CDE fields |
| [fix-underscores](help/fix_underscores.md) | Fix Pydantic-incompatible field names |
| [extract-embed](help/extract_embed.md) | Extract fields for transformer embeddings |
| [lemma-fasta](help/lemma_fasta.md) | Create pseudo-FASTA format for genomic tools |
| [subset](help/subset.md) | Extract subsets by tinyId with Pydantic validation |

### Workflows & Automation

| Command | Description |
|---------|-------------|
| [workflow](help/workflow.md) | Execute YAML-defined multi-step pipelines |
| [llm-classify](help/llm_classify.md) | Multi-LLM phrase classification |
| [batch-expand-abbreviations](help/batch_expand_abbreviations.md) | Batch expand abbreviations in TSV files |

## Documentation

- [Overview](overview.md) --- Project motivation, pipeline summary, and architecture
- [Workflow Architecture](workflow-architecture.md) --- Pipeline diagrams and command reference
- [Commands Overview](commands/index.md) --- All commands organized by category

### Guides

- [Curation Guide](curation-guide.md) --- Decision guidelines for human pattern curation
- [Phrase Miner Logic](phrase_miner_logic.md) --- Algorithm internals and data flow

### Workflows

- [Instrument & Phrase Stripping](workflows/instrument-phrase-stripping-workflow.md) --- 6-phase conceptual workflow
- [Instrument Detection Pipeline](workflows/instrument-detection-workflow.md) --- Automated YAML pipeline

### Vignettes

- [Phrase Stripping](vignettes/phrase-stripping.md) --- From raw CDE JSON to cleaned output (6 scenarios)

## Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/cde-clustering.git
cd cde-clustering/cde_analyzer

# Install dependencies (TODO: create requirements.txt)
pip install pydantic nltk

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"
```

## License

See [LICENSE](../LICENSE) for details.
