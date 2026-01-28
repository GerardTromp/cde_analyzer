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

### Split strip_discover into Focused Commands
**Date Added**: 2026-01-28 (from CLAUDE.md backlog)

**Problem**: CLI has grown too large (5+ modes). Hard to document and maintain.

**Proposed Split**:
- `strip_discover` - Core discovery only (pattern list → verbatim → TSV)
- `strip_analyze` - Analysis modes (false-negatives, conflicts, supplementary import)
- `pattern_util` - TSV utilities (merge, coalesce) - no CDE input needed

**After split**: Regenerate workflow diagrams in `docs/diagrams/`

---

## Medium Priority

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
