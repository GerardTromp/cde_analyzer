# Gotchas and Known Issues

## Data Model Gotchas

### 1. Self-Referential Nesting
**Issue**: CDE data structures can nest arbitrarily deep

**Examples**:
- `Classification.elements[].elements` - recursive classification trees
- `Property.value` - can be a dict containing more properties
- `ElementInner.elements` - list of dicts that may contain more ElementInner

**Impact**:
- Must use recursive traversal (core/recursor.py)
- Cannot assume fixed depth
- Path tracking essential for context
- Potential for stack overflow on pathological data (unlikely in practice)

**Mitigation**:
- Always use recursive_descent() for deep traversal
- Don't hard-code nesting levels
- Test with deeply nested sample data

### 2. Optional Field Semantics
**Issue**: Three types of "empty" values

**Types**:
1. `None` - Field is null/not present
2. `""` - Empty string (distinct from None)
3. `[]` - Empty list (distinct from None)

**Code Example** (logic/counter.py:21):
```python
if value is None or value == "" or value == []:
    return match_type == "null"
```

**Impact**:
- Checks for emptiness must handle all three
- `if not value` catches all three but also catches `False`, `0`
- Explicit checks recommended: `if value is None or value == "" or value == []`

**Recommendation**: Use helper function for null checks

### 3. Underscore Field Names
**Issue**: MongoDB/API uses underscore-prefixed fields

**Examples**:
- `_id` - MongoDB primary key
- `__v` - Version field

**Pydantic Mapping**:
```python
id: Optional[str] = Field(alias="_id", default=None)
x__v: Optional[int] = None  # x__ prefix to avoid conflict
```

**Impact**:
- Field names diverge from API (x_id vs _id)
- Need fix_underscores action to prepare data
- Potential confusion when debugging API responses

**Workaround**: Use `fix_underscores` action before other processing

### 4. Duplicate Field Definitions
**Issue**: CDEForm has `elementType` defined twice (lines 57, 64 in CDE_Form.py)

**Code**:
```python
class CDEForm(BaseModel):
    elementType: Optional[str]    # Line 57
    # ... other fields ...
    elementType: Optional[str]    # Line 64 (duplicate!)
```

**Impact**:
- Second definition overwrites first
- No functional issue (same type)
- Confusing for readers
- May indicate schema inconsistency

**Recommendation**: Remove duplicate or add comment explaining

### 5. API Schema Typos
**Issue**: API has field name typos preserved in models

**Example**:
```python
class Comment(BaseModel):
    usename: Optional[str]  # Should be "username"

class Reply(BaseModel):
    usename: Optional[str]  # Should be "username"
```

**Impact**:
- Must use incorrect spelling to match API
- Confusing for developers
- Cannot "fix" without breaking API compatibility

**Rationale**: Models must exactly mirror API for validation

**Recommendation**: Add comment documenting the typo

## Architecture Gotchas

### 6. Lazy Loading Errors Only at Runtime
**Issue**: Action imports happen at invocation time

**Code** (cde_analyzer.py):
```python
# Module not imported until user selects action
module = load_action_module(args._module_path)
```

**Impact**:
- Import errors not caught at CLI startup
- Syntax errors discovered late
- Missing dependencies only fail when action invoked
- Can't validate all actions without running each

**Mitigation**:
- Test suite should invoke all actions
- Consider optional startup validation mode
- Good error messages on import failure

**Trade-off**: Fast startup vs early error detection

### 7. Global Verbosity State
**Issue**: Module-level mutable state (utils/analyzer_state.py)

**Code**:
```python
_verbosity = 1

def set_verbosity(level: int):
    global _verbosity
    _verbosity = level
```

**Impact**:
- Not thread-safe (but CLI is single-threaded)
- Hard to test multiple verbosity levels in same test run
- Potential issues if used as library
- Can't have different verbosity for different operations

**Mitigation**:
- Acceptable for CLI tool
- If library use needed, refactor to pass verbosity
- For testing, reset state between tests

**Rationale**: Simplicity over thread safety (appropriate for CLI)

### 8. ~~No Dependency Specification~~ (RESOLVED)
**Resolved**: `pyproject.toml` has full dependency specs. See `06-dependencies.md`.

## Code Organization Gotchas

### 9. Legacy Code Clutter
**Issue**: 12+ legacy kmer_*.py files in utils/

**Files**:
- kmer_phrase_detection.py
- kmer_build_longest_phrases.py (4 versions!)
- kmer_consolidated_phrases*.py
- kmer_extend_phrases*.py
- kmer_enrich_w_verbatim.py
- kmer_connect_extendedphrase.py
- plot_kmer_counts.py

**Impact**:
- Confusion about which is current
- Maintenance burden (may break)
- Unclear purpose of each version
- Discouraged from removing (represents work history)

**Recommendation**:
- Add README.md in utils/ explaining legacy status
- Consider moving to legacy/ subdirectory
- Document which (if any) are still referenced
- Archive in git branch if truly obsolete

### 10. Blurred Logic/Utils Boundary
**Issue**: Some "utility" files contain significant business logic

**Example**:
- `utils/phrase_extraction.py` - 9.4 KB, complex algorithms
- Should this be in logic/?

**Impact**:
- Unclear module purpose
- Hard to navigate codebase
- Inconsistent with architecture (see 01-architecture.md)

**Recommendation**:
- Review utils/ contents
- Move complex logic to logic/
- Keep only simple helpers in utils/

### 11. Inconsistent Argument Names
**Issue**: Similar functionality uses different names across actions

**Examples** (from README note):
- `--fields` vs `--field`
- `--verbose` vs `--verbosity`
- Inconsistent flag naming

**Impact**:
- Users must check help for each action
- Hard to remember correct names
- Inconsistent UX

**Status**: Acknowledged in README as needing refactoring

**Recommendation**:
- Standardize argument names
- Create shared argument groups
- Document conventions in developer guide

## Data Processing Gotchas

### 12. Path String Ambiguity
**Issue**: Three interpretation modes for field paths

**Modes** (--group-type):
- `top`: Top-level field only
- `path`: Full path contains key
- `terminal`: Deepest component matches

**Example**: `name` could mean:
- Top-level "name" field (top)
- Any path containing "name" (path)
- Any field named "name" at any depth (terminal)

**Impact**:
- Must understand and specify mode
- Easy to get unexpected results
- Mode choice affects matches

**Mitigation**:
- Clear documentation of modes
- Good defaults (top is safest)
- Examples in help text

### 13. CSV/TSV Data Loss
**Issue**: Flattening nested data loses structure

**Example**:
```json
{"designations": [{"designation": "Name1"}, {"designation": "Name2"}]}
```

Becomes:
```
designations.*.designation: "Name1, Name2"
```
(or multiple rows, depending on implementation)

**Impact**:
- Can't reconstruct original structure
- Lists lose order information
- Nested dicts become dot-notation strings

**Mitigation**:
- Document limitations in help text
- Recommend JSON for complex data
- CSV/TSV only for simple extracts

**Status**: Accepted trade-off for spreadsheet compatibility

### 14. ~~Lemmatization Dependencies~~ (RESOLVED)
**Resolved**: spaCy + NLTK documented in `pyproject.toml` and `06-dependencies.md`. Model: `en_core_web_sm`.

## Performance Gotchas

### 15. Recursive Traversal Performance
**Issue**: Visitor pattern on every node has overhead

**Code** (core/recursor.py):
```python
def recursive_descent(item, path, visitor, *, context=None, depth=0):
    # ... recursive calls and visitor invocation
```

**Impact**:
- Function call overhead per node
- Path string construction on every node
- Memory allocation for path strings

**Mitigation**:
- Acceptable for typical CDE data sizes
- For very large datasets, consider optimization
- Path construction is O(depth * nodes)

**Note**: Load time logs (load_times4.log) suggest performance acceptable

### 16. Lazy Loading Startup Trade-off
**Issue**: Action import happens first time invoked

**Impact**:
- First invocation slower (import cost)
- Subsequent invocations fast (if same action)
- User may notice delay on first run

**Mitigation**:
- Document expected behavior
- Import time typically < 1 second for most actions

**Trade-off**: First-run delay vs overall startup speed

## Testing Gotchas

### 17. ~~Minimal Test Coverage~~ (RESOLVED)
**Resolved**: 297 tests as of v1.0.1. Test-to-code ratio 1:15. Covers phrase_miner, flexible_pattern_matcher, workflow_engine, and more.

### 18. ~~No Type Checking~~ (PARTIALLY RESOLVED)
**Status**: mypy configured in `pyproject.toml` (`disallow_untyped_defs = false`, gradual adoption). ruff linting active.

## Deployment Gotchas

### 19. Executable Script Permissions
**Issue**: cde_analyzer.py must be executable

**Setup**:
```bash
chmod +x cde_analyzer.py
```

**Shebang**:
```python
#! /usr/bin/python3
```

**Impact**:
- Users may not know to set permissions
- Shebang assumes python3 in specific location
- May not work in virtual environments

**Recommendation**:
- Document in README
- Consider entry point in setup.py
- Provide both script and module invocation methods

### 20. Working Directory Assumptions
**Issue**: Relative imports assume specific working directory

**Impact**:
- Must run from project root
- Can't install as system-wide command
- IDE may have different working directory

**Mitigation**:
- Document working directory requirement
- Consider proper package installation
- Add __init__.py files for package structure

## User Experience Gotchas

### 21. Error Messages
**Issue**: Error messages may not be user-friendly

**Example**: Pydantic validation errors can be verbose and technical

**Recommendation**:
- Catch and reformat Pydantic errors
- Provide context about what went wrong
- Suggest fixes when possible

### 22. Help Text Consistency
**Issue**: Help text format varies across actions

**Recommendation**:
- Standardize help text format
- Include examples in help
- Consistent terminology

### 23. Output Format Confusion
**Issue**: Some outputs may be ambiguous

**Example**: Count results - what do numbers represent?

**Mitigation**:
- Clear column headers in CSV/TSV
- JSON keys should be descriptive
- Include units/context in output

## Parallelization Gotchas

### 24. Global State in Multiprocessing Workers
**Issue**: Global variables don't share state across ProcessPoolExecutor workers

**Context**: The `strip_phrases` action uses multiprocessing for parallel phrase stripping. Initially, match logging (tracking which patterns matched) forced sequential mode because global `_match_log` state isn't shared across workers.

**Why This Happens**:
- `ProcessPoolExecutor` forks worker processes with isolated memory spaces
- Each worker gets its own copy of global variables after fork
- Modifications in workers are invisible to the main process and other workers

**Solution Pattern**: Per-worker collection with main process aggregation
```python
def _worker_process_chunk(chunk_with_indices):
    """Worker collects data locally and returns it."""
    global _match_log
    _match_log = []  # Reset per chunk (workers may be reused)

    for data in data_list:
        processed = process_item(data)  # Populates _match_log
        results.append(processed)

    # Return collected data alongside results
    return chunk_idx, results, list(_match_log)

# Main process aggregates after all workers complete
all_matches = []
for future in as_completed(futures):
    chunk_idx, processed, matches = future.result()
    all_matches.extend(matches)
```

**Key Points**:
1. Workers can maintain independent state — this is a feature, not a bug
2. Reset per-chunk state at start (workers may be reused)
3. Extend return tuple to include data needing aggregation
4. Aggregate in main process after parallel completion

**Impact**: Match logging (`--match-log`, `--match-summary`) now works with parallel execution. Only trace file output (`--trace-matching`) requires sequential mode because it needs streaming file writes.

**See**: `.claude/analysis/parallel-match-logging.md` for full implementation details.

---

### 25. Trace Files vs Batch Logging
**Issue**: Streaming output to files cannot be parallelized without temp file merging

**Context**: `strip_phrases` has two diagnostic modes:
- `--trace-matching FILE`: Streams detailed per-match output during processing
- `--match-log FILE`: Writes batch summary after all processing completes

**Current Behavior** (all parallel-safe):
- `--trace-matching` collects per-worker entries, merges by timestamp after completion
- `--match-log` and `--match-summary` work with parallel execution

**Pattern**: All diagnostic features use batch aggregation — workers collect entries in per-process memory, return them alongside processed data, and the main process aggregates and writes to file after all workers complete.

---

## Coalescer Gotchas

### 28. Reverse Subsumption Drops Instrument Sub-Domains
**Issue**: Phase 1b reverse subsumption removes long patterns whose tinyIds ⊆ a shorter base's tinyIds, treating them as "greedy expansions". But when the shorter is a prefix of the longer AND the extension is a noun phrase, it's a family sub-domain, not greedy context gobbling.

**Example**:
- "NIH Toolbox" (9 tinyIds) subsumes "NIH Toolbox General Life Satisfaction" (9 tinyIds)
- Phase 1b removed the longer form, leaving only "NIH Toolbox"
- After stripping "NIH Toolbox", the residual "General Life Satisfaction" appears as a false positive in diagnostics

**Fix** (v0.5.11): `_is_np_continuation()` helper checks if the extension beyond the prefix is NP-like (80%+ Title Case words). If so, both forms are kept.

**Location**: `utils/flexible_pattern_matcher.py` — Phase 1b loop (~line 1412) and helper (~line 1056)

**Impact**: allcde01 coalesced patterns increased from 417 to 604 (+325 sub-domain patterns preserved)

### 29. Anchor-Prefix Residuals After Stripping
**Issue**: After stripping "Dizziness Handicap Inventory", the sanity check finds "the Dizziness Handicap Inventory" (29x) because the anchor prefix "the" was attached in the source text but not expanded during stripping.

**Mitigation**: The iterative stripping pipeline (`phase1_iterate`) harvests these residuals and adds them to the pattern set for the next round. The `--harvest-to-supplementary` command ingests them into `supplementary_patterns.yaml` for permanent coverage.

**Location**: `actions/diagnose_strip/run.py`, `actions/pattern_util/run.py` (harvest functions)

## Future Gotchas

### 26. API Schema Evolution
**Issue**: NLM CDE API may change schema

**Impact**:
- Pydantic models may become outdated
- New fields not captured
- Changed fields break validation

**Mitigation**:
- Regular schema updates
- Versioning strategy
- Backward compatibility considerations

### 27. Python Version Sunset
**Issue**: Python 3.7 end-of-life

**Impact**:
- May need to update syntax
- Libraries may drop support

**Mitigation**:
- Test with newer Python versions
- Update type hint syntax if needed
- Monitor dependency compatibility

## Best Practices to Avoid Gotchas

1. **Always use recursive_descent()** for nested data traversal
2. **Explicit null checks**: Check for None, "", and [] explicitly
3. **Test with real data**: Use actual CDE API responses
4. **Document assumptions**: Add comments for non-obvious behavior
5. **Standardize patterns**: Follow established action structure
6. **Version dependencies**: Use requirements.txt or pyproject.toml
7. **Write tests**: Especially for core components
8. **Clear error messages**: Help users understand failures
9. **Document gotchas**: Update this file as new issues found
10. **Regular refactoring**: Address technical debt incrementally
