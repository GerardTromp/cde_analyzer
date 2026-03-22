# CDE Analyzer — Codebase Metrics Report

> **Generated**: 2026-03-16
> **Version**: v1.0.0
> **Tool**: Claude Code static analysis (no external linters)

## Size & Structure

| Metric | Value |
|--------|-------|
| **Python files** | 217 |
| **Total LOC** | 56,067 |
| **SLOC** (non-blank, non-comment) | 43,406 |
| **Comment/docstring lines** | ~5,900 (10.5%) |
| **Functions + Classes** | 1,351 |
| **HTML (editor/docs)** | 11,254 lines |
| **Action modules** | 20 action packages |

### LOC by Component

| Component | LOC | % |
|-----------|-----|---|
| actions/ | 20,471 | 36.5% |
| utils/ | 15,520 | 27.7% |
| logic/ | 8,731 | 15.6% |
| scripts/ | 8,056 | 14.4% |
| tests/ | 1,767 | 3.2% |
| CDE_Schema/ | 839 | 1.5% |
| tools/ | 189 | 0.3% |

### Largest Files

| File | LOC |
|------|-----|
| `actions/workflow/run.py` | 2,324 |
| `utils/flexible_pattern_matcher.py` | 1,910 |
| `actions/curation/run.py` | 1,414 |
| `actions/pattern_util/run.py` | 1,249 |
| `actions/instrument_util/run.py` | 1,210 |
| `logic/phrase_miner.py` | 1,195 |
| `actions/recall_analyze/run.py` | 1,081 |
| `scripts/generate_health_neuro.py` | 1,049 |
| `utils/instrument_extractor.py` | 1,014 |
| `actions/strip_discover/run.py` | 939 |

## Complexity (Branch-Count Proxy)

Top files by branching statements (`if`/`elif`/`for`/`while`/`try`/`except`):

| File | Branches | LOC | Ratio |
|------|----------|-----|-------|
| `utils/flexible_pattern_matcher.py` | 260 | 1,910 | 13.6% |
| `actions/workflow/run.py` | 254 | 2,324 | 10.9% |
| `actions/pattern_util/run.py` | 201 | 1,249 | 16.1% |
| `logic/phrase_miner.py` | 166 | 1,195 | 13.9% |
| `actions/supplementary/run.py` | 159 | 913 | **17.4%** |

Average: ~41 SLOC/function — moderate granularity.

## Maintainability Assessment

| Factor | Rating | Notes |
|--------|--------|-------|
| **Estimated MI** | **55–65** (moderate) | High SLOC per file in top modules drags score down; clean 3-layer architecture helps |
| **Avg cyclomatic complexity** | **~8–12** per function (estimated) | Top files hit 15+ in orchestration functions |
| **Comment ratio** | 10.5% | Adequate but not heavy |
| **Modularity** | Good | Clean `cli.py` → `run.py` → `logic/` separation across 20 actions |

## Test Coverage

| Metric | Value |
|--------|-------|
| **Test files** | 8 |
| **Test LOC** | 1,767 |
| **Test-to-code ratio** | **1:30** (3.2%) |
| **Estimated coverage** | **Low** — focused on specific logic (ledger, field-aware splits, instrument extraction, remnants) |

### Test Inventory

| Test File | Target |
|-----------|--------|
| `test_curation_ledger.py` | `logic/curation_ledger.py` |
| `test_field_aware_splits.py` | Field-aware instrument split logic |
| `test_helpers.py` | Shared test utilities |
| `test_instrument_extractor.py` | `utils/instrument_extractor.py` |
| `test_remnant_detector.py` | Remnant detection logic |
| `test_smart_strip_order.py` | Strip ordering logic |
| `test_verbatim_coalesce.py` | Verbatim pattern coalescence |
| `test_verbatim_template.py` | Verbatim template expansion |

**Coverage gap**: Core orchestration (`workflow/run.py`, `pattern_util/run.py`) and the coalescer (`flexible_pattern_matcher.py`) have no dedicated tests.

## Code Churn

| Metric | Value |
|--------|-------|
| **Total commits** | 167 (over 12 months) |
| **Total insertions** | 3.8M |
| **Total deletions** | 3.7M |
| **Net lines** | ~150K |
| **Churn ratio** | ~68× current LOC |

High churn-to-size ratio reflects heavy iteration — data files checked in/out and significant refactoring (action splits, legacy-to-nway migration).

### Most Volatile Files (by commit frequency)

| Commits | File |
|---------|------|
| 21 | `__version__.py` |
| 19 | `cde_analyzer.py` |
| 17 | `actions/pattern_util/cli.py` |
| 16 | `actions/pattern_util/run.py` |
| 15 | `actions/strip_phrases/cli.py` |
| 13 | `logic/extract_embed.py` |
| 13 | `actions/strip_phrases/run.py` |
| 13 | `actions/phrase_miner/cli.py` |
| 11 | `utils/flexible_pattern_matcher.py` |
| 11 | `logic/phrase_stripper.py` |

## Code Duplication

Not measured with a dedicated clone-detection tool (e.g., `jscpd`, `pylint`). Structural observations:

- **6 synthetic generator scripts** (8,056 LOC total) share significant injection logic — prime duplication candidates for refactoring into a shared module
- **`cli.py` boilerplate**: 20 action packages each follow a ~30-line registration pattern (`__init__`, `register`, `add_args`)
- **Legacy k-mer code**: `utils/legacy_kmer/` (11 files) preserved alongside current `logic/` — potential dead code

## Defect Density

No formal bug tracker. Git log shows ~5 fix-tagged commits out of 167 — approximately **0.5 bugs/KLOC** (likely understated; many fixes are bundled into feature commits).

## Summary Risk Profile

| Area | Risk | Action |
|------|------|--------|
| **Test coverage** | **High** | Core orchestration and coalescer untested |
| **Top-file complexity** | Medium | 5 files >150 branches; consider extracting helpers |
| **Script duplication** | Medium | 6 generators share injection logic; refactor to shared module |
| **Churn concentration** | Low | Hotspots align with active development areas |
| **Architecture** | Low | Clean layered design with lazy loading |
