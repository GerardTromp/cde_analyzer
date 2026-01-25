# Architecture Decision Records (ADRs)

## ADR-001: Pydantic for Data Modeling

**Date**: Initial design (pre-dating git history)

**Status**: Accepted

**Context**:
- NLM CDE API returns complex, nested JSON structures
- Data has variable schema (many optional fields)
- Need type safety and validation
- Need clear documentation of expected structure

**Decision**: Use Pydantic BaseModel classes to model the entire CDE API schema

**Rationale**:
- Type hints provide IDE support and documentation
- Automatic validation of API responses
- Easy serialization/deserialization (JSON ↔ Python objects)
- Self-documenting code (class definitions mirror API spec)
- Handles optional fields elegantly

**Consequences**:
- **Positive**:
  - Type-safe data handling
  - Clear schema documentation in code
  - Catches API mismatches early
  - Easy to extend as API evolves
- **Negative**:
  - Pydantic dependency required
  - Some performance overhead for validation
  - Field name conflicts (underscore prefix) require aliases

**Referenced In**: CDE_Schema/*.py, README.md

---

## ADR-002: Layered Action Architecture

**Date**: Initial design

**Status**: Accepted

**Context**:
- Multiple distinct operations needed (count, extract, phrase analysis, HTML stripping)
- Each operation has specific arguments
- Want to keep CLI startup fast
- Want to maintain clean separation of concerns

**Decision**: Implement a three-layer architecture for actions:
1. **CLI Layer** (cli.py): Argument parsing only
2. **Orchestration Layer** (run.py): File I/O, result formatting
3. **Business Logic Layer** (logic/*.py): Core processing algorithms

**Rationale**:
- Separation of concerns makes code maintainable
- Business logic testable without CLI dependencies
- Consistent structure makes adding new actions predictable
- Orchestration layer handles cross-cutting concerns (I/O, formatting)

**Consequences**:
- **Positive**:
  - Clear, consistent structure
  - Testable business logic
  - Easy to add new actions
  - Contributors know where to look
- **Negative**:
  - More files per action (3 instead of 1)
  - Some code duplication in I/O handling
  - Steeper learning curve for simple additions

---

## ADR-003: Lazy Loading Architecture

**Date**: December 2024 (commit 4400bf7)

**Status**: Accepted

**Context**:
- CLI startup becoming slow (see load_times4.log)
- Many actions loading heavy dependencies (NLP libraries, etc.)
- User only invokes one action per execution
- Git/pip provide good models for subcommand CLIs

**Decision**: Implement max-lazy loading where action modules are only imported when invoked

**Implementation**:
```python
ACTION_REGISTRY = {
    "action_name": {
        "module": "actions.action_name.cli",
        "help": "...",
        "description": "..."
    }
}

# Load module only when user selects that action
module = importlib.import_module(registry[action]["module"])
args.func(args)
```

**Rationale**:
- Dramatic startup time improvement
- Memory efficiency (only load what's needed)
- Scales well as more actions added
- Proven pattern (git, pip use similar approach)

**Consequences**:
- **Positive**:
  - Fast CLI response (immediate help text)
  - Lower memory footprint
  - Can add heavy dependencies without affecting startup
  - Better user experience
- **Negative**:
  - Slightly more complex dispatcher code
  - Import errors only caught at runtime (not startup)
  - Each action must be self-contained

**Commit**: 4400bf7 "Refactor launcher to be fully lazy load"

**Related Commits**:
- 57b9437, 4e601c7: Launcher fixes post-refactoring

---

## ADR-004: Single Recursive Descent Engine

**Date**: Initial design

**Status**: Accepted

**Context**:
- CDE data structures are deeply nested
- Self-referential nesting (Classification.elements.elements...)
- Many operations need to traverse entire structure
- Want consistent traversal logic

**Decision**: Implement a single recursive descent engine using visitor pattern

**Implementation**: `core/recursor.py` - 25 lines, handles all traversal

**Rationale**:
- DRY principle: Write traversal once, use everywhere
- Visitor pattern separates traversal from processing
- Path tracking provides context for leaf nodes
- Handles both dict and list structures uniformly

**Consequences**:
- **Positive**:
  - Consistent traversal across all actions
  - Easy to add new operations (just write visitor)
  - Compact, well-tested core engine
  - Path strings useful for debugging
- **Negative**:
  - All operations must fit visitor pattern
  - Performance overhead of function calls per node
  - Path strings may be less efficient than indices

**Used By**: All logic/* modules requiring deep traversal

---

## ADR-005: Multiple Output Formats

**Date**: Initial design

**Status**: Accepted

**Context**:
- Different users have different downstream tools
- JSON good for nested data, bad for spreadsheets
- CSV/TSV good for analysis, bad for nested data
- Want flexibility without code duplication

**Decision**: Support JSON, CSV, and TSV output via `--output-format` flag

**Implementation**:
- Internal representation: Python dict/list
- utils/output_writer.py: Format conversion
- Dot notation for nested keys in flat formats

**Rationale**:
- Users choose format for their workflow
- JSON preserves structure
- CSV/TSV enables Excel, R, Python pandas
- Standard formats, no custom parsers needed

**Consequences**:
- **Positive**:
  - Flexibility for diverse workflows
  - No need for separate conversion scripts
  - Interoperability with many tools
- **Negative**:
  - CSV/TSV loses nesting information
  - Need flattening logic for complex results
  - Users must understand format limitations

---

## ADR-006: Optional Field Strategy

**Date**: Initial design

**Status**: Accepted

**Context**:
- NLM CDE API returns sparse data
- Not all fields present in all records
- Want to avoid validation errors
- Need to distinguish None vs "" vs []

**Decision**: Make nearly all Pydantic fields Optional with `= None` default

**Rationale**:
- API responses highly variable
- Better to accept sparse data than fail validation
- Downstream code can check for presence
- Matches API's optional semantics

**Consequences**:
- **Positive**:
  - Robust parsing of API responses
  - No validation errors on missing fields
  - Flexible data handling
- **Negative**:
  - Weaker validation (accepts incomplete data)
  - Downstream code must check None
  - Type hints less informative (everything Optional)

**Trade-off**: Flexibility over strict validation (appropriate for data analysis tool)

---

## ADR-007: Legacy Code Retention

**Date**: Ongoing

**Status**: Accepted (with reservations)

**Context**:
- Multiple experimental approaches to phrase detection (kmer_*.py files)
- Tried various algorithms for finding longest repeated phrases
- Some approaches didn't work well but represent significant effort

**Decision**: Retain legacy kmer_*.py modules in utils/ directory

**Rationale**:
- Document what has been tried
- May revisit approaches later
- Show evolution of thinking
- Reference for understanding problem space

**Consequences**:
- **Positive**:
  - History preserved
  - Can compare approaches
  - Avoids repeating failed experiments
- **Negative**:
  - Clutter in utils/ directory
  - Maintenance burden (may break)
  - Confusing for new contributors
  - Unclear what's active vs legacy

**Note**: Files explicitly documented as "LEGACY" in codebase map. Consider moving to separate archive branch or dedicated legacy/ directory.

**Affected Files**:
- kmer_phrase_detection.py
- kmer_build_longest_phrases.py (4 versions!)
- kmer_consolidated_phrases*.py
- kmer_extend_phrases*.py
- kmer_enrich_w_verbatim.py
- kmer_connect_extendedphrase.py
- plot_kmer_counts.py

---

## ADR-008: Path-Based Field Addressing

**Date**: Initial design

**Status**: Accepted

**Context**:
- Need to specify fields in nested structures
- Users don't know exact nesting depth
- Want flexible, readable syntax

**Decision**: Use dot notation with wildcards for field paths

**Syntax**:
- `tinyId` - top-level field
- `valueDomain.datatype` - nested field
- `designations.*.designation` - all designation text values
- `*.name` - any name field at any depth

**Rationale**:
- Intuitive for users familiar with JSON
- Wildcard handles variable list lengths
- Single syntax for multiple path types

**Implementation**: Three interpretation modes (`--group-type`):
- `top`: Top-level only
- `path`: Full path contains key
- `terminal`: Deepest component matches

**Consequences**:
- **Positive**:
  - User-friendly syntax
  - Handles nesting flexibly
  - Works with recursive traversal
- **Negative**:
  - Ambiguity requires mode selection
  - Wildcard matching can be slow
  - No array indexing (only `*`)

---

## ADR-009: Underscore Field Handling

**Date**: Initial implementation

**Status**: Accepted

**Context**:
- MongoDB uses `_id` for primary key
- API includes `__v` version field
- Python convention: leading underscore = private
- Pydantic doesn't like underscore-prefixed names

**Decision**: Use Field aliases to map API names to Python-safe names

**Implementation**:
```python
class CDEForm(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    x__v: Optional[int] = None  # Maps to "__v"
```

**Action**: Created `fix_underscores` action to clean data files

**Rationale**:
- Preserve API semantics
- Avoid Python naming conflicts
- Allow Pydantic validation

**Consequences**:
- **Positive**:
  - Models work with API data
  - Python-compliant naming
  - Clear mapping via aliases
- **Negative**:
  - Divergence from API names (x_id vs _id)
  - Need fix_underscores action for data prep
  - Potential confusion for API users

---

## ADR-010: Verbosity via Global State

**Date**: Initial design

**Status**: Accepted (pragmatic choice)

**Context**:
- Need verbosity control throughout application
- Many layers of function calls
- Don't want to pass verbosity to every function

**Decision**: Use module-level global state in `utils/analyzer_state.py`

**Implementation**:
```python
_verbosity = 1

def set_verbosity(level: int):
    global _verbosity
    _verbosity = level

def get_verbosity() -> int:
    return _verbosity
```

**Rationale**:
- Simple, pragmatic solution
- Avoids parameter passing through many layers
- CLI tools typically single-threaded
- Logging module uses similar approach

**Consequences**:
- **Positive**:
  - Clean function signatures
  - Easy to use throughout codebase
  - Standard pattern for CLI tools
- **Negative**:
  - Global mutable state
  - Not thread-safe
  - Harder to test with different verbosity levels
  - Potential issues if used as library

**Trade-off**: Simplicity over thread safety (acceptable for CLI tool)

---

## ADR-011: Multi-LLM Classification Architecture

**Date**: January 2026 (commit 10b7f13)

**Status**: Accepted

**Context**:
- Need to classify phrases extracted by phrase_miner into semantic categories
- Manual curation of thousands of phrases is time-consuming
- Different LLMs may have different strengths/biases
- Want confidence scoring to prioritize human review
- API keys are sensitive and need secure handling

**Decision**: Implement multi-LLM classification with async providers, pluggable modules, and confidence aggregation

**Implementation**:

1. **Provider Abstraction** (`utils/llm/provider_base.py`)
   - Abstract LLMProvider class for uniform interface
   - Implementations for Claude, OpenAI, Gemini
   - Async batch processing with rate limiting

2. **API Key Resolution** (`utils/llm/config.py`)
   - Priority: config file → environment variables → CLI
   - Config file: `~/.cde_analyzer/llm_config.json`
   - CLI args documented as least preferred (security)

3. **Query Module Framework** (`utils/query_modules/`)
   - Abstract QueryModule for pluggable classification tasks
   - Current modules: instrument_detector, temporal_detector
   - Modules define categories, prompts, and response parsing

4. **Result Aggregation** (`utils/llm/result_aggregator.py`)
   - Four methods: unanimous, majority, weighted_majority, confidence_weighted
   - Quintile system: highly_likely → highly_unlikely (5 levels)
   - Agreement tracking: unanimous, majority, split

**Rationale**:
- Multi-LLM reduces single-provider bias
- Async pattern enables parallel queries (faster)
- Pluggable modules allow easy extension
- Quintile system aids human curation prioritization
- Config file priority protects API keys

**Consequences**:
- **Positive**:
  - Robust classification with cross-validation
  - Fast execution via async parallelism
  - Extensible to new classification tasks
  - Secure API key handling
  - Human curation aided by confidence scores
- **Negative**:
  - External API dependency (costs, availability)
  - Requires API keys from multiple providers
  - Added complexity (async, multiple providers)
  - Network latency affects performance

**Commit**: 10b7f13 "Implement llm_classify command for multi-LLM phrase classification"

**Files Created**:
- CDE_Schema/LLM_Classification.py
- logic/llm_classifier.py
- actions/llm_classify/ (cli.py, run.py)
- utils/llm/ (7 files)
- utils/query_modules/ (4 files)
- docs/llm/ (4 documentation files)

---

## ADR-012: Confidence Quintile System

**Date**: January 2026

**Status**: Accepted

**Context**:
- LLMs return confidence scores (0.0-1.0)
- Need human-readable confidence levels
- Want consistent terminology across tools

**Decision**: Use 5-tier quintile system for confidence levels

**Mapping**:
| Score Range | Quintile | Interpretation |
|------------|----------|----------------|
| 0.81-1.00 | highly_likely | High confidence, minimal review needed |
| 0.61-0.80 | likely | Good confidence, spot-check recommended |
| 0.41-0.60 | indeterminate | Uncertain, human review required |
| 0.21-0.40 | unlikely | Low confidence, likely incorrect |
| 0.00-0.20 | highly_unlikely | Very low confidence, probably wrong |

**Rationale**:
- Equal-width bins are intuitive
- Five levels balance granularity and simplicity
- Names convey clear meaning
- "Indeterminate" highlights uncertainty for review

**Consequences**:
- **Positive**:
  - Easy to understand
  - Actionable (prioritize "indeterminate" for review)
  - Consistent terminology
- **Negative**:
  - Loses precision of raw scores
  - Boundary effects (0.60 vs 0.61)

---

## ADR-013: Two-Tier Instrument Identification

**Date**: January 2026

**Status**: Accepted

**Context**:
- Instruments extracted by phrase_miner need grouping by family (e.g., all Neuro-QOL subscales together)
- Need to enable text substitution testing (family-level vs full instrument name)
- Pattern-based detection may have low confidence for some instruments
- LLM adjudication can resolve uncertain cases but adds cost
- Need to track which instruments need human review

**Decision**: Implement two-tier identification with `family_id` + `instrument_id` and confidence-based LLM adjudication

**Implementation**:

1. **Two-Tier ID System**:
   - `family_id`: Short identifier (e.g., "neuro-qol", "promis", "mds-updrs")
   - `instrument_id`: Unique slug (e.g., "neuro-qol-ability-participate-sra")
   - `family_display_name`: Human-readable name for substitution testing

2. **Pattern-Based Detection** (`utils/instrument_family_patterns.py`):
   - 13 known families with regex patterns
   - Confidence scoring based on pattern specificity
   - False positive exclusion patterns

3. **Confidence Thresholding**:
   - Instruments with `family_confidence < 0.7` flagged with `needs_review=True`
   - Enables prioritized human curation

4. **LLM Adjudication** (optional):
   - `llm_classify --adjudicate-instruments` for uncertain cases
   - 15-category query module (`instrument_family_detector.py`)
   - Only processes instruments below threshold

**Rationale**:
- Two-tier system enables both family-level and individual analysis
- Pattern-based detection is fast and free (no API costs)
- Confidence thresholding focuses LLM costs on uncertain cases
- Human review queue prevents unvalidated classifications

**Consequences**:
- **Positive**:
  - Enables family-based text substitution experiments
  - Reduces LLM costs by only adjudicating uncertain cases
  - Provides clear review queue for human curators
  - Extensible to new instrument families
- **Negative**:
  - Additional complexity in output files
  - Regex patterns may miss novel naming conventions
  - Requires domain expertise to add new family patterns

**Files Created**:
- `utils/instrument_family_patterns.py` (InstrumentFamilyDetector)
- `utils/query_modules/instrument_family_detector.py` (LLM module)
- `logic/instrument_family_assigner.py` (orchestration)

**Files Modified**:
- `CDE_Schema/LLM_Classification.py` (InstrumentFamily enum, InstrumentIdentification)
- `utils/instrument_extractor.py` (InstrumentMatch family fields, assign_families method)
- `actions/phrase_miner/cli.py` (--detect-families, --family-confidence-threshold, --family-summary)
- `actions/phrase_miner/run.py` (family output generation)
- `actions/llm_classify/cli.py` (--adjudicate-instruments, --adjudicate-threshold)
- `utils/query_modules/__init__.py` (instrument_family module registration)

---

## Deferred Decisions

### DD-001: Test Framework Choice
**Context**: Minimal testing currently exists
**Options**: unittest (standard library) vs pytest (more features)
**Status**: Needs decision when expanding tests

### DD-002: Argument Name Standardization
**Context**: README notes inconsistency in argument names
**Status**: Needs systematic review and refactoring plan

### DD-003: Legacy Code Cleanup Strategy
**Context**: Multiple kmer_*.py files retained
**Options**: Remove, archive branch, legacy/ directory
**Status**: Awaiting decision from project owner

### DD-004: Type Checking Strategy
**Context**: Type hints present but no mypy/pyright enforcement
**Options**: Add mypy to CI, use pyright, skip static checking
**Status**: Needs decision if type safety becomes priority

---

## Open Questions

1. **Why multiple kmer_build_longest_phrases versions?**
   - 4 versions suggest iterative refinement
   - No clear documentation of differences
   - Which (if any) worked best?

2. **Why both logic/ and utils/ for phrase processing?**
   - utils/phrase_extraction.py is 9.4 KB (not a simple utility)
   - Boundary between "logic" and "utils" unclear
   - Should phrase_extraction move to logic/?

3. **Is lemmatization always desired?**
   - phrase action defaults to lemmatize=True
   - Some contexts may want exact text
   - Current design flexible with flag

4. **What's the relationship between actions?**
   - Is there a typical workflow? (e.g., fix_underscores → strip_html → phrase)
   - Should there be pipeline support?
   - Or are actions independent?

---

## Decision-Making Process

**Current**: Implicit, documented through commit messages and code comments

**Observation**: This ADR document created retrospectively by analyzing:
- Git commit messages
- Code structure and patterns
- README.md notes
- Inline comments

**Recommendation**: For future decisions, document:
1. Context (why decision needed)
2. Options considered
3. Decision made
4. Rationale
5. Expected consequences

**Tool**: Could use ADR template and store in `.claude/context/decisions/` directory
