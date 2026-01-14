# Legacy Kmer-Based Phrase Detection

**Status:** Archived - Experimental code retained for historical reference

**Date Archived:** 2026-01-13

## Overview

This directory contains archived experimental implementations of kmer-based phrase detection algorithms developed during the exploratory phase of the CDE Analyzer project. These files represent multiple iterations of different algorithmic approaches to finding repeated phrases in Common Data Element text fields.

## Why Archived

The production system now uses a different approach:
- **Current Implementation:** NLTK-based tokenization and lemmatization with recursive descent pattern matching
- **Location:** `utils/phrase_extraction.py` and `logic/phrase_extractor.py`
- **Active Legacy Code:** Only `utils/kmer_extend_phrases1.py` remains in active use

## Consolidated Version

All algorithms from these files have been consolidated into:
**`utils/kmer_legacy_algorithms.py`**

This single file provides:
- `is_sub_kmer()` - Shared utility (was duplicated 5 times)
- `build_longest_phrases_*()` - Three versions (simple, with tracking, iterative)
- `extend_within_bins_*()` - Two versions (basic, with deduplication)
- `consolidate_phrases_*()` - Two strategies (merging, pruning)
- `group_connectors()` - Connector-based phrase grouping
- `enrich_with_verbatim()` - Lemma-to-verbatim mapping

## Original Files

### Phrase Building (5 files - 85-100% similar)

#### `kmer_phrase_detection.py`
- **Purpose:** Original phrase detection attempt
- **Algorithm:** Group kmers by count, extend forward, discard sub-kmers
- **Status:** Identical to kmer_build_longest_phrases.py (appears to be v0)
- **Lines:** 69

#### `kmer_build_longest_phrases.py`
- **Purpose:** Version 1 - Basic phrase building
- **Algorithm:** Same as kmer_phrase_detection.py
- **Output:** Simple format (phrase, k, count)
- **Lines:** 69

#### `kmer_build_longest_phrases2.py`
- **Purpose:** Version 2 - Add tinyId tracking
- **Enhancement:** Tracks `kmer_source` (which tinyIds) and `fields`
- **Difference:** +18% code, line 50 uses `kmer_source`
- **Lines:** 86

#### `kmer_build_longest_phrases3.py`
- **Purpose:** Version 3 - Alternative tinyId tracking
- **Enhancement:** Tracks `tinyId` instead of `kmer_source`
- **Difference:** Nearly identical to v2, line 50 uses `tinyId`, line 76 outputs `tinyIds`
- **Lines:** 85

#### `kmer_build_longest_phrases4.py`
- **Purpose:** Version 4 - Iterative bin processing
- **Enhancement:** Processes one frequency bin at a time, removes consumed kmers
- **Algorithm:** Split into `extend_phrases_once()` + `build_longest_phrases_iterative()`
- **Benefit:** Cleaner separation of phrase frequencies
- **Lines:** 96

**Code Duplication:** All 5 files contain identical `is_sub_kmer()` function (lines 3-9).

### Phrase Extension (3 files)

#### `kmer_extend_phrases1.py` ✓ **STILL IN ACTIVE USE**
- **Purpose:** Production phrase extension
- **Location:** `utils/kmer_extend_phrases1.py` (NOT archived)
- **Used by:** `logic/phrase_builder.py:12`
- **Function:** `extend_phrases_in_bin()` with `try_merge()` helper
- **Algorithm:** Merge overlapping phrases within count bins
- **Lines:** 114

#### `kmer_extend_phrases2.py`
- **Purpose:** Version 2 - Bidirectional extension
- **Algorithm:** Uses prefix/suffix indexes for efficient extension
- **Enhancement:** Extends both forward and backward
- **Lines:** 86

#### `kmer_extend_phrases3.py`
- **Purpose:** Version 3 - Extension with deduplication
- **Enhancement:** Same as v2 PLUS removes contained phrases (lines 87-103)
- **Difference:** +24% code for deduplication logic
- **Lines:** 106

### Phrase Consolidation (2 files - different strategies)

#### `kmer_consolidated_phrases1.py`
- **Purpose:** Strategy 1 - Merge overlapping phrases
- **Algorithm:** Iteratively merge phrases with suffix/prefix overlap
- **Approach:** Greedy merging until no more merges possible
- **Lines:** 48

#### `kmer_consolidated_phrases2.py`
- **Purpose:** Strategy 2 - Prune subsequences
- **Algorithm:** Keep longest phrases, remove subsequences
- **Approach:** Filtering rather than merging
- **Lines:** 42

### Advanced Analysis (2 files - unique algorithms)

#### `kmer_connect_extendedphrase.py`
- **Purpose:** Phase 3 - Connector-based grouping
- **Algorithm:** Find common prefix/suffix connectors, group branches
- **Use Case:** Identify phrases that serve as connectors between variations
- **Parameters:** `min_branch`, `constrain_fields`, `both_directions`
- **Lines:** 116

#### `kmer_enrich_w_verbatim.py`
- **Purpose:** Map lemmas back to verbatim text
- **Algorithm:** Use tinyId mapping to recover original wording
- **Use Case:** Surface form variation analysis
- **Output:** Adds `verbatim_variants` with variant counts
- **Lines:** 57

## Evolution Timeline

```
kmer_phrase_detection.py (v0)
    ↓
kmer_build_longest_phrases.py (v1 - basic)
    ↓
kmer_build_longest_phrases2.py (v2 - add kmer_source tracking)
    ↓
kmer_build_longest_phrases3.py (v3 - use tinyId instead)
    ↓
kmer_build_longest_phrases4.py (v4 - iterative bin processing) ✓ BEST

kmer_extend_phrases1.py (production) ✓ ACTIVE
    ↓
kmer_extend_phrases2.py (bidirectional extension)
    ↓
kmer_extend_phrases3.py (+ deduplication) ✓ BEST

kmer_consolidated_phrases1.py (merge strategy)
kmer_consolidated_phrases2.py (prune strategy) ← different approaches

kmer_connect_extendedphrase.py (connector analysis) ← unique
kmer_enrich_w_verbatim.py (verbatim mapping) ← unique
```

## Algorithm Families

### 1. Substring Detection
**Function:** `is_sub_kmer(small, large)`
- Check if one kmer is contiguous subsequence of another
- Duplicated identically in 5 files

### 2. Phrase Building
**Goal:** Build longest phrases from overlapping kmers
- **v1 (simple):** Basic extension, no tracking
- **v2-3 (tracking):** Add tinyId and field tracking
- **v4 (iterative):** Process bins separately, remove consumed kmers

### 3. Phrase Extension
**Goal:** Extend phrases by finding overlapping neighbors
- **v1 (production):** Simple overlap-based merging
- **v2 (indexed):** Prefix/suffix indexes for efficiency
- **v3 (dedup):** Add deduplication of contained phrases

### 4. Phrase Consolidation
**Goal:** Reduce redundancy in phrase lists
- **Strategy 1:** Merge overlapping phrases (iterative)
- **Strategy 2:** Prune subsequences (filtering)

### 5. Advanced Analysis
- **Connector Grouping:** Find phrases that connect variations
- **Verbatim Enrichment:** Map lemmas back to surface forms

## Code Metrics

| File | Lines | Functions | Unique Algorithm |
|------|-------|-----------|-----------------|
| kmer_phrase_detection.py | 69 | 2 | ❌ (= v1) |
| kmer_build_longest_phrases.py | 69 | 2 | ❌ (= v0) |
| kmer_build_longest_phrases2.py | 86 | 2 | ⚠️ (v1 + tracking) |
| kmer_build_longest_phrases3.py | 85 | 2 | ⚠️ (v2 variant) |
| kmer_build_longest_phrases4.py | 96 | 3 | ✅ (iterative) |
| kmer_extend_phrases1.py | 114 | 2 | ✅ (active) |
| kmer_extend_phrases2.py | 86 | 1 | ✅ (indexed) |
| kmer_extend_phrases3.py | 106 | 1 | ⚠️ (v2 + dedup) |
| kmer_consolidated_phrases1.py | 48 | 1 | ✅ (merge) |
| kmer_consolidated_phrases2.py | 42 | 2 | ✅ (prune) |
| kmer_connect_extendedphrase.py | 116 | 2 | ✅ (connectors) |
| kmer_enrich_w_verbatim.py | 57 | 1 | ✅ (verbatim) |
| **Total** | **974** | **19** | **8 unique** |

## Duplication Analysis

- **100% duplicated:** `is_sub_kmer()` in 5 files
- **85-95% similar:** `build_longest_phrases()` family (5 versions)
- **90% similar:** `extend_within_bins()` family (2 versions)
- **Different algorithms:** `consolidate_phrases()` strategies

**Total duplicate lines:** ~400 out of 974 (41%)

## Why Keep This Archive

1. **Historical Record:** Documents evolution of algorithmic thinking
2. **Algorithm Comparison:** Multiple approaches to same problem
3. **Future Reference:** May inform future phrase detection enhancements
4. **Educational Value:** Shows iterative refinement process
5. **Design Decisions:** Explains why current approach was chosen

## Current Production System

The production phrase detection system does NOT use these algorithms:

**Current Stack:**
```
utils/phrase_extraction.py
    ↓ (NLTK tokenization, lemmatization)
logic/phrase_extractor.py
    ↓ (recursive descent pattern matching)
utils/phrase_pruning.py
    ↓ (prune subphrases by various strategies)
```

**Exception:** `logic/phrase_builder.py` imports `kmer_extend_phrases1.py` for phrase merging.

## If You Need These Algorithms

**Don't use these archived files.** Use the consolidated version:

```python
from utils.kmer_legacy_algorithms import (
    is_sub_kmer,
    build_longest_phrases_iterative,      # Best version
    extend_within_bins_with_dedup,        # Best version
    consolidate_phrases_by_merging,       # Strategy 1
    consolidate_phrases_by_pruning,       # Strategy 2
    group_connectors,
    enrich_with_verbatim,
)
```

## Restoration

If you need to restore any original file:
1. Files are preserved exactly as archived
2. Use `git log` to see original commit history
3. Copy from this directory back to `utils/` if needed

## Related Documentation

- **Current phrase detection:** See `utils/phrase_extraction.py` docstrings
- **Recursive descent:** See `core/recursor.py` and `logic/phrase_extractor.py`
- **Project overview:** See `CLAUDE.md` section on phrase detection

---

**Archive maintained by:** Claude Code Assistant
**Consolidation reference:** `utils/kmer_legacy_algorithms.py`
**Active kmer code:** `utils/kmer_extend_phrases1.py` (not archived)
