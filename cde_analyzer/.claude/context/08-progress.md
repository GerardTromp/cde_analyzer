# Progress and Current State

## Current Branch: phrase-curator

**Focus**: LLM-based phrase classification for semantic curation

**Tracking**: origin/phrase-curator

## Recent Work (Last 30 Days)

### Session 2026-01-27: Pattern Variant Enhancements & Coalesce

**Focus**: Number word variants, spaced punctuation, tinyId format fixes, coalesce feature

**Key Accomplishments**:
- Added number word variant generation for temporal phrases
  - Bidirectional mapping: "7" ↔ "seven", "30" ↔ "thirty", etc.
  - Handles common temporal numbers: 1-10, 12, 14, 24, 30, 60, 90
- Added spaced punctuation variants: " - ", ": ", ", "
- Fixed critical tinyId format mismatch bug across pipeline
  - Root cause: strip_discover wrote space-separated, phrase_grouper expected pipe-separated
  - Fix: All parsers now use `re.split(r'[\s|]+', ...)` for flexible format support
  - Fixed in: phrase_grouper, phrase_family_analyzer, strip_discover, strip_phrases, flexible_pattern_matcher
- Added `--coalesce-variants` mode for tinyId-aware pattern subsumption
  - Removes shorter patterns when covered by longer ones with same tinyIds
  - Outputs subsumption report showing which patterns were removed

**Files Modified**:
- `utils/pattern_variant_generator.py` - Number word and spaced punctuation variants
- `utils/flexible_pattern_matcher.py` - Added `coalesce_variants_tsv()` function
- `actions/strip_discover/cli.py` - Added `--coalesce-variants`, `--coalesce-report`
- `actions/strip_discover/run.py` - Added coalesce mode handler
- `actions/phrase_grouper/run.py` - Fixed tinyIds parsing
- `logic/phrase_family_analyzer.py` - Fixed tinyIds counting
- Multiple files - Consistent tinyId parsing with flexible format support

**Planned Work**: Split strip_discover into focused commands
- `strip_discover` - Core discovery only
- `strip_analyze` - Analysis modes (false-negatives, conflicts)
- `pattern_util` - TSV utilities (merge, coalesce)

**Status**: Features implemented, testing pending

---

### Session 2026-01-26c: Architecture Split & Phrase Grouper

**Focus**: Split phrase_miner into dedicated instrument_miner action, added phrase_grouper for bottom-up family discovery

**Key Accomplishments**:
- Split `phrase_miner` into separate `instrument_miner` action
  - Created `actions/instrument_miner/` (cli.py, run.py, __init__.py)
  - Removed instrument-specific arguments from `phrase_miner`
  - Cleaner separation of concerns: instruments vs general phrases
- Added `phrase_grouper` action for bottom-up k-mer analysis
  - Created `actions/phrase_grouper/` (cli.py, run.py, __init__.py)
  - Created `logic/phrase_grouper.py` with three tree strategies:
    - Prefix tree (trie): Groups by shared beginnings
    - Suffix tree (reversed trie): Groups by shared endings
    - Infix index (inverted index): Groups by shared internal patterns
  - Stopword filtering to exclude low-content patterns
  - Outputs: `families.tsv`, `phrase_assignments.tsv`, `family_members.tsv`
- Bumped version to 0.4.0
- Updated workflow documentation and SVG diagram

**CLI Changes**:
- New action: `instrument_miner` (dedicated instrument extraction)
- New action: `phrase_grouper` (phrase family analysis)
- `phrase_miner` no longer has `--instruments-only` (use `instrument_miner` instead)

**Files Created**:
- `actions/instrument_miner/__init__.py`, `cli.py`, `run.py`
- `actions/phrase_grouper/__init__.py`, `cli.py`, `run.py`
- `logic/phrase_grouper.py`

**Files Modified**:
- `cde_analyzer.py` (registered new actions)
- `cde_analyzer/__version__.py` (0.3.0 → 0.4.0)
- `docs/workflows/instrument-phrase-stripping-workflow.md` (updated for new actions)
- `docs/workflows/instrument-phrase-stripping-workflow.svg` (updated diagram)

**Status**: MILESTONE - Action architecture improved with dedicated commands

---

### Session 2026-01-26b: Strip Discover Complete & False-Negative Reduction

**Focus**: Completed strip_discover action, achieved 91% false-negative reduction

**Key Accomplishments**:
- Reduced false negatives from ~500 to 46 unique patterns (123 occurrences)
- All remaining patterns are legitimate contextual phrases (not instruments)
- Fixed RFQ-U patterns (changed from abbreviated to full form)
- Added patterns: Neuro-QOL subscales, PROMIS Anxiety, NIH Toolbox
- Refactored `--analyze-false-negatives` from string arg to boolean flag
- Implemented per-mode argument validation in strip_discover

**CLI Changes**:
- `--analyze-false-negatives` now uses `-i/--input` for input file (consistent with other tools)
- Arguments are optional at argparse level, validated per-mode in run.py

**False-Negative Analysis Final Results**:
```
Total unique patterns: 46
Total occurrences: 123
Top patterns: medical history, treatment sessions, project descriptions
```
All remaining are legitimate "as part of" contextual phrases.

**Status**: MILESTONE COMPLETE - Instrument stripping pipeline ready for production

**Checkpoint**: checkpoint-20260126-1540-strip-discover-complete.md

---

### Session 2026-01-26a: Config Architecture & Diagnostic Action

**Focus**: Refactored supplementary patterns to config-based architecture, created diagnostic action for iterative stripping improvement.

**Key Changes**:
- Created `config/supplementary_patterns.yaml` - 27 patterns for non-Title-Case instruments
- Created `utils/config_loader.py` - Generic YAML config loader with caching
- Created `actions/diagnose_strip/` - New action for stripping diagnostics
- Refactored `utils/instrument_extractor.py` to load patterns from config

**Critical Learning**: Two separate workflows exist:
1. `phrase_miner --instruments-only --extract-supplementary` → Extract instrument catalog
2. `strip_discover` → `strip_phrases` → Strip patterns from text

These workflows use **different pattern sources**. For comprehensive stripping:
1. Run phrase_miner with all extraction passes
2. Use instruments_verbatim.tsv as pattern-list for strip_discover
3. Run strip_phrases
4. Run diagnose_strip to identify remaining patterns
5. Add patterns to config, iterate

**Status**: Config architecture complete, diagnostic action working

### Commits

**2026-01-07: Launcher fixes (commits 4e601c7, 57b9437)**
- Fixed launcher issues post lazy-load refactoring
- Updated multiple action CLI modules
- Affected files:
  - cde_analyzer/actions/extract_embed/cli.py & run.py
  - cde_analyzer/actions/lemma_fasta/cli.py
  - cde_analyzer/actions/strip_phrases/cli.py
  - cde_analyzer/actions/subset/cli.py & run.py
  - cde_analyzer/actions/count/cli.py
  - cde_analyzer/actions/fix_underscores/cli.py & run.py
  - cde_analyzer/actions/strip_html/cli.py
  - cde_analyzer/actions/phrase/cli.py
  - cde_analyzer/actions/phrase_builder/cli.py

**2026-01-05: Clean repo (commit 83f1df2)**
- Removed temporary file (cde_analyzer/1)
- Cleaned up utils/constants.py

**Status**: Recent stabilization work completing major refactoring

## Recent Major Work (Last 90 Days)

### Major Refactoring: Lazy Loading Architecture (Dec 2024)

**Commit**: 4400bf7 "Refactor launcher to be fully lazy load"

**Problem**: CLI startup was slow due to bloat of imports

**Solution**: Redesigned architecture to be lazy load compatible, similar to git/pip

**Impact**:
- Dramatically improved startup time
- Action modules only loaded when invoked
- Required updates to all action CLI modules
- Some follow-up fixes needed (commits 57b9437, 4e601c7)

**Files Changed**: Multiple action files, main dispatcher

### Feature Development: Repeated Phrase Analysis

**Branch**: Repeats (current)

**Recent Activity**:
- Phrase extraction refinements
- Lemma processing improvements
- FASTA format export

**Related Actions**:
- phrase
- phrase_builder
- lemma_fasta
- strip_phrases

## Branches

### Active Branch: phrase-curator (CURRENT)
- **Purpose**: LLM-based phrase classification for semantic curation
- **Status**: ALL PHASES COMPLETE (5 phases + documentation)
- **Created**: 2026-01-24
- **Latest Work**: 2026-01-24 (Full implementation)
- **Contains**: Full llm_classify action with:
  - Async LLM provider implementations (Claude, OpenAI, Gemini)
  - Modular query framework (instrument detection, temporal detection)
  - Four aggregation methods (unanimous, majority, weighted, confidence-weighted)
  - Confidence quintile system (highly_likely → highly_unlikely)
  - API key resolution: config file → env vars → CLI
  - Comprehensive MkDocs documentation

### Previous Branch: feature/phrase-miner-kmer-detection
- **Purpose**: Advanced k-mer phrase mining implementation
- **Status**: ALL PHASES COMPLETE - merged or ready to merge
- **Contains**: Full phrase_miner action

### Main Branch: main
- **Status**: Stable, recently updated
- **Last Sync**: Commit 328b48e "Revamp CLI documentation with complete command reference"
- **Purpose**: Stable release baseline
- **Tracking**: origin/main

### Branch Relationship
```
main (328b48e) ← stable baseline
  ↓
  └── phrase-curator (10b7f13) ← current development (llm_classify)
```

**Recommendation**:
- Review phrase-curator branch for llm_classify feature
- Test with API keys before merging to main

## Development Phases (Historical)

### Phase 1: Initial Implementation
- Pydantic models for CDE schema
- Basic CLI structure with actions
- Recursive descent engine
- HTML stripping
- Field counting

### Phase 2: Phrase Analysis Focus
- Multiple experimental approaches (kmer_*.py modules)
- Lemmatization support
- Phrase extraction algorithms
- FASTA export for bioinformatics tools
- Various iterations (kmer_build_longest_phrases v1-v4)

### Phase 3: Refactoring and Optimization (Recent)
- Lazy loading architecture (commit 4400bf7)
- Performance improvements
- Launcher stabilization
- Code cleanup

### Phase 4: Current - Stabilization
- Fixing issues from lazy load refactoring
- Code cleanup (removed temporary files)
- Documentation improvements

## Active Work Areas

### 1. Phrase Detection
**Status**: Active development on Repeats branch

**Components**:
- logic/phrase_extractor.py
- logic/phrase_builder.py
- utils/phrase_extraction.py
- utils/phrase_pruning.py

**Recent Changes**:
- Lemma processing improvements
- FASTA format support
- Phrase stripping functionality

### 2. Extract/Embed Functionality
**Status**: Recently updated (commits 4e601c7, 57b9437)

**Purpose**: Prepare data for transformer models

**Components**:
- actions/extract_embed/
- logic/extract_embed.py
- utils/extract_embed.py

### 3. Subset Extraction
**Status**: Recently updated

**Purpose**: Extract data subsets based on criteria

**Components**:
- actions/subset/

## Incomplete or Planned Work

### 1. Testing Infrastructure
**Status**: Minimal

**Current**: Only tests/test_helpers.py

**Needed**:
- Tests for core/recursor.py
- Tests for logic modules
- Integration tests for actions
- CI/CD pipeline

**Priority**: High (affects refactoring confidence)

### 2. Argument Standardization
**Status**: Identified but not started

**Source**: README.md note

**Issue**: Inconsistent argument names across actions

**Scope**:
- Audit all action CLI modules
- Define standard argument names
- Refactor for consistency
- Update documentation

**Priority**: Medium (affects UX)

### 3. Legacy Code Cleanup
**Status**: Deferred

**Issue**: 12+ legacy kmer_*.py files in utils/

**Options**:
- Remove and archive in git history
- Move to legacy/ subdirectory
- Document and keep for reference

**Priority**: Low (not blocking functionality)

### 4. Dependency Documentation
**Status**: Missing

**Needed**:
- requirements.txt or pyproject.toml
- Installation instructions
- Version specifications
- NLP library clarification

**Priority**: High (affects usability)

### 5. Enhanced Documentation
**Status**: Basic README exists

**Needed**:
- User guide with examples
- Developer guide
- API documentation (if used as library)
- Contribution guidelines

**Priority**: Medium

## Recently Completed

### ✓ LLM Classify Implementation (ALL PHASES COMPLETE)
- Completed: 2026-01-24
- Branch: phrase-curator
- Status: All 5 phases + documentation complete
- Commit: 10b7f13

**Implemented Features**:
- ✅ Async LLM provider implementations (Claude, OpenAI, Gemini)
- ✅ Modular query framework (instrument detection, temporal detection)
- ✅ Four aggregation methods (unanimous, majority, weighted, confidence-weighted)
- ✅ Confidence quintile system (highly_likely → highly_unlikely)
- ✅ API key resolution: config file → env vars → CLI
- ✅ Rate limiting with token bucket algorithm
- ✅ Comprehensive MkDocs documentation (4 files)

### ✓ Phrase Miner Implementation (ALL PHASES COMPLETE)
- Completed: 2026-01-20
- Branch: feature/phrase-miner-kmer-detection
- Status: All phases implemented and tested

**Implemented Features**:
- ✅ Phase 1: Foundation (data structures, vocabulary)
- ✅ Phase 2: Action setup (CLI, orchestration)
- ✅ Phase 3: Core k-mer mining (iterative descent k=25→k=3)
- ✅ Phase 3.5: Verbatim text recovery (position-based + lemma→variants)
- ✅ Phase 4: Aho-Corasick multi-pattern matching for masking
- ✅ Phase 5: De Bruijn graph extension for phrase merging
- ✅ Phase 6: Subsumption filtering to remove redundant phrases
- ✅ Phase 7: Anchor-based phrase extension using context bigrams

**Output Files**:
1. `phrases.tsv` - All detected phrases with metadata
2. `occurrences.tsv` - Every occurrence with verbatim text
3. `verbatim_phrases.tsv` - Lemma→verbatim mappings (one-to-many)
4. `verbatim_variants.tsv` - Token-level variants
5. `verbatim_templates.tsv` - Regex templates from multi-form phrases
6. `extended.tsv` - Anchor-extended phrases (when enabled)

**CLI Flags**:
- `--enable-debruijn` - Enable De Bruijn graph extension
- `--enable-subsumption` - Enable subsumption filtering
- `--enable-anchor` - Enable anchor-based extension
- `--no-aho-corasick` - Use naive matching (for debugging)

**Files Created/Modified**:
- utils/phrase_miner_vocab.py (Vocabulary class)
- utils/verbatim_tracker.py (VerbatimTracker, PrefixTrie)
- utils/subsumption_filter.py (subsumption filtering)
- utils/aho_corasick_token.py (token-based AC automaton)
- utils/debruijn_graph.py (De Bruijn graph extension)
- utils/phrase_extraction.py (added tokenize_text_with_positions)
- logic/phrase_miner.py (core mining algorithm)
- logic/phrase_anchor_extend.py (anchor extension)
- actions/phrase_miner/ (CLI and orchestration)

### ✓ Lazy Loading Refactoring
- Completed: December 2024
- Follow-up fixes: January 2026
- Status: Complete and stable

### ✓ Repository Cleanup
- Removed temporary file (commit 83f1df2)
- Cleaned constants (commit 83f1df2)
- Status: Ongoing maintenance

### ✓ Multiple Action Implementations
- fix_underscores
- strip_html
- phrase
- count
- extract_embed
- strip_phrases
- lemma_fasta
- phrase_builder
- subset
- phrase_miner
- llm_classify (NEW)

All functional and updated for lazy loading

## Known Issues

### Post-Refactoring Stability
**Status**: Addressed by recent commits (57b9437, 4e601c7)

**Issue**: Launcher fixes needed after lazy load refactoring

**Resolution**: Two rounds of fixes completed

**Current State**: Stable

### Legacy Code Maintenance
**Status**: Open

**Issue**: Legacy kmer_*.py files may break with dependency updates

**Mitigation**: Documented as legacy, not actively maintained

**Impact**: Low (not used in production)

## Git Status Summary

**Current Branch**: Repeats

**Working Directory**: Clean (as of last git status)

**Staged Changes**: None

**Untracked Files**: Potentially .claude/ session files (git-ignored)

**Recent Commit**: 4e601c7 "Launcer fix (2)" - 6 days ago

## Development Velocity

### Commit Frequency (Last 90 Days)
- High activity in December 2024 (lazy loading refactoring)
- Continued activity in January 2026 (launcher fixes)
- Focus on stability and refinement

### Active Development Areas
1. Phrase analysis (ongoing)
2. Architecture improvements (recent)
3. Bug fixes (ongoing)

### Stable Components
- Core data models (CDE_Schema)
- Recursive engine (core/recursor.py)
- Basic action infrastructure

## Next Steps (Recommendations)

### Immediate (High Priority)
1. ☐ Create requirements.txt or pyproject.toml
2. ☐ Document NLP library dependency
3. ☐ Add installation instructions to README
4. ☐ Test all actions on fresh Python environment

### Short Term (Medium Priority)
5. ☐ Test `--coalesce-variants` feature with real data
6. ☐ Split `strip_discover` into focused commands:
   - `strip_discover` - Core discovery only
   - `strip_analyze` - Analysis modes (false-negatives, conflicts, supplementary import)
   - `pattern_util` - TSV utilities (merge, coalesce)
7. ☐ Merge Repeats → main (after validation)
8. ☐ Expand test coverage (core modules)
9. ☐ Standardize CLI argument names
10. ☐ Document legacy kmer_*.py files

### Long Term (Lower Priority)
11. ☐ Package for PyPI distribution
12. ☐ Add CI/CD pipeline
13. ☐ Comprehensive user guide
14. ☐ Type checking with mypy

## Metrics

### Codebase Size
- **Python Files**: ~95 files (including legacy and new llm modules)
- **Lines of Code**: ~5,600+ new lines in llm_classify feature
- **Actions**: 11 implemented (added llm_classify)
- **Data Models**: 4 top-level (CDEItem, CDEForm, EmbedText, LLM_Classification)

### Recent Activity
- **Commits (30 days)**: 3
- **Files Changed (30 days)**: ~15
- **Contributors**: Gerard Tromp (primary)

### Test Coverage
- **Coverage**: Unknown (minimal tests)
- **Test Files**: 1 (tests/test_helpers.py)

### Documentation
- **README.md**: Yes (basic)
- **CLAUDE.md**: Yes (AI assistant context)
- **API Docs**: No
- **User Guide**: Minimal (see docs/help/)

## Checkpoint System Status

**Recently Added**: 2026-01-13

**Components**:
- .claude/checkpoints/ - Created
- .claude/context/ - Created, populated
- .claude/sessions/ - Created
- .claude/memory-bank/ - Created
- CHECKPOINT_PROMPTS.md - Added
- CHECKPOINT_SYSTEM.md - Added

**Context Files Created**:
1. ✓ 01-architecture.md - System architecture
2. ✓ 02-codebase-map.md - Code organization
3. ✓ 03-data-models.md - Data structures
4. ✓ 04-patterns.md - Design patterns
5. ✓ 05-decisions.md - Architecture decisions
6. ✓ 06-dependencies.md - Dependencies
7. ✓ 07-gotchas.md - Known issues
8. ✓ 08-progress.md - THIS FILE

**Status**: Initial checkpoint context complete

**Next**: Update CLAUDE.md to reference checkpoint system

## Session Notes

### Session 2026-01-24: LLM Classify Implementation Complete

**Branch**: phrase-curator

**Commit**: 10b7f13 "Implement llm_classify command for multi-LLM phrase classification"

**Goals**:
- Implement multi-LLM phrase classification action
- Support Claude, OpenAI, and Gemini providers
- Create modular query framework for extensible classification
- Add comprehensive MkDocs documentation

**Accomplishments**:
- ✅ Phase 1: Core Infrastructure & Data Models
  - Created `CDE_Schema/LLM_Classification.py` with Pydantic models
  - Implemented ConfidenceQuintile enum and dataclasses
- ✅ Phase 2: Async LLM Provider Implementations
  - Created `utils/llm/config.py` for API key resolution
  - Created `utils/llm/provider_base.py` abstract interface
  - Implemented Claude, OpenAI, Gemini providers
  - Added `utils/llm/rate_limiter.py` with token bucket algorithm
- ✅ Phase 3: Query Module Framework
  - Created `utils/query_modules/module_base.py` abstract interface
  - Created module registry with lazy loading
  - Implemented `utils/llm/result_aggregator.py` (4 aggregation methods)
- ✅ Phase 4: Orchestration Layer
  - Created `logic/llm_classifier.py` core orchestration
  - Created `actions/llm_classify/` (cli.py, run.py)
  - Registered in ACTION_REGISTRY
- ✅ Phase 5: Query Modules
  - Implemented instrument_detector.py (3 categories)
  - Implemented temporal_detector.py (6 categories)
- ✅ Documentation
  - Created `docs/llm/` directory with 4 comprehensive files
  - Updated `mkdocs.yml` with new navigation section
  - Updated `docs/commands/index.md` and `docs/help/all-commands.md`

**Files Created** (26 files, 5,615 lines):
- CDE_Schema/LLM_Classification.py (186 lines)
- actions/llm_classify/__init__.py (5 lines)
- actions/llm_classify/cli.py (128 lines)
- actions/llm_classify/run.py (196 lines)
- logic/llm_classifier.py (506 lines)
- utils/llm/__init__.py (200 lines)
- utils/llm/config.py (325 lines)
- utils/llm/provider_base.py (293 lines)
- utils/llm/provider_claude.py (262 lines)
- utils/llm/provider_openai.py (267 lines)
- utils/llm/provider_google.py (289 lines)
- utils/llm/rate_limiter.py (356 lines)
- utils/llm/result_aggregator.py (401 lines)
- utils/query_modules/__init__.py (174 lines)
- utils/query_modules/module_base.py (310 lines)
- utils/query_modules/instrument_detector.py (154 lines)
- utils/query_modules/temporal_detector.py (196 lines)
- docs/llm/index.md (152 lines)
- docs/llm/llm_classify.md (379 lines)
- docs/llm/configuration.md (324 lines)
- docs/llm/query_modules.md (319 lines)
- docs/help/llm_classify.md (103 lines)

**Files Modified** (4 files):
- cde_analyzer.py (added to ACTION_REGISTRY)
- docs/commands/index.md (added LLM section)
- docs/help/all-commands.md (added llm_classify command)
- mkdocs.yml (added LLM Classification nav section)

**Key Design Decisions**:
1. API key priority: config file → env vars → CLI (security)
2. Async pattern with asyncio for parallel LLM queries
3. Token bucket rate limiting per provider
4. Quintile confidence system (5 levels)
5. Four aggregation methods for multi-LLM consensus
6. Lazy loading for providers and modules

**Checkpoint**: checkpoint-2026-01-24-llm-classify-complete.md

**Status**: Complete, committed and pushed to remote

**Next Steps**:
- Test with actual API keys
- Add unit tests for providers and modules
- Consider merging to main after validation

---

### Session 2026-01-24b: Enhanced Instrument Detection with Family Grouping

**Branch**: phrase-curator

**Goals**:
- Add two-tier identification system (family_id + instrument_id)
- Enable instrument family grouping for substitution testing
- Pattern-based family detection with LLM adjudication fallback
- Extended output formats for family analysis

**Accomplishments**:
- ✅ Phase 1: Data Model Extensions
  - Added `InstrumentFamily` enum to `CDE_Schema/LLM_Classification.py` (15 families)
  - Added `InstrumentIdentification` dataclass for two-tier ID system
- ✅ Phase 2: Family Detection Patterns
  - Created `utils/instrument_family_patterns.py` with `InstrumentFamilyDetector` class
  - 13 known families with regex patterns (neuro-qol, promis, mds-updrs, sf-health, beck, phq, gad, mmse, moca, nihss, pdqualif, dsq, rome)
  - False positive exclusion patterns
  - Confidence scoring based on pattern specificity
- ✅ Phase 3: Extended InstrumentMatch/Catalog
  - Added family fields to `InstrumentMatch` dataclass
  - Added `assign_families()` and `get_families_summary()` methods to `InstrumentCatalog`
- ✅ Phase 4: Family Assigner Orchestration
  - Created `logic/instrument_family_assigner.py` with `InstrumentFamilyAssigner` class
  - Handles family assignment workflow with confidence thresholding
- ✅ Phase 5: CLI Integration
  - Added `--detect-families`, `--family-confidence-threshold`, `--family-summary` to phrase_miner
  - Added `--adjudicate-instruments`, `--adjudicate-threshold` to llm_classify
- ✅ Phase 6: LLM Adjudication Module
  - Created `utils/query_modules/instrument_family_detector.py` (15 categories)
  - Registered in module registry
- ✅ Phase 7: Documentation
  - Updated `docs/commands/phrase_miner.md` with family detection
  - Updated `docs/llm/llm_classify.md` with adjudication mode
  - Updated `docs/llm/query_modules.md` with instrument_family module
  - Updated `docs/help/all-commands.md` with new CLI options

**Files Created** (3):
- `logic/instrument_family_assigner.py` (InstrumentFamilyAssigner orchestration)
- `utils/instrument_family_patterns.py` (InstrumentFamilyDetector, regex patterns)
- `utils/query_modules/instrument_family_detector.py` (LLM adjudication module)

**Files Modified** (7):
- `CDE_Schema/LLM_Classification.py` (+67 lines: InstrumentFamily enum, InstrumentIdentification)
- `utils/instrument_extractor.py` (+89 lines: family fields, assign_families method)
- `actions/phrase_miner/cli.py` (+19 lines: family detection flags)
- `actions/phrase_miner/run.py` (+69 lines: family output generation)
- `actions/llm_classify/cli.py` (+16 lines: adjudication mode)
- `utils/query_modules/__init__.py` (+2 lines: instrument_family registration)
- Various documentation files

**Key Design Decisions**:
1. Two-tier ID enables family-level and individual analysis
2. Pattern-based detection is fast and free (no API costs)
3. Confidence threshold (0.7) flags uncertain cases for review
4. LLM adjudication only for instruments below threshold

**Status**: Implementation complete, documentation updated

**Next Steps**:
- Run integration tests on real CDE data
- Test LLM adjudication with API keys
- Consider merging to main after validation

---

### Session 2026-01-21b: Instrument Pattern Extraction

**Branch**: main

**Goals**:
- Implement instrument pattern extraction for "as part of <Instrument>" patterns
- Create two-phase workflow for instrument curation
- Add pre-masking of curated instruments before k-mer mining

**Accomplishments**:
- ✅ Created `utils/instrument_extractor.py` with InstrumentExtractor class
  - Regex-based detection of "as part of [version X.X of] [the] <Instrument Name> [(<ACRONYM>)]"
  - APA-style Title Case validation (>60% correct casing)
  - Support for ALL CAPS abbreviations (TBI, PTSD) and Roman numerals (III, IV)
  - Multi-hyphen acronym support (K-SADS-PL, WHOQOL-BREF)
- ✅ Added CLI arguments to `actions/phrase_miner/cli.py`:
  - `--extract-instruments` - Enable instrument extraction
  - `--instruments-only` - Phase 1 mode (extract only, skip phrase mining)
  - `--instrument-list` - Phase 2 pre-masking from curated TSV
  - `--min-instrument-words` - Minimum words in instrument name (default: 3)
- ✅ Implemented `load_instrument_list()` in `actions/phrase_miner/run.py`
  - Flexible format: `filename` or `filename,column_name`
  - Default column: `full_match`
- ✅ Added `extract_instruments_only()` function to `logic/phrase_miner.py`
- ✅ Integrated instrument pre-masking in `extract_token_sequences()`
  - Case-insensitive pattern matching
  - Character-to-token span mapping
  - Mask key: `__CURATED_INSTRUMENT__:<pattern>`
- ✅ Added `write_instruments_tsv()` and `write_instruments_verbatim_tsv()` output functions
- ✅ Created comprehensive unit tests in `tests/test_instrument_extractor.py`
- ✅ Updated `docs/commands/phrase_miner.md` with new arguments and examples

**Files Created** (2):
- utils/instrument_extractor.py (InstrumentExtractor, InstrumentMatch, InstrumentCatalog)
- tests/test_instrument_extractor.py (31 test cases)

**Files Modified** (4):
- actions/phrase_miner/cli.py (added 4 CLI arguments)
- actions/phrase_miner/run.py (added load_instrument_list, output functions)
- logic/phrase_miner.py (added MinerConfig fields, extract_instruments_only, pre-masking)
- docs/commands/phrase_miner.md (documented new features)

**Two-Phase Workflow**:
1. **Phase 1**: `--instruments-only` extracts instruments for curation
2. **Curation**: User reviews `instruments_verbatim.tsv`, removes false positives
3. **Phase 2**: `--instrument-list <file>` pre-masks curated patterns

**Example Usage**:
```bash
# Phase 1: Extract instruments
cde_analyzer phrase_miner -i data.json -o output/ --instruments-only --min-tinyids 1

# Phase 2: Full mining with curated list
cde_analyzer phrase_miner -i data.json -o output/ --instrument-list output/instruments_verbatim.tsv
```

**Status**: Complete and tested

---

### Session 2026-01-21: Unicode Normalization and Verbatim Templates

**Branch**: feature/phrase-miner-kmer-detection

**Commit**: c1f7af9 "Add Unicode normalization pipeline and verbatim template extraction"

**Goals**:
- Add Unicode normalization earlier in pipeline (strip_html)
- Expand Unicode substitution table
- Implement verbatim template extraction

**Accomplishments**:
- ✅ Expanded `utils/unicode.py` UNICODE_SUBSTITUTIONS from 39 to 156 entries
  - Control characters (misencoded quotes/dashes)
  - Full Latin-1 Supplement (accented letters, symbols)
  - Greek alphabet (scientific/medical text)
  - General Punctuation (spaces, quotes, dashes)
  - Superscripts/Subscripts, Number Forms, Math Operators
  - Miscellaneous symbols (bullets, checkboxes)
- ✅ Added Unicode normalization to all HTML text extraction paths
  - `strip_html()` already called `normalize_unicode()` via `normalize_string()`
  - `process_html_blob()` now uses `normalize_string()` for all text
  - Table cell extraction uses new `_normalize_cell()` helper
- ✅ Added `normalize_unicode()` call to `sanitize()` in `utils/extract_embed.py`
- ✅ Created `utils/verbatim_template.py` for template extraction
- ✅ Created `utils/verbatim_coalesce.py` for case-insensitive grouping
- ✅ Created `utils/verbatim_diff.py` for diff annotation
- ✅ Added `write_verbatim_templates_tsv()` to phrase_miner run.py
- ✅ Updated documentation (phrase_miner.md, context files)

**Files Created** (3):
- utils/verbatim_template.py (extract_template, format_template_row)
- utils/verbatim_coalesce.py (coalesce_verbatim_groups)
- utils/verbatim_diff.py (annotate_diff)

**Files Modified** (4):
- utils/unicode.py (expanded substitution table 39→156 entries)
- utils/html.py (added _normalize_cell helper, normalize all text paths)
- utils/extract_embed.py (added normalize_unicode call to sanitize)
- actions/phrase_miner/run.py (added write_verbatim_templates_tsv)

**Impact**: Unicode variants (smart quotes, em-dashes, accented chars) now
collapsed before phrase detection, reducing false phrase variants.

**Status**: Complete, pushed to remote

---

### Session 2026-01-20: phrase_miner All Phases Complete

**Branch**: feature/phrase-miner-kmer-detection

**Goals**:
- Complete remaining phases (6, 7) of phrase_miner
- Implement verbatim phrase extraction
- Update all documentation

**Accomplishments**:
- ✅ Implemented Phase 6: Subsumption filtering (`utils/subsumption_filter.py`)
- ✅ Implemented Phase 7: Anchor-based extension (`logic/phrase_anchor_extend.py`)
- ✅ Added verbatim phrase output (`write_verbatim_phrases_tsv()`)
- ✅ Added CLI flags: `--enable-subsumption`, `--enable-anchor`
- ✅ Updated plan document (marked all phases complete)
- ✅ Updated context documentation

**Files Created**:
- utils/subsumption_filter.py (subsumption filtering with tinyId overlap check)

**Files Modified**:
- logic/phrase_anchor_extend.py (full implementation replacing stub)
- actions/phrase_miner/run.py (added verbatim output, subsumption integration)
- actions/phrase_miner/cli.py (added new CLI flags)

**Performance**: ~40s for 22,000 CDEs with k_min=7

**Status**: All phases complete, ready for production use

---

### Session 2026-01-15: Documentation Update for phrase_miner

**Branch**: feature/phrase-miner-kmer-detection

**Commit**: 9cfb01a "Update overall architecture documentation"

**Goals**:
- Update .claude context documentation to reflect phrase_miner implementation
- Ensure all architectural documentation accurately shows new files and patterns

**Accomplishments**:
- ✅ Updated .claude/context/02-codebase-map.md (6 edits)
- ✅ Updated .claude/context/01-architecture.md (4 edits)
- ✅ Updated .claude/context/04-patterns.md (2 edits)
- ✅ Distinguished original phrase action from new phrase_miner action
- ✅ Documented k-mer mining workflow (5-step pipeline)
- ✅ Committed documentation changes

**Files Modified** (3):
- .claude/context/02-codebase-map.md (directory structure, key files)
- .claude/context/01-architecture.md (current actions, current state)
- .claude/context/04-patterns.md (visitor pattern usage, phrase pipeline)

**Checkpoint**: incremental-20260115-1430.md

**Status**: Documentation update complete

**Next Steps**:
- Pending: Test phrase_miner on small dataset (10-100 CDEs)
- Pending: Validate output quality and performance

---

### Session 2026-01-13b: Phrase Miner Implementation (Phase 1-3)

**Branch**: feature/phrase-miner-kmer-detection (NEW)

**Commit**: d543ff2 "Implement phrase_miner action (Phase 1-3: Core k-mer mining)"

**Goals**:
- Implement core k-mer mining algorithm based on PhraseExtensionConcept_20260113.md
- Focus on Phase 1-3 (foundation, action setup, core mining)
- Defer advanced features to future phases

**Accomplishments**:
- ✅ Created feature branch (feature/phrase-miner-kmer-detection)
- ✅ Implemented Vocabulary class (utils/phrase_miner_vocab.py)
- ✅ Implemented core data structures and mining algorithm (logic/phrase_miner.py)
- ✅ Created action structure (actions/phrase_miner/)
- ✅ Registered phrase_miner in ACTION_REGISTRY
- ✅ Fixed pre-existing broken imports in logic/__init__.py
- ✅ Committed changes with comprehensive commit message

**Files Created** (6):
- utils/phrase_miner_vocab.py
- logic/phrase_miner.py
- logic/phrase_anchor_extend.py (placeholder)
- actions/phrase_miner/__init__.py
- actions/phrase_miner/cli.py
- actions/phrase_miner/run.py

**Files Modified** (2):
- cde_analyzer.py (added phrase_miner to ACTION_REGISTRY)
- logic/__init__.py (fixed broken imports)

**Checkpoint**: checkpoint-20260113-phrase-miner-phase1-3.md

**Status**: Implementation complete, ready for testing

**Next Steps**:
- Test on small dataset (10-100 CDEs)
- Validate output quality and performance
- Merge to main after successful testing
- Future: Implement Phase 4-7 enhancements

---

### Session 2026-01-26: Config Architecture & Diagnostic Action

**Branch**: phrase-curator

**Goals**:
- Move hardcoded supplementary patterns to YAML config
- Create diagnostic action for iterative stripping improvement
- Enable curator-friendly pattern curation workflow

**Accomplishments**:
- ✅ Created `config/supplementary_patterns.yaml` (27 patterns, categorized)
- ✅ Created `utils/config_loader.py` (generic YAML loader with caching)
- ✅ Refactored `utils/instrument_extractor.py` to load from config
- ✅ Created `actions/diagnose_strip/` action (cli.py, run.py)
- ✅ Registered `diagnose_strip` in ACTION_REGISTRY

**Files Created** (4):
- config/supplementary_patterns.yaml (27 patterns in YAML format)
- utils/config_loader.py (load_yaml_config, load_supplementary_patterns)
- actions/diagnose_strip/cli.py (CLI argument definitions)
- actions/diagnose_strip/run.py (diagnostic logic, pattern categorization)

**Files Modified** (2):
- utils/instrument_extractor.py (removed hardcoded constant, added config loading)
- cde_analyzer.py (added diagnose_strip to ACTION_REGISTRY)

**Key Insight**: phrase_miner and strip_discover are **separate workflows**:
- phrase_miner uses config/supplementary_patterns.yaml for extraction
- strip_discover uses --pattern-list input (TSV)
- For comprehensive stripping, use phrase_miner output as strip_discover input

**Test Results** (on cde_all_06_20260105_phrases14/cleaned.json):
- 170 unique remaining patterns
- 936 total occurrences
- Categories: other(499), test(186), questionnaire(122), model(61), scale(44), acronym(22), version(2)

**Checkpoint**: checkpoint-2026-01-26-config-diagnostics.md

**Status**: Implementation complete, ready for iteration

**Recommended Workflow**:
```bash
# 1. Extract instruments with supplementary
cde_analyzer phrase_miner -i cdes.json -o output/ --instruments-only --extract-supplementary

# 2. Discover patterns using instrument list
cde_analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv --pattern-list output/instruments_verbatim.tsv

# 3. Strip patterns
cde_analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json --patterns discovered.tsv

# 4. Diagnose remaining
cde_analyzer diagnose_strip -i cleaned.json -m CDE -o remaining.tsv --suggest-patterns

# 5. Review remaining.yaml, add to config, iterate
```

---

### Session 2026-01-13a: Initial checkpoint system setup

**Goals**:
- Establish checkpoint infrastructure
- Document codebase comprehensively
- Create context preservation system

**Progress**: Context documentation complete

**Next Session**:
- Continue development on Repeats branch
- Use checkpoint system for context preservation
- Consider merge to main when stable
