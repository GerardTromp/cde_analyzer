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

**Active Branch**: main (v0.9.0)

**Recent Work** (Last 30 days):
- **v0.6.0: Multi-Curator Curation + Workflow Scaffold + Vignettes**
  - `--init-curation` / `--merge-curation` in pattern_util for multi-curator workflows
  - `logic/inter_rater.py` — Cohen's kappa, Fleiss' kappa, Krippendorff's alpha
  - `actions/pattern_util/curation_diff.html` — browser-based visual diff viewer
  - `workflow scaffold` command — generates project-specific pipeline orchestration scripts
  - Auto Windows→WSL path conversion, phase subset support, `--with-iterate`
  - 5 new vignettes: quickstart, instrument-detection, pipeline-orchestration, parameter-tuning, index
  - `mkdocs.yml` nav: "Guides" → "Guides & Vignettes"
  - Rare word detection with wordfreq Zipf scoring and whitelist
- **v0.5.15–v0.5.17: Documentation Restructuring**
  - Reorganized `mkdocs.yml` navigation: Workflows elevated, Command Reference section, LLM section, Appendix
  - Created `docs/about.md` (renamed from overview.md) and `docs/workflow-architecture.md` (consolidated from workflow-diagram + lessons_learned)
  - Generated SVGs: `detailed-workflow-architecture.svg`, `llm-workflow.svg` (replacing ASCII art)
  - Distributed `extensions_v0.5.x.md` content into relevant help pages; archived to `docs/appendix/`
  - Standardized CLI short options across 10 actions (phrase_miner, strip_discover, strip_phrases, pattern_util, instrument_miner, phrase_grouper, recall_analyze, pipeline_report, subset, count/fix_underscores)
  - Updated all `docs/help/*.md` pages and `all-commands.md`
- **v0.5.14: Temporal Case-Insensitive Split Pipeline**
  - Split `branching_strip.yaml` into separate temporal (case-insensitive) and curated phrase (case-sensitive) passes
  - Added bare/article-only temporal variant forms; expanded to 25 seeds (~2100 variants)
  - allcde01: 0 temporal remnants in definition/designation fields
- **v0.5.13: Universal Temporal Stripping + Dedup Pre-Pass + Bug Fixes**
  - `--expand-temporal-seeds`, `--merge-patterns`, `--dedup` in phrase_miner
  - Fixed workflow engine list args, phrase strip performance (5h → 13s), anchor expansion
- **v0.5.0: Parent Phrase Tracking & Recall Analysis**
  - `strip_discover --parent-column` propagates generic phrase info through pipeline
  - `pattern_util --min-parent-tinyids` filters low-coverage patterns during coalesce
  - `recall_analyze` integrated into both `instrument_detection.yaml` and `phrase_pipeline.yaml`
  - Conditional workflow steps (`condition:` in YAML) skip recall when no ground truth provided
  - Phrase pipeline validated on scheuermann02 (98.9% recall) and scheuermann03
- **v0.4.2: Command Split** - Split `strip_discover` into three focused commands:
  - `strip_discover` - Core pattern discovery only
  - `strip_analyze` - Conflict analysis and false-negative detection
  - `pattern_util` - TSV utilities (merge, coalesce, supplementary import)
- **Instrument Detection Workflow** - Complete 4-phase, 14-step automated pipeline
  - YAML-based workflow with 3 curator checkpoints
  - Comprehensive documentation: [docs/workflows/instrument-detection-workflow.md](docs/workflows/instrument-detection-workflow.md)
  - SVG workflow diagram: [docs/diagrams/instrument-detection-workflow.svg](docs/diagrams/instrument-detection-workflow.svg)
- **Prefix Extraction in Coalesce** (`--min-prefix-tinyids`)
  - Groups patterns by common word prefix (e.g., "Neuro-QOL Lower...", "Neuro-QOL Upper..." → "Neuro-QOL")
  - Dramatically reduces manual curation effort (553 patterns → ~50)
- **Abbreviation Pattern Discovery** (`--discover-abbreviations`)
  - Finds `[PROMIS]` bracketed suffix and `PROMIS - ...` hyphen prefix patterns
  - Catches patterns missed by k-mer mining
- Added `--coalesce-variants` mode for tinyId-aware pattern subsumption
- Added number word variants (7↔seven) and spaced punctuation variants
- Fixed tinyId format mismatch (space vs pipe separators) across pipeline
- MILESTONE: False-negative reduction complete (500 → 46 patterns, 91% reduction)
- Config-based supplementary patterns (`config/supplementary_patterns.yaml`)
- Enhanced Instrument Detection with family grouping (two-tier ID system)
- LLM classify action implementation
- Multi-provider support: Claude, OpenAI, Gemini
- Comprehensive MkDocs documentation

**Major Refactoring** (Dec 2024, commit 4400bf7):
- Converted to max-lazy loading architecture
- Dramatic startup performance improvement
- Inspired by git/pip command structure

## Actions (CLI Commands)

The `cde-analyzer` command accepts action arguments:

1. **fix_underscores** - Fix Pydantic-incompatible field names (underscore prefix)
2. **strip_html** - Remove HTML markup from CDE fields
3. **phrase** - Find repeated phrases across CDE records (original approach)
4. **phrase_miner** - Advanced k-mer phrase mining with iterative descent
5. **count** - Count structural elements and field occurrences
6. **extract_embed** - Extract fields for transformer model embedding
7. **strip_phrases** - Remove literal phrases at specified paths (substitution only)
8. **strip_discover** - Discover instrument patterns in CDE text fields (discovery only)
9. **strip_analyze** - Pattern conflict and false-negative analysis (NEW v0.4.2)
10. **pattern_util** - TSV utilities: merge, coalesce, supplementary import (NEW v0.4.2)
11. **diagnose_strip** - Diagnose remaining patterns after stripping
12. **lemma_fasta** - Create FASTA format from lemma sequences
13. **phrase_builder** - Incremental phrase construction
14. **subset** - Extract subsets using literal/regex/tinyID filters
15. **llm_classify** - Multi-LLM phrase classification with confidence aggregation
16. **workflow** - YAML-based workflow orchestrator with checkpoints
17. **strip_report** - Quality report for stripped JSON outputs (remnant detection, temporal phrases)

**Usage**: `cde-analyzer <action> [arguments]`

**Help**: `cde-analyzer <action> --help` for action-specific options

### phrase_miner Features (Advanced)
The `phrase_miner` action provides sophisticated phrase detection:
- Iterative descending k-mer mining (k=25 → k=3)
- Aho-Corasick multi-pattern matching for efficient masking
- De Bruijn graph extension (`--enable-debruijn`)
- Subsumption filtering (`--enable-subsumption`)
- Anchor-based phrase extension (`--enable-anchor`)
- Verbatim text recovery for original surface forms
- Instrument extraction with family grouping (`--detect-families`)

**Example**: `cde-analyzer phrase_miner -i cdes.json -o output/ --enable-subsumption`

**Instrument Family Detection**:
```bash
cde-analyzer phrase_miner -i cdes.json -o output/ --instruments-only --detect-families --family-summary
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

**Example**: `cde-analyzer llm_classify -i phrase_output/ -m instrument --providers claude openai`

**Instrument Adjudication Mode**:
```bash
cde-analyzer llm_classify --adjudicate-instruments instruments.tsv --adjudicate-threshold 0.7 -m instrument_family --providers claude
```
- Resolves uncertain family assignments from pattern-based detection
- Processes only instruments with `family_confidence < threshold`
- 15 family categories including known families and "other_instrument"

**Documentation**: See [docs/llm/](docs/llm/) for comprehensive guide.

### Pattern Stripping Workflow (v0.4.2)
Three-command workflow for pattern discovery, analysis, and stripping:

**Phase 1: Discovery** (`strip_discover`)
```bash
cde-analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv \
    --pattern-list instruments.tsv --expand-variants --discover-bare-names
```
- Loads patterns from TSV file
- Applies flexible regex matching to find verbatim occurrences
- Outputs TSV with columns: `pattern`, `tinyIds`, `type`, `source_pattern`
- Supports `--use-expected-tinyids` for filtered discovery
- Supports `--discover-fails` for failure logging
- Supports `--discover-abbreviations` for `[PROMIS]` and `PROMIS - ...` patterns

**Phase 2: Coalesce** (`pattern_util`)
```bash
cde-analyzer pattern_util --coalesce-variants discovered.tsv \
    -o coalesced.tsv --min-prefix-tinyids 3
```
- Removes patterns subsumed by longer patterns (tinyId-aware)
- Extracts common prefixes to reduce pattern count (553 → ~50)
- Also supports `--merge-patterns` for deduplication

**Phase 3: Substitution** (`strip_phrases`)
```bash
cde-analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json \
    --patterns coalesced.tsv --trace-matching trace.tsv
```
- Reads curator-reviewed patterns TSV
- Applies exact string replacement (longest-first by default)
- Supports parallel processing (`--workers`)

**Phase 4: Analysis** (`strip_analyze`)
```bash
# False-negative analysis
cde-analyzer strip_analyze --analyze-false-negatives \
    -i cleaned.json -o false_negatives.tsv

# Conflict analysis (before stripping)
cde-analyzer strip_analyze --analyze-conflicts report.tsv \
    --pattern-list patterns.tsv
```
- `--analyze-false-negatives`: Find remaining anchor patterns after stripping
- `--analyze-conflicts`: Detect pattern containment issues

**Supplementary Pattern Import** (`pattern_util`):
```bash
cde-analyzer pattern_util --add-to-supplementary curated.tsv
```
- Imports curated patterns to `config/supplementary_patterns.yaml`
- Re-run phrase_miner with `--extract-supplementary` to pick up new patterns

### Workflow Orchestrator (NEW)
YAML-based pipeline execution with checkpoints for human review:

```bash
# Run a workflow
cde-analyzer workflow run workflows/instrument_pipeline.yaml

# Override variables
cde-analyzer workflow run workflows/instrument_pipeline.yaml \
    --set input_json=/path/to/cdes.json \
    --set output_dir=/path/to/output

# Resume after checkpoint
cde-analyzer workflow resume --state-file ./output/.workflow_state.json

# Check status
cde-analyzer workflow status

# Preview without executing
cde-analyzer workflow run workflows/instrument_pipeline.yaml --dry-run
```

**Features**:
- Sequential step execution with action chaining
- Variable resolution: environment → YAML defaults → CLI overrides
- Checkpoint steps pause for human review
- State persistence for resume after interruption
- Dry-run mode for command preview

**Built-in Workflows** (`workflows/` directory):
- `instrument_detection.yaml` - **Full 4-phase instrument detection pipeline** (recommended)
  - Phase 1: Mining (instrument_miner, batch_expand_abbreviations, discover_abbreviations)
  - Phase 2: Discovery & Coalesce (discover_verbatim, coalesce with prefix extraction)
  - Phase 3: Family Analysis & Final Coalesce (phrase_grouper, re-discover, final coalesce)
  - Phase 4: Stripping & Verification (strip_phrases, diagnose_strip)
  - 3 checkpoints for curator review
- `instrument_pipeline.yaml` - Phase 1: Basic instrument mining & stripping
- `phrase_pipeline.yaml` - Phase 2: Generic phrase mining & stripping

**Workflow YAML Format**:
```yaml
name: my_workflow
variables:
  input_json: "${CDE_INPUT:-cdes.json}"
  output_dir: "./output"
steps:
  - name: mine_instruments
    action: instrument_miner
    args:
      input: "${input_json}"
      output: "${output_dir}/"
  - name: curator_review
    checkpoint: true
    message: "Review output, then resume"
  - name: strip_instruments
    action: strip_phrases
    args:
      input: "${input_json}"
      patterns: "${output_dir}/curated.tsv"
```

## Key Technical Notes

### Python Environment (WSL)
The project uses a Unix-style Python virtual environment. To run commands from Windows, use WSL:
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```
- Venv location: `/mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/`
- Has `bin/` directory (Unix-style), not `Scripts/` (Windows-style)

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
- `logic/verbatim_discoverer.py` (pattern discovery for strip_discover)
- `utils/phrase_extraction.py` (shared tokenization utilities)
- `utils/verbatim_tracker.py` (verbatim text recovery)
- `utils/subsumption_filter.py` (redundant phrase removal)
- `utils/aho_corasick_token.py` (efficient pattern matching)
- `utils/instrument_extractor.py` (instrument pattern extraction)
- `utils/instrument_family_patterns.py` (family detection regex patterns)
- `utils/flexible_pattern_matcher.py` (flexible regex for discovery)
- `utils/pattern_variant_generator.py` (spelling/punctuation variants)
- `utils/pattern_tsv_utils.py` (shared TSV loading for pattern commands)
- `utils/config_loader.py` (YAML config loading for supplementary patterns)
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
6. ~~Standardize CLI argument names~~ - **COMPLETED in v0.5.17**: Short options added across 10 actions
7. Document legacy kmer files explicitly
8. Enhanced user documentation with examples
9. ~~**Split strip_discover**~~ - **COMPLETED in v0.4.2**:
   - `strip_discover` - Core discovery only (pattern list → verbatim → TSV)
   - `strip_analyze` - Analysis modes (false-negatives, conflicts)
   - `pattern_util` - TSV utilities (merge, coalesce, supplementary import)
   - `utils/pattern_tsv_utils.py` - Shared TSV loading functions
   - **TODO**: Regenerate workflow diagrams in `docs/diagrams/`

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

**Entry Point**: [cde_analyzer.py](cde_analyzer.py) (or `cde-analyzer` executable)

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
- [docs/workflows/](docs/workflows/) - Workflow documentation
  - [instrument-detection-workflow.md](docs/workflows/instrument-detection-workflow.md) - **Detailed YAML workflow guide**
  - [instrument-phrase-stripping-workflow.md](docs/workflows/instrument-phrase-stripping-workflow.md) - Conceptual workflow
- [docs/workflow-architecture.md](docs/workflow-architecture.md) - Pipeline workflow architecture
- [docs/diagrams/](docs/diagrams/) - SVG workflow diagrams for embedding
- [.claude/context/](.claude/context/) - Comprehensive context for AI assistance
