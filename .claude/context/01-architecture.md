# Architecture

## System Overview

The CDE Analyzer is a Python-based CLI tool for parsing, analyzing, and extracting data from the National Library of Medicine's Common Data Elements (CDE) repository. The repository is accessible via a RESTful API at https://cde.nlm.nih.gov/api.

## Architectural Style

**Layered Monolithic with Plugin Architecture**

The system uses a layered architecture with clear separation of concerns:
- **CLI Layer** (actions/*/cli.py) - Argument parsing and command registration
- **Orchestration Layer** (actions/*/run.py) - Action coordination
- **Business Logic Layer** (logic/) - Core processing algorithms
- **Utility Layer** (utils/) - Reusable functions and helpers
- **Data Model Layer** (CDE_Schema/) - Pydantic-based data models
- **Core Engine** (core/) - Recursive descent engine for nested data structures

The "plugin" aspect comes from the lazy-loaded action system where each action is a self-contained module that registers itself with the main dispatcher.

## Major Components

### 1. Main Dispatcher (`cde_analyzer.py`)
- Entry point for all commands
- Implements **max-lazy loading** architecture
- Uses an ACTION_REGISTRY to map command names to modules
- Only imports action modules when invoked (not at startup)
- Inspired by git/pip command architecture
- **Recent refactoring** (commit 4400bf7) to address startup performance

### 2. Action Modules (`actions/`)
Each action follows a consistent 3-file structure:
- `cli.py` - Argument parser registration
- `run.py` - Action orchestration and execution
- `__init__.py` - Package marker

Current actions:
- **fix_underscores** - Fix Pydantic incompatible field names starting with underscore
- **strip_html** - Remove HTML markup from CDE fields
- **phrase** - Find repeated phrases across CDE records (original implementation)
- **phrase_miner** - Advanced k-mer phrase mining with iterative descending detection
- **count** - Count structural elements and field occurrences
- **extract_embed** - Extract fields for transformer embedding
- **strip_phrases** - Remove literal phrases at specified paths
- **lemma_fasta** - Create FASTA format from lemma sequences
- **phrase_builder** - Incremental phrase construction
- **subset** - Extract subsets using literal/regex/tinyID filters
- **llm_classify** - Multi-LLM phrase classification with confidence aggregation (NEW)

### 3. Business Logic (`logic/`)
Core processing implementations:
- **counter.py** - Field counting and type classification
- **phrase_extractor.py** - Phrase detection and extraction (original)
- **phrase_miner.py** - K-mer phrase mining with iterative descending detection (NEW)
- **phrase_anchor_extend.py** - Anchor extension for phrase_miner (placeholder for Phase 7+)
- **phrase_stripper.py** - Phrase removal
- **phrase_builder.py** - Incremental phrase construction
- **extract_embed.py** - Field extraction for embeddings
- **html_stripper.py** - HTML tag removal
- **lemma_fasta.py** - FASTA format generation
- **llm_classifier.py** - LLM-based phrase classification orchestration (NEW)

### 4. Data Models (`CDE_Schema/`)
Pydantic-based object models mirroring the NLM CDE API schema:
- **CDE_Item.py** - CDEItem model (individual data elements)
- **CDE_Form.py** - CDEForm model (form structures)
- **classes.py** - Shared model classes (Source, Designation, Definition, ValueDomain, etc.)
- **EmbedText.py** - EmbedText model for embedding extraction output
- **LLM_Classification.py** - LLM classification result models (NEW)

### 5. LLM Integration Layer (`utils/llm/`) - NEW
Async LLM provider infrastructure for multi-provider classification:
- **config.py** - API key resolution (config file → env vars → CLI)
- **provider_base.py** - Abstract LLMProvider interface
- **provider_claude.py** - Anthropic Claude implementation
- **provider_openai.py** - OpenAI ChatGPT implementation
- **provider_google.py** - Google Gemini implementation
- **rate_limiter.py** - Async rate limiting with token bucket algorithm
- **result_aggregator.py** - Multi-LLM result reconciliation and quintile calculation
- **__init__.py** - Provider factory with lazy loading

### 6. Query Module Framework (`utils/query_modules/`) - NEW
Pluggable classification modules for semantic categorization:
- **module_base.py** - Abstract QueryModule interface
- **instrument_detector.py** - Instrument/device name detection
- **temporal_detector.py** - Temporal pattern detection
- **instrument_family_detector.py** - Instrument family classification (15 categories)
- **__init__.py** - Module registry with lazy loading

### 6b. Instrument Family Detection (`utils/`, `logic/`) - NEW
Two-tier instrument identification and family grouping:
- **instrument_extractor.py** - Pattern-based instrument extraction (InstrumentExtractor, InstrumentCatalog)
- **instrument_family_patterns.py** - Regex patterns for 13 known families (InstrumentFamilyDetector)
- **instrument_family_assigner.py** (logic/) - Orchestration for family assignment workflow

### 7. Recursive Engine (`core/recursor.py`)
- Implements recursive descent pattern
- Traverses nested Pydantic models and dictionaries
- Visitor pattern for processing nodes
- Handles both dictionary and list structures
- Path tracking for field identification

Key characteristic: **Self-referential nesting** - models can contain nested instances of themselves, requiring recursive traversal.

### 8. Utilities (`utils/`)
Reusable functions grouped by purpose:
- **cde_impexport.py** - JSON import/export
- **datatype_check.py** - Type validation utilities
- **designation_parser.py** - Designation field parsing
- **helpers.py** - Common helper functions
- **html.py** - HTML processing
- **logger.py** - Logging configuration
- **output_writer.py** - Formatted output generation
- **path_utils.py** - File path utilities
- **phrase_extraction.py** - Phrase detection algorithms (tokenization, lemmatization)
- **phrase_miner_vocab.py** - Vocabulary class for k-mer phrase mining (token-to-ID mapping)
- **phrase_pruning.py** - Phrase filtering and pruning
- **analyzer_state.py** - Global state management (verbosity)
- **unicode.py** - Unicode handling
- **tinyid_utils.py** - TinyID manipulation

**Legacy/Experimental kmer modules** (retained for reference):
- kmer_phrase_detection.py
- kmer_build_longest_phrases*.py (multiple versions)
- kmer_consolidated_phrases*.py
- kmer_extend_phrases*.py
- kmer_enrich_w_verbatim.py
- kmer_connect_extendedphrase.py
- plot_kmer_counts.py

These represent experimental approaches to finding longest repeated phrases, particularly for identifying common patterns in CDE descriptions.

## Technology Stack

### Core Technologies
- **Language**: Python 3.x
- **Data Modeling**: Pydantic (v1 or v2, models use Field aliases and Optional typing)
- **CLI Framework**: argparse (standard library)
- **Data Format**: JSON (primary), CSV/TSV (output options)

### Standard Library Dependencies
- sys, argparse, importlib - CLI infrastructure
- json, csv - Data serialization
- re - Regular expressions
- logging - Application logging
- collections (defaultdict) - Data structures
- typing - Type hints

### External Dependencies
Based on import analysis:
- **pydantic** - Data validation and modeling (core dependency)
- Likely: **requests** - API interaction (not visible in sampled files)
- Likely: **spacy** or similar - NLP for lemmatization (phrase action)

## Component Communication

### Data Flow Patterns

1. **Command Execution Flow**:
   ```
   User Command
      ↓
   cde_analyzer.py (dispatcher)
      ↓
   ACTION_REGISTRY lookup
      ↓
   Lazy load action module
      ↓
   actions/*/cli.py (parse args)
      ↓
   actions/*/run.py (orchestration)
      ↓
   logic/*.py (business logic)
      ↓
   core/recursor.py (traverse data)
      ↓
   utils/*.py (helper functions)
      ↓
   Output (file or stdout)
   ```

2. **Data Processing Flow**:
   ```
   JSON Input File
      ↓
   Parse as Pydantic models (CDE_Schema)
      ↓
   Recursive traversal (core/recursor.py)
      ↓
   Visitor function processes each node
      ↓
   Accumulate results
      ↓
   Format output (JSON/CSV/TSV)
      ↓
   Write to file or stdout
   ```

3. **Recursive Traversal Pattern**:
   ```python
   recursive_descent(item, path, visitor, context, depth)
      - If dict: recurse on each key-value
      - If list: recurse on each element
      - If scalar: call visitor(path, item, context)
   ```

## Architectural Principles

1. **Lazy Loading**
   - Actions loaded only when invoked
   - Minimizes startup time
   - Reduces memory footprint

2. **Separation of Concerns**
   - CLI parsing separated from logic
   - Logic separated from utilities
   - Data models independent of processing

3. **Extensibility**
   - New actions easily added via ACTION_REGISTRY
   - Consistent action structure (cli.py + run.py)
   - Modular design allows independent development

4. **Recursive Processing**
   - Single recursive engine handles all nested structures
   - Visitor pattern for flexible processing
   - Path tracking for context preservation

5. **Flexible Output**
   - Multiple format support (JSON, CSV, TSV)
   - Configurable verbosity
   - Optional logging to file

## Key Design Decisions

- **Pydantic models**: Type safety, validation, and clear schema definition
- **Lazy action loading**: Performance optimization for CLI startup
- **Recursive visitor pattern**: Handles arbitrary nesting in CDE data
- **Modular action structure**: Each action is self-contained and independently testable
- **Standard library preference**: Minimal external dependencies where possible

## Current State

See `08-progress.md` for current version and status. See `02-codebase-map.md` for
the full directory/action listing.
