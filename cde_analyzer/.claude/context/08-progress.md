# Progress and Current State

## Current Branch: Repeats

**Focus**: Repeated phrase detection and analysis

**Tracking**: origin/Repeats

## Recent Work (Last 30 Days)

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

### Active Branch: feature/phrase-miner-kmer-detection (CURRENT)
- **Purpose**: Advanced k-mer phrase mining implementation
- **Status**: ALL PHASES COMPLETE - ready for merge to main
- **Created**: 2026-01-13
- **Latest Work**: 2026-01-21 (All phases + Unicode normalization + verbatim templates)
- **Contains**: Full phrase_miner action with:
  - Iterative descending k-mer detection (k=25 → k=3)
  - Aho-Corasick multi-pattern masking
  - De Bruijn graph extension
  - Subsumption filtering
  - Anchor-based phrase extension
  - Verbatim text recovery

### Active Branch: Repeats
- **Purpose**: Repeated phrase detection work
- **Status**: Active development
- **Divergence**: Ahead of main by several commits
- **Contains**: Latest lazy loading fixes and phrase analysis work

### Main Branch: main
- **Status**: Stable
- **Last Sync**: Commit 2ca729c "Minor fix of phrase extractor invocation"
- **Purpose**: Stable release baseline
- **Tracking**: origin/main

### Branch Relationship
```
main (2ca729c) ← older, stable
  ↓
  ├── Repeats (4e601c7) ← previous active work
  └── feature/phrase-miner-kmer-detection (d543ff2) ← current development
```

**Recommendation**:
- Test feature/phrase-miner-kmer-detection, then merge to main
- Evaluate merging Repeats → main once stabilized

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
- phrase_miner (NEW)

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
5. ☐ Merge Repeats → main (after validation)
6. ☐ Expand test coverage (core modules)
7. ☐ Standardize CLI argument names
8. ☐ Document legacy kmer_*.py files

### Long Term (Lower Priority)
9. ☐ Package for PyPI distribution
10. ☐ Add CI/CD pipeline
11. ☐ Comprehensive user guide
12. ☐ Type checking with mypy

## Metrics

### Codebase Size
- **Python Files**: ~75 files (including legacy)
- **Lines of Code**: Unknown (not measured)
- **Actions**: 9 implemented
- **Data Models**: 3 top-level (CDEItem, CDEForm, 50+ classes)

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
