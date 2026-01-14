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
- **phrase** - Find repeated phrases across CDE records
- **count** - Count structural elements and field occurrences
- **extract_embed** - Extract fields for transformer embedding
- **strip_phrases** - Remove literal phrases at specified paths
- **lemma_fasta** - Create FASTA format from lemma sequences
- **phrase_builder** - Incremental phrase construction
- **subset** - Extract subsets using literal/regex/tinyID filters

### 3. Business Logic (`logic/`)
Core processing implementations:
- **counter.py** - Field counting and type classification
- **phrase_extractor.py** - Phrase detection and extraction
- **phrase_stripper.py** - Phrase removal
- **phrase_builder.py** - Incremental phrase construction
- **extract_embed.py** - Field extraction for embeddings
- **html_stripper.py** - HTML tag removal
- **lemma_fasta.py** - FASTA format generation

### 4. Data Models (`CDE_Schema/`)
Pydantic-based object models mirroring the NLM CDE API schema:
- **CDE_Item.py** - CDEItem model (individual data elements)
- **CDE_Form.py** - CDEForm model (form structures)
- **classes.py** - Shared classes (Source, Designation, Definition, ValueDomain, etc.)

Key characteristic: **Self-referential nesting** - models can contain nested instances of themselves, requiring recursive traversal.

### 5. Recursive Engine (`core/recursor.py`)
- Implements recursive descent pattern
- Traverses nested Pydantic models and dictionaries
- Visitor pattern for processing nodes
- Handles both dictionary and list structures
- Path tracking for field identification

### 6. Utilities (`utils/`)
Reusable functions grouped by purpose:
- **cde_impexport.py** - JSON import/export
- **datatype_check.py** - Type validation utilities
- **designation_parser.py** - Designation field parsing
- **helpers.py** - Common helper functions
- **html.py** - HTML processing
- **logger.py** - Logging configuration
- **output_writer.py** - Formatted output generation
- **path_utils.py** - File path utilities
- **phrase_extraction.py** - Phrase detection algorithms
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

- **Active branch**: Repeats (working on repeated phrase detection)
- **Main branch**: Stable, up-to-date
- **Recent focus**: Lazy loading refactoring, launcher performance, phrase analysis
