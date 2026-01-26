# Codebase Map

## Directory Structure

```
cde_analyzer/
├── .claude/                    # Checkpoint system (git-ignored sessions/checkpoints)
│   ├── checkpoints/           # Full and incremental snapshots
│   ├── context/               # Context documentation (THIS FILE)
│   ├── sessions/              # Session notes
│   ├── memory-bank/           # Lessons learned
│   ├── CHECKPOINT_PROMPTS.md  # Checkpoint creation prompts
│   └── CHECKPOINT_SYSTEM.md   # System documentation
│
├── .vscode/                   # VSCode configuration
├── __pycache__/              # Python bytecode cache
│
├── config/                   # Configuration files (YAML)
│   └── supplementary_patterns.yaml  # Non-Title-Case instrument patterns (195 lines, 27+ patterns)
│
├── CDE_Schema/               # Pydantic data models
│   ├── __init__.py
│   ├── CDE_Item.py          # CDEItem model (42 lines)
│   ├── CDE_Form.py          # CDEForm model (86 lines)
│   ├── EmbedText.py         # EmbedText model for embedding output
│   ├── LLM_Classification.py # LLM classification result models (NEW)
│   └── classes.py           # Shared model classes (>150 lines)
│
├── actions/                  # CLI action modules (plugin architecture)
│   ├── __init__.py
│   ├── count/               # Count structural elements
│   │   ├── __init__.py
│   │   ├── cli.py          # Argument parser
│   │   └── run.py          # Action orchestration
│   ├── extract_embed/       # Extract for transformer embedding
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── fix_underscores/     # Fix Pydantic-incompatible field names
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── lemma_fasta/         # Generate FASTA from lemmas
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── llm_classify/        # Multi-LLM phrase classification (NEW)
│   │   ├── __init__.py
│   │   ├── cli.py           # Argument parser (128 lines)
│   │   └── run.py           # Action orchestration (196 lines)
│   ├── phrase/              # Repeated phrase detection
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── phrase_builder/      # Incremental phrase construction
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── phrase_miner/        # Advanced k-mer phrase mining (NEW)
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── strip_html/          # Remove HTML markup
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── strip_discover/      # Discover instrument patterns (NEW)
│   │   ├── cli.py           # Discovery CLI options (216 lines, multiple modes)
│   │   └── run.py           # Discovery logic (692 lines, 5 modes)
│   ├── strip_phrases/       # Remove literal phrases
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── run.py
│   ├── diagnose_strip/      # Diagnose remaining patterns (NEW)
│   │   ├── cli.py           # Diagnostic CLI options
│   │   └── run.py           # Diagnostic logic
│   └── subset/              # Extract data subsets
│       ├── __init__.py
│       ├── cli.py
│       └── run.py
│
├── core/                     # Core processing engines
│   └── recursor.py          # Recursive descent visitor (25 lines)
│
├── docs/                     # Documentation
│   ├── commands/            # Command documentation
│   │   ├── index.md         # Commands overview
│   │   └── phrase_miner.md  # phrase_miner detailed docs
│   ├── help/
│   │   ├── all-commands.md  # Command reference
│   │   ├── llm_classify.md  # llm_classify CLI synopsis (NEW)
│   │   └── ...              # Other help files
│   └── llm/                  # LLM Classification docs (NEW)
│       ├── index.md         # LLM module overview (152 lines)
│       ├── llm_classify.md  # Comprehensive command guide (379 lines)
│       ├── configuration.md # API key setup (324 lines)
│       └── query_modules.md # Module reference (319 lines)
│
├── logic/                    # Business logic implementations
│   ├── counter.py           # Field counting logic (~50 lines visible)
│   ├── extract_embed.py     # Embedding extraction logic
│   ├── html_stripper.py     # HTML removal logic
│   ├── instrument_family_assigner.py # Family assignment orchestration (NEW)
│   ├── lemma_fasta.py       # FASTA generation logic
│   ├── llm_classifier.py    # LLM classification orchestration (506 lines) (NEW)
│   ├── phrase_anchor_extend.py # Anchor extension with bigram model (373 lines)
│   ├── phrase_builder.py    # Phrase construction logic
│   ├── phrase_extractor.py  # Phrase detection logic (original)
│   ├── phrase_miner.py      # Core k-mer mining algorithm (~430 lines)
│   ├── phrase_stripper.py   # Phrase removal logic
│   ├── verbatim_discoverer.py # Verbatim pattern discovery (~300 lines)
│   └── phrase_family_analyzer.py # Phrase family analysis
│
├── scripts/                  # Utility scripts
│   └── export_help_docs.py  # Help documentation generator
│
├── tests/                    # Unit tests
│   └── test_helpers.py      # Tests for helper functions
│
├── utils/                    # Utility functions
│   ├── __pycache__/
│   │
│   ├── llm/                  # LLM provider infrastructure (NEW)
│   │   ├── __init__.py       # Provider factory (200 lines)
│   │   ├── config.py         # API key resolution (325 lines)
│   │   ├── provider_base.py  # Abstract LLMProvider (293 lines)
│   │   ├── provider_claude.py # Anthropic Claude (262 lines)
│   │   ├── provider_openai.py # OpenAI ChatGPT (267 lines)
│   │   ├── provider_google.py # Google Gemini (289 lines)
│   │   ├── rate_limiter.py   # Async rate limiting (356 lines)
│   │   └── result_aggregator.py # Multi-LLM aggregation (401 lines)
│   │
│   ├── query_modules/        # Query module framework (NEW)
│   │   ├── __init__.py       # Module registry (174 lines)
│   │   ├── module_base.py    # Abstract QueryModule (310 lines)
│   │   ├── instrument_detector.py # Instrument detection (154 lines)
│   │   ├── temporal_detector.py # Temporal patterns (196 lines)
│   │   └── instrument_family_detector.py # LLM family adjudication (NEW)
│   │
│   ├── instrument_extractor.py # Instrument pattern detection (~300 lines)
│   ├── instrument_family_patterns.py # Family detection patterns (NEW)
│   │
│   ├── analyzer_state.py    # Global state (verbosity) (459 bytes)
│   ├── cde_impexport.py     # JSON import/export (2.0 KB)
│   ├── config_loader.py     # YAML config loader with caching (~110 lines)
│   ├── flexible_pattern_matcher.py # Flexible regex pattern matching (~400 lines)
│   ├── pattern_variant_generator.py # Spelling/punctuation variants (~200 lines)
│   ├── file_utils.py         # File utilities
│   ├── histogram_generator.py # Histogram generation
│   ├── context_aware_masking.py # Context-aware masking
│   ├── constants.py         # Constants (542 bytes)
│   ├── datatype_check.py    # Type validation (1.4 KB)
│   ├── designation_parser.py # Designation parsing (1.5 KB)
│   ├── diff_utils.py        # Diff utilities (1.7 KB)
│   ├── extract_embed.py     # Embedding extraction (5.5 KB)
│   ├── helpers.py           # Common helpers (5.9 KB)
│   ├── html.py              # HTML processing (5.4 KB)
│   ├── logger.py            # Logging config (872 bytes)
│   ├── output_writer.py     # Output formatting (1.9 KB)
│   ├── path_utils.py        # Path utilities (2.6 KB)
│   ├── phrase_builder.py    # Phrase building (1.4 KB)
│   ├── phrase_extraction.py # Phrase extraction (9.4 KB)
│   ├── phrase_miner_vocab.py # Vocabulary for phrase_miner (54 lines)
│   ├── phrase_pruning.py    # Phrase filtering (3.1 KB)
│   ├── verbatim_tracker.py  # Verbatim text recovery (PrefixTrie) (~200 lines)
│   ├── verbatim_coalesce.py # Case-insensitive verbatim grouping (~150 lines)
│   ├── verbatim_template.py # Template extraction from verbatim variants (~250 lines)
│   ├── verbatim_diff.py     # Diff annotation for verbatim comparison (~100 lines)
│   ├── subsumption_filter.py # Phrase subsumption filtering (~230 lines)
│   ├── aho_corasick_token.py # Token-based Aho-Corasick automaton (~150 lines)
│   ├── debruijn_graph.py    # De Bruijn graph extension (~200 lines)
│   ├── tinyid_utils.py      # TinyID utilities (1.5 KB)
│   ├── unicode.py           # Unicode normalization (156 substitutions)
│   ├── lemma_fasta.py       # FASTA lemma utils (7.4 KB)
│   ├── plot_kmer_counts.py  # LEGACY: Kmer visualization (5.9 KB)
│   │
│   └── [LEGACY KMER MODULES - Experimental phrase detection approaches]
│       ├── kmer_phrase_detection.py        (2.3 KB)
│       ├── kmer_build_longest_phrases.py   (2.3 KB)
│       ├── kmer_build_longest_phrases2.py  (2.7 KB)
│       ├── kmer_build_longest_phrases3.py  (2.7 KB)
│       ├── kmer_build_longest_phrases4.py  (3.0 KB)
│       ├── kmer_consolidated_phrases1.py   (1.6 KB)
│       ├── kmer_consolidated_phrases2.py   (1.4 KB)
│       ├── kmer_connect_extendedphrase.py  (3.9 KB)
│       ├── kmer_extend_phrases1.py         (3.8 KB)
│       ├── kmer_extend_phrases2.py         (2.7 KB)
│       ├── kmer_extend_phrases3.py         (3.5 KB)
│       └── kmer_enrich_w_verbatim.py       (1.7 KB)
│
├── cde_analyzer.py           # ENTRY POINT: Main CLI dispatcher (145 lines)
├── CLAUDE.md                 # Project overview for Claude
├── README.md                 # User-facing documentation (97 lines)
├── .gitignore                # Git ignore rules
├── test1.py                  # Test file (304 bytes)
├── test2.py                  # Test file (716 bytes)
└── load_times4.log          # Performance profiling log (13.9 KB)
```

## Entry Points

### Primary Entry Point
- **cde_analyzer.py** (or `cde_analyzer` executable)
  - Main CLI dispatcher
  - Loads actions lazily based on command
  - Configures logging and verbosity
  - Uses ACTION_REGISTRY for command mapping

### Action Entry Points
Each action in `actions/*/cli.py` registers itself via:
```python
def register_subparser(subparser: ArgumentParser):
    # Add arguments
    subparser.set_defaults(func=run_action)
```

Then `actions/*/run.py` implements:
```python
def run_action(args):
    # Orchestrate the action logic
```

## Module Dependencies

### Internal Dependency Graph

```
cde_analyzer.py
  ├─→ utils.logger
  ├─→ utils.analyzer_state
  └─→ actions.*  (lazy loaded)
      └─→ actions.*/run.py
          └─→ logic.*
              ├─→ core.recursor
              ├─→ utils.datatype_check
              ├─→ utils.helpers
              ├─→ utils.analyzer_state
              └─→ utils.logger

CDE_Schema/*.py
  └─→ pydantic (external)

logic/*.py
  ├─→ core.recursor
  ├─→ CDE_Schema.* (models)
  └─→ utils.* (various)

core/recursor.py
  └─→ (no internal dependencies, pure recursion)
```

### Dependency Layers (Bottom-Up)
1. **Foundation**: pydantic, standard library
2. **Core Engine**: core/recursor.py (no dependencies)
3. **Data Models**: CDE_Schema/*.py (depends on pydantic)
4. **Utilities**: utils/*.py (some depend on each other)
5. **Business Logic**: logic/*.py (depends on core, utils, models)
6. **Actions**: actions/*/*.py (depends on logic, utils)
7. **CLI**: cde_analyzer.py (depends on utils, lazy-loads actions)

## Hot Files (Frequently Changed)

Based on git history (last 90 days):

### Most Active Files (3+ changes)
1. **cde_analyzer/actions/subset/cli.py** - Recent launcher fixes
2. **cde_analyzer/actions/lemma_fasta/cli.py** - Recent launcher fixes
3. **cde_analyzer/actions/extract_embed/cli.py** - Recent launcher fixes, embed feature development

### Moderately Active (2 changes)
- cde_analyzer/cde_analyzer.py - Lazy loading refactor
- cde_analyzer/actions/*/cli.py - Multiple actions updated for launcher compatibility
- cde_analyzer/actions/*/run.py - Action logic updates
- cde_analyzer/utils/constants.py - Constants refinement

### Development Focus Areas
- **Launcher architecture** - Major refactoring for lazy loading (commit 4400bf7)
- **CLI modules** - Widespread updates across all actions
- **Phrase detection** - Multiple legacy kmer modules, now refined to current approach
- **Extract/embed functionality** - Recent feature additions

## Stable Files (Core Infrastructure)

### Rarely Changed Since Initial Development
- **core/recursor.py** - Recursive engine, stable design
- **CDE_Schema/CDE_Item.py** - Data model matches API spec
- **CDE_Schema/CDE_Form.py** - Data model matches API spec
- **CDE_Schema/classes.py** - Shared classes, stable
- **utils/logger.py** - Simple logging configuration
- **utils/analyzer_state.py** - Minimal state management
- **utils/datatype_check.py** - Stable utility functions

### Test Infrastructure
- **tests/test_helpers.py** - Basic test structure (needs expansion)

## Key Files by Function

### Data Model Definition
- CDE_Schema/CDE_Item.py
- CDE_Schema/CDE_Form.py
- CDE_Schema/classes.py

### CLI Infrastructure
- cde_analyzer.py (dispatcher)
- actions/*/cli.py (argument parsing)
- actions/*/run.py (action orchestration)

### Core Processing
- core/recursor.py (traversal engine)
- logic/counter.py (counting)
- logic/phrase_extractor.py (phrase detection - original)
- logic/phrase_miner.py (phrase detection - k-mer mining)
- logic/phrase_stripper.py (phrase removal)
- logic/html_stripper.py (HTML cleaning)
- logic/llm_classifier.py (LLM phrase classification - NEW)

### LLM Integration (NEW)
- utils/llm/config.py (API key resolution)
- utils/llm/provider_base.py (abstract provider)
- utils/llm/provider_claude.py (Claude implementation)
- utils/llm/provider_openai.py (OpenAI implementation)
- utils/llm/provider_google.py (Gemini implementation)
- utils/llm/rate_limiter.py (async rate limiting)
- utils/llm/result_aggregator.py (multi-LLM aggregation)
- utils/query_modules/module_base.py (abstract module)
- utils/query_modules/instrument_detector.py (instrument detection)
- utils/query_modules/temporal_detector.py (temporal patterns)
- utils/query_modules/instrument_family_detector.py (family classification)

### Instrument Family Detection (NEW)
- utils/instrument_extractor.py (InstrumentExtractor, InstrumentCatalog)
- utils/instrument_family_patterns.py (InstrumentFamilyDetector, regex patterns)
- logic/instrument_family_assigner.py (InstrumentFamilyAssigner orchestration)

### Utilities
- utils/helpers.py (general utilities)
- utils/cde_impexport.py (I/O)
- utils/output_writer.py (formatting)
- utils/phrase_extraction.py (phrase algorithms)
- utils/phrase_miner_vocab.py (vocabulary for k-mer mining)

## Documentation Files
- README.md - User-facing project overview
- CLAUDE.md - AI assistant context
- docs/help/all-commands.md - CLI command reference
- .claude/context/*.md - Detailed context for checkpoints

## Configuration Files
- .gitignore - Git exclusions (includes .claude/sessions/, .claude/checkpoints/)
- .vscode/ - VSCode settings

## Special Notes

### Legacy Code
The `utils/kmer_*.py` files represent experimental approaches to phrase detection. They are retained for reference but not actively used. The current phrase detection implementations are:
- logic/phrase_extractor.py (original phrase detection)
- logic/phrase_miner.py (iterative k-mer mining - ALL PHASES COMPLETE)
- logic/phrase_anchor_extend.py (anchor-based phrase extension)
- utils/phrase_extraction.py (tokenization and lemmatization utilities)
- utils/verbatim_tracker.py (verbatim text recovery)
- utils/verbatim_coalesce.py (case-insensitive verbatim grouping)
- utils/verbatim_template.py (template extraction from variants)
- utils/verbatim_diff.py (diff annotation for comparison)
- utils/subsumption_filter.py (redundant phrase removal)
- utils/aho_corasick_token.py (efficient pattern matching)
- utils/debruijn_graph.py (phrase extension via graph)
- utils/unicode.py (Unicode normalization, 156 substitutions)

### Checkpoint System
The `.claude/` directory contains a structured checkpoint system for maintaining context across sessions. See `.claude/CHECKPOINT_SYSTEM.md` for details.

### Performance Logs
- load_times4.log - Recent profiling data for launch performance optimization
