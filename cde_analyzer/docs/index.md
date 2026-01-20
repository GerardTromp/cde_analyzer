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
python cde_analyzer.py phrase_miner --help
```

## Available Commands

| Command | Description |
|---------|-------------|
| [phrase_miner](commands/phrase_miner.md) | Advanced k-mer phrase mining with iterative detection |
| [phrase](help/phrase.md) | Find repeated phrases (original implementation) |
| [count](help/count.md) | Count structural elements and field occurrences |
| [extract_embed](help/extract_embed.md) | Extract fields for transformer embeddings |
| [strip_html](help/strip.md) | Remove HTML markup from CDE fields |
| [fix_underscores](help/fix_underscores.md) | Fix Pydantic-incompatible field names |
| phrase_builder | Incremental phrase construction |
| strip_phrases | Remove literal phrases at specified paths |
| lemma_fasta | Create FASTA format from lemma sequences |
| subset | Extract subsets using literal/regex/tinyID filters |

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
