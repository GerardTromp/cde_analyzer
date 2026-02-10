# Development TODO List

This file tracks development tasks and enhancements for future sessions.

## High Priority

### Phrase Curation Partitioning
**Date Added**: 2026-01-28

**Problem**: When curating instrument or phrase patterns, the full list can be overwhelming (500+ patterns). Manual curation fatigue leads to errors and missed patterns.

**Proposed Solution**: Partition phrases into manageable groups (~30-40 per set) for editing/curation sessions.

**Implementation Ideas**:
1. Group by family/prefix (e.g., all Neuro-QOL patterns together)
2. Group by source field (designation vs definition)
3. Group by confidence score (high-confidence separate from low)
4. Add `--partition-output` flag to `strip_discover --coalesce-variants`
5. Output format: `coalesced_part01.tsv`, `coalesced_part02.tsv`, etc.
6. Or: Single file with `partition` column for filtering in spreadsheet

**Applies to**:
- Instrument pattern curation (strip_discover)
- Generic phrase curation (phrase_miner output)
- LLM classification review (llm_classify output)

---

---

### Smarter Expansion Subsumption
**Date Added**: 2026-01-28

**Problem**: Variant expansion can produce greedy false positives. Current reverse subsumption uses pure text-substring + tinyId-subset check, but a smarter approach is needed: if a discovered phrase is a subset of the original full_match pattern, check whether the full_match itself exists in the tinyIds. If yes → subsumed (expansion noise). If no → legitimate human variant that should persist.

**Also**: Filter "as part of" with no instrument name — clearly not a valid instrument pattern.

---

### Semantic Span Boundary Detection (`--group-semantic`)
**Date Added**: 2026-01-29

**Problem**: When grouping patterns by shared stems (prefix/suffix tree), the longest common span often overshoots the boilerplate boundary into content-bearing tokens. E.g., `"in the past 7 days I"` — the `"I"` syntactically attaches left but semantically belongs to the content clause.

**Proposed Solution**: Use SpaCy (`en_core_web_sm`) POS + dependency parsing to trim candidate spans back to the last non-function-word token. Three-stage pipeline:
1. **Suffix/prefix tree** groups patterns by shared spans
2. **POS-based trim** mechanically clips dangling function words (PRP, DT, CC, IN-clause-initial, TO)
3. **LLM** only reviews genuinely ambiguous boundaries

**Applies to**:
- Phase 2 phrase curation (temporal patterns, definitional templates, response scales)
- **Instrument pattern discovery** — instrument names also need field-specific boundary detection
- Any future pattern family that requires span extension/trimming

**Implementation**: `logic/span_boundary.py` (algorithm) + `--group-semantic` on `pattern_util` (CLI)

---

### Field-Specificity Across All Tools
**Date Added**: 2026-01-29

**Problem**: Most tools that work with Pydantic model data currently treat all fields uniformly. Field-aware processing (def-only vs desig-only vs both) should be a first-class concept throughout the pipeline, not bolted on per-tool.

**Scope**:
- `strip_discover` — already has `--fields` and field distribution
- `strip_phrases` — has `--fields` for stripping target selection
- `pattern_util --field-analysis` — newly added field enrichment
- `phrase_miner` — should support field-specific k-mer mining
- `instrument_family_assigner` — should track which field the match came from
- `llm_classify` — field_profile should inform classification prompts

**Action**: When implementing new features or refactoring existing ones, ensure field_path awareness is built in from the start rather than added retroactively.

---

### Iterative Discovery with Diagnostic Reports
**Date Added**: 2026-01-29

**Problem**: Discovery is inherently iterative. After each strip pass, surviving instrument patterns must be identified, diagnosed, and fed back into the pipeline. Currently this loop is fully manual (inspect CSV → identify gaps → modify code/patterns → re-run). The scheuermann06 session required 5 iterations to go from 404 → 236 surviving parenthetical fields.

**Proposed Solution**: `pattern_util --discovery-report` — a diagnostic scan that runs after stripping and produces a structured markdown report for curator review.

**Report Contents (per iteration)**:
1. **Surviving Pattern Census**: Scan stripped output for instrument-like patterns
   - `(ABBREV) -` patterns in designations (grouped by prefix)
   - `[ABBREV]` bracketed patterns in definitions
   - "as part of" anchors that survived stripping
   - Parenthetical abbreviations `(UPPERCASE)` anywhere
2. **Per-Pattern Detail**: For each surviving pattern type:
   - Frequency (tinyId count)
   - 2-3 context examples (full field text, truncated)
   - Whether the abbreviation exists in instruments.tsv
   - Why it may have been missed (not in abbrev set, name variant, separator mismatch)
3. **Iteration History Table**: Track across iterations
   - Iteration number, change description, pattern count, surviving count
   - Delta from previous iteration
4. **Curator Action Items**: Prioritized list of what to investigate next
   - High-frequency survivors first
   - Suggested pattern additions (auto-generated from surviving text)

**Implementation Plan**:

1. **New subcommand**: `pattern_util --discovery-report`
   - Input: stripped JSON + original JSON + curated patterns TSV
   - Output: markdown report + optional TSV of surviving patterns
   - Scans stripped JSON for instrument-like residuals
   - Compares against curated patterns to identify gaps

2. **Surviving pattern scanner** (`logic/discovery_diagnostics.py`):
   - Regex battery for instrument-like residuals
   - Group by prefix, count tinyIds, collect context examples
   - Cross-reference against instruments.tsv abbreviation set

3. **Report generator** with markdown output:
   - Iteration history table (auto-accumulated in JSON state file)
   - Per-pattern sections with frequency, examples, diagnosis
   - Curator action items prioritized by frequency

4. **Iteration state file** (JSON, auto-managed):
   - Each run appends iteration record with counts and timestamp
   - Enables cross-iteration comparison without manual tracking

5. **Workflow integration**: Optional post-strip step in `instrument_detection.yaml`

**Semi-automation flow**:
```
While surviving_patterns > threshold:
  1. Run pipeline (discover → coalesce → strip)
  2. Run discovery-report on stripped output
  3. Report identifies top-N surviving patterns with context
  4. Curator reviews report, decides:
     a. Add patterns manually → re-run from step 1
     b. Approve code fix (new pattern type) → implement → re-run
     c. Accept remaining as edge cases → stop
  5. Iteration state auto-updated
```

---

## Medium Priority

### Workflow Support for Diverging Instrument Pipelines
**Date Added**: 2026-01-28

After instrument mining, the pipeline diverges into two paths:
1. **Full instrument substitution** — strip using `curated_fullmatch.tsv` (pattern = full_match)
2. **Family-level substitution** — strip using `curated.tsv` (curator edits for family grouping)

Both paths also need generic phrase stripping on the resulting JSON. Currently the curator must manually rename/move the stripped JSON in `phase2_output`. Consider whether the workflow orchestrator should manage this (e.g., named output variants, or a branching step type).

---

### Workflow Step Dependencies
**Date Added**: 2026-01-28

Add file existence validation before step execution, with clear error messages about missing dependencies from previous steps.

---

### Test Coverage
- Unit tests for `tinyid_utils.py` (new `file:column` parsing functions)
- Integration tests for workflow resumption
- Tests for prefix extraction algorithm

---

## Completed

*(Move completed items here with date)*

- 2026-01-28: TinyId loading with `file:column` format and multi-value parsing
- 2026-01-28: Split strip_discover into focused commands (v0.4.2)
  - `strip_discover` - Core discovery only
  - `strip_analyze` - Analysis modes (false-negatives, conflicts)
  - `pattern_util` - TSV utilities (merge, coalesce, supplementary import)
  - TODO remaining: Regenerate workflow diagrams in `docs/diagrams/`
