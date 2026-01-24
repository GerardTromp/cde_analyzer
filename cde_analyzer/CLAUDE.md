# CDE Analyzer

Project aims to parse and analyze Common Data Elements (CDEs) hosted by the National Library of Medicine at the National Institutes of Health (https://cde.nlm.nih.gov/home).

**API**: Well-documented RESTful API at https://cde.nlm.nih.gov/api describing data structure.

**Data Model**: The CDE repository data structure has been implemented as a set of Pydantic models.

## Primary Principles

### Code Organization
- **All functions broken down to effect lazy loading**
  - Action directories contain:
    - `cli.py` - Argument parser (launcher)
    - `run.py` - Called by launcher, orchestrates action
  - `logic/` - Algorithm implementations (business logic)
  - `utils/` - Lightweight functions and utility tools

- **Data Models**: Pydantic classes in `CDE_Schema/` directory
  - `CDE_Item.py` - Individual data elements (CDEItem model)
  - `CDE_Form.py` - Form structures (CDEForm model)
  - `classes.py` - Shared classes (50+ supporting models)

- **Core Engine**: `core/recursor.py` - Recursive descent visitor pattern for nested structures

### Architecture
- **Layered monolithic** with plugin-style action system
- **Lazy loading** - Actions loaded only when invoked (fast startup)
- **Visitor pattern** - Single recursive engine handles all nested traversal
- **Three-layer actions**: CLI → Orchestration → Logic separation

## Current Status

**Active Branch**: phrase-curator (LLM-based phrase classification)

**Main Branch**: main (stable)

**Recent Work** (Last 30 days):
- Enhanced Instrument Detection with family grouping (two-tier ID system)
- LLM classify action implementation (commit 10b7f13, 7344e83)
- Multi-provider support: Claude, OpenAI, Gemini
- Comprehensive MkDocs documentation
- Launcher fixes post lazy-load refactoring (commits 4e601c7, 57b9437)

**Major Refactoring** (Dec 2024, commit 4400bf7):
- Converted to max-lazy loading architecture
- Dramatic startup performance improvement
- Inspired by git/pip command structure

## Actions (CLI Commands)

The `cde_analyzer` wrapper script accepts action arguments:

1. **fix_underscores** - Fix Pydantic-incompatible field names (underscore prefix)
2. **strip_html** - Remove HTML markup from CDE fields
3. **phrase** - Find repeated phrases across CDE records (original approach)
4. **phrase_miner** - Advanced k-mer phrase mining with iterative descent
5. **count** - Count structural elements and field occurrences
6. **extract_embed** - Extract fields for transformer model embedding
7. **strip_phrases** - Remove literal phrases at specified paths
8. **lemma_fasta** - Create FASTA format from lemma sequences
9. **phrase_builder** - Incremental phrase construction
10. **subset** - Extract subsets using literal/regex/tinyID filters
11. **llm_classify** - Multi-LLM phrase classification with confidence aggregation (NEW)

**Usage**: `cde_analyzer <action> [arguments]`

**Help**: `cde_analyzer <action> --help` for action-specific options

### phrase_miner Features (Advanced)
The `phrase_miner` action provides sophisticated phrase detection:
- Iterative descending k-mer mining (k=25 → k=3)
- Aho-Corasick multi-pattern matching for efficient masking
- De Bruijn graph extension (`--enable-debruijn`)
- Subsumption filtering (`--enable-subsumption`)
- Anchor-based phrase extension (`--enable-anchor`)
- Verbatim text recovery for original surface forms
- Instrument extraction with family grouping (`--detect-families`)

**Example**: `cde_analyzer phrase_miner -i cdes.json -o output/ --enable-subsumption`

**Instrument Family Detection**:
```bash
cde_analyzer phrase_miner -i cdes.json -o output/ --instruments-only --detect-families --family-summary
```
- Two-tier identification: `family_id` (e.g., "neuro-qol") + `instrument_id` (e.g., "neuro-qol-ability-participate-sra")
- Pattern-based detection for 13 known families (neuro-qol, promis, mds-updrs, sf-health, beck, phq, etc.)
- Confidence thresholding: instruments with confidence < 0.7 flagged for review
- Output: `instruments.tsv`, `instruments_verbatim.tsv`, `instrument_families.tsv`

### llm_classify Features (NEW)
The `llm_classify` action provides LLM-based phrase classification:
- Multi-provider support: Claude, OpenAI, Gemini (async parallel queries)
- Modular query framework with pluggable classification modules
- Four aggregation methods: unanimous, majority, weighted_majority, confidence_weighted
- Confidence quintile system: highly_likely → likely → indeterminate → unlikely → highly_unlikely
- API key resolution: config file → environment variables → CLI
- Rate limiting with token bucket algorithm

**Available Modules**:
- `instrument` - Detect measurement instruments, devices, assessment tools
- `temporal` - Identify temporal patterns (recency, age ranges, durations)
- `instrument_family` - Classify instruments into known families (Neuro-QOL, PROMIS, etc.)

**Example**: `cde_analyzer llm_classify -i phrase_output/ -m instrument --providers claude openai`

**Instrument Adjudication Mode**:
```bash
cde_analyzer llm_classify --adjudicate-instruments instruments.tsv --adjudicate-threshold 0.7 -m instrument_family --providers claude
```
- Resolves uncertain family assignments from pattern-based detection
- Processes only instruments with `family_confidence < threshold`
- 15 family categories including known families and "other_instrument"

**Documentation**: See [docs/llm/](docs/llm/) for comprehensive guide.

## Key Technical Notes

### Legacy Code
Files in `utils/` with `kmer_*` prefix are **legacy experimental code** for phrase detection:
- Multiple versions of kmer_build_longest_phrases.py (v1-v4)
- Various kmer approaches to finding longest repeated phrases
- Retained for reference and history of attempts
- Not actively used in current implementation
- May document evolution toward effective phrase detection algorithms

Current phrase detection uses:
- `logic/phrase_extractor.py` (original approach via `phrase` action)
- `logic/phrase_miner.py` (advanced k-mer mining via `phrase_miner` action)
- `logic/phrase_anchor_extend.py` (anchor-based extension)
- `logic/llm_classifier.py` (LLM-based classification via `llm_classify` action)
- `logic/instrument_family_assigner.py` (instrument family assignment orchestration)
- `utils/phrase_extraction.py` (shared tokenization utilities)
- `utils/verbatim_tracker.py` (verbatim text recovery)
- `utils/subsumption_filter.py` (redundant phrase removal)
- `utils/aho_corasick_token.py` (efficient pattern matching)
- `utils/instrument_extractor.py` (instrument pattern extraction)
- `utils/instrument_family_patterns.py` (family detection regex patterns)
- `utils/llm/` (LLM provider infrastructure)
- `utils/query_modules/` (classification query modules including instrument_family)

### Data Model Characteristics
- **Self-referential nesting** - Models can contain nested instances of themselves
- **All fields Optional** - Handles sparse API responses
- **Field aliases** - Maps MongoDB/API names to Python-safe names (e.g., `_id` → `id`)
- **Type validation** - Pydantic provides automatic validation

### Recursive Processing
All nested data traversal uses `core/recursor.py`:
```python
recursive_descent(item, path, visitor, context, depth)
```
- Visitor pattern separates traversal from processing
- Path tracking provides context (e.g., "designations.*.designation")
- Handles both dict and list structures uniformly

### Output Formats
All actions support multiple output formats via `--output-format`:
- **JSON** - Preserves nested structure
- **CSV/TSV** - Flat format for spreadsheets (loses nesting)

## Checkpoint System

This project uses a structured checkpoint system for context preservation across sessions.

### Session Finalization Macro: `/finalize`

Use this prompt to complete a development session with full documentation:

---

**PROMPT** (copy and paste):

```
Execute the Session Finalization workflow. Complete each step fully before proceeding to the next. Pause after each step for my review.

## Step 1: Document Changes
- Review git status and recent changes
- Create a summary of work completed this session
- List files created, modified, and deleted
- Note any architectural decisions made
**PAUSE for review after completing Step 1**

## Step 2: Update MkDocs Documentation
If new commands or features were added:
- Update docs/commands/index.md with new command entries
- Update docs/help/all-commands.md with CLI synopsis
- Create new documentation files in docs/ as needed
- Update mkdocs.yml navigation if new pages added
**PAUSE for review after completing Step 2**

## Step 3: Update Claude Context Files
Update relevant files in .claude/context/:
- 01-architecture.md - New components, layers, or patterns
- 02-codebase-map.md - New directories or files
- 03-data-models.md - New Pydantic models or data structures
- 05-decisions.md - Add ADRs for significant decisions
- 06-dependencies.md - New external dependencies
- 08-progress.md - Session notes and status updates
**PAUSE for review after completing Step 3**

## Step 4: Update CLAUDE.md
Update CLAUDE.md with:
- Current Status section (active branch, recent work)
- Actions list if new commands added
- Feature sections for significant new capabilities
- Any new documentation references
**PAUSE for review after completing Step 4**

## Step 5: Create Checkpoint
Create checkpoint file at .claude/checkpoints/checkpoint-YYYY-MM-DD-<description>.md
Include: session summary, files changed, decisions made, next steps
(Note: Checkpoints are gitignored - for local reference only)
**PAUSE for review after completing Step 5**

## Step 6: Commit and Push
- Stage all relevant files (code, docs, context files, CLAUDE.md)
- Create comprehensive commit message with Co-Authored-By
- Push to remote
- Report final status
**DONE**
```

---

**When to use**: At the end of any development session that introduced new features, commands, or significant changes.

**Context management**: Each step may use significant context. If Claude becomes slow or loses track, use `/compact` between steps.

### Quick Commands
- **Create checkpoint**: See [.claude/CHECKPOINT_PROMPTS.md](.claude/CHECKPOINT_PROMPTS.md) → "Incremental Checkpoint: End of Session"
- **Recover context**: See [.claude/CHECKPOINT_PROMPTS.md](.claude/CHECKPOINT_PROMPTS.md) → "Recovery: Full Context Restoration"
- **Update progress**: See [.claude/CHECKPOINT_PROMPTS.md](.claude/CHECKPOINT_PROMPTS.md) → "Update: 08-progress.md"

### Context Files Location
All context documentation in [.claude/context/](.claude/context/):

1. **[01-architecture.md](.claude/context/01-architecture.md)** - System architecture, components, tech stack, data flow
2. **[02-codebase-map.md](.claude/context/02-codebase-map.md)** - Directory structure, entry points, hot files, stable files
3. **[03-data-models.md](.claude/context/03-data-models.md)** - Pydantic models, data structures, validation patterns
4. **[04-patterns.md](.claude/context/04-patterns.md)** - Design patterns, coding conventions, best practices
5. **[05-decisions.md](.claude/context/05-decisions.md)** - Architecture Decision Records (ADRs)
6. **[06-dependencies.md](.claude/context/06-dependencies.md)** - External and internal dependencies
7. **[07-gotchas.md](.claude/context/07-gotchas.md)** - Known issues, workarounds, pitfalls
8. **[08-progress.md](.claude/context/08-progress.md)** - Current work status, recent commits, roadmap

### Checkpoints Location
- [.claude/checkpoints/](.claude/checkpoints/) - Full and incremental snapshots
- [.claude/sessions/](.claude/sessions/) - Session-specific notes
- [.claude/memory-bank/](.claude/memory-bank/) - Lessons learned across sessions

### Recovery After Interruption
1. Read most recent `.claude/checkpoints/checkpoint-*.md`
2. Read incremental checkpoints since then
3. Check [.claude/context/08-progress.md](.claude/context/08-progress.md)
4. Check `git status` and `git log --oneline -5`

### System Documentation
See [.claude/CHECKPOINT_SYSTEM.md](.claude/CHECKPOINT_SYSTEM.md) for complete documentation of the checkpoint system.

## Development Priorities

### High Priority
1. Create `requirements.txt` or `pyproject.toml` (no dependency specification currently)
2. Document NLP library dependency (spacy? nltk? - used for lemmatization)
3. Add installation instructions to README
4. Expand test coverage (currently minimal)

### Medium Priority
5. Merge Repeats → main after validation
6. Standardize CLI argument names (noted inconsistency in README)
7. Document legacy kmer files explicitly
8. Enhanced user documentation with examples

### Lower Priority
9. Package for PyPI distribution
10. Add CI/CD pipeline
11. Type checking with mypy/pyright
12. Refactor utils/ (some files contain business logic, should be in logic/)

## Design Comments

The design is flexible, allowing for more actions that minimally increase complexity of the base script and prevent runaway codebase of separate scripts.

**Note**: The project would greatly benefit from consolidating some functions and refactoring to improve consistency. For example, arguments and flags (Boolean arguments) for actions should have identical names where relevant, and similar names where functionality is semantically related.

## Extension Possibilities

Can easily be extended to support:
- `SearchDocumentResponse` model (wraps one or more `Cd` records with response metadata)
- `SearchFormResponse` model (same for `Form` responses)
- Direct API integration (currently processes downloaded JSON files)

## Quick Reference

**Entry Point**: [cde_analyzer.py](cde_analyzer.py) (or `cde_analyzer` executable)

**Core Engine**: [core/recursor.py](core/recursor.py) - 25 lines, handles all traversal

**Data Models**: [CDE_Schema/](CDE_Schema/) - Pydantic models mirroring NLM CDE API

**Actions**: [actions/](actions/) - Each action has cli.py + run.py

**Business Logic**: [logic/](logic/) - Core processing algorithms

**Utilities**: [utils/](utils/) - Helper functions (note: some contain complex logic)

**Tests**: [tests/](tests/) - Unit tests (minimal coverage currently)

**Documentation**:
- [README.md](README.md) - User-facing overview
- [docs/help/](docs/help/) - CLI command reference
- [docs/llm/](docs/llm/) - LLM classification guide
- [.claude/context/](.claude/context/) - Comprehensive context for AI assistance
