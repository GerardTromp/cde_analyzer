# CDE Analyzer

A Python CLI tool for parsing and analyzing Common Data Elements (CDEs) from the National Library of Medicine (NLM) at the National Institutes of Health.

**API Documentation**: [NLM CDE API](https://cde.nlm.nih.gov/api)

## Overview

CDE Analyzer provides a suite of commands for:

- **Phrase Detection**: Find repeated multi-word phrases across CDE records
- **Data Cleaning**: Fix field names, strip HTML markup
- **Analysis**: Count structural elements and field occurrences
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

| Command | Description |
|---------|-------------|
| [phrase-miner](commands/phrase_miner.md) | Advanced k-mer phrase mining with iterative detection |
| [phrase](help/phrase.md) | Find repeated phrases (original implementation) |
| [phrase-builder](help/phrase_builder.md) | K-mer analysis for phrase identification |
| [strip-phrases](help/strip_phrases.md) | Remove curated phrases from CDE documents |
| [count](help/count.md) | Count structural elements and field occurrences |
| [strip-html](help/strip.md) | Remove HTML markup from CDE fields |
| [fix-underscores](help/fix_underscores.md) | Fix Pydantic-incompatible field names |
| [extract-embed](help/extract_embed.md) | Extract fields for transformer embeddings |
| [lemma-fasta](help/lemma_fasta.md) | Create pseudo-FASTA format for genomic tools |
| [subset](help/subset.md) | Extract subsets by tinyId with Pydantic validation |

## Architecture

CDE Analyzer uses a **layered monolithic** architecture with a plugin-style action system:

```
cde_analyzer.py          # Entry point with ACTION_REGISTRY
├── actions/             # Each action has cli.py + run.py
│   ├── phrase_miner/    # Argument parsing + orchestration
│   └── ...
├── logic/               # Business logic implementations
├── utils/               # Helper functions
└── CDE_Schema/          # Pydantic data models
```

**Key Features**:

- **Lazy Loading**: Actions loaded only when invoked (fast startup)
- **Visitor Pattern**: Single recursive engine for nested traversal
- **Three-Layer Actions**: CLI → Orchestration → Logic separation

## Data Model

The CDE repository data structure is implemented as Pydantic models:

- `CDEItem` - Individual data elements
- `CDEForm` - Form structures
- 50+ supporting models for nested structures

All fields are optional to handle sparse API responses, with field aliases mapping MongoDB/API names to Python-safe names.

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
