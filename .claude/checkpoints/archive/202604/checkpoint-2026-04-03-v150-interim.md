# Checkpoint: v1.5.0 Interim — Scoped Stripping + Boilerplate + LLM Prompts

**Date**: 2026-04-03
**Package Version**: 1.5.0
**Branch**: main
**Parent Checkpoint**: checkpoint-2026-04-02-v101-consolidated.md
**Commits**: 71dbf61, a11d834, f49b270

---

## Summary

Three features implemented in a single session (2026-04-02):

1. **tinyId-scoped verbatim stripping** — bare instrument tags stripped only within their CDE set
2. **Boilerplate definition substitution** — LLM summaries replace 30 verbose definitions (88% reduction)
3. **YAML-driven LLM prompt registry** — new task types via config, no code needed

---

## 1. Scoped Verbatim Stripping (commit 71dbf61)

### Architecture
- `config_loader.py`: 3-tuple return `(pattern, replace_with, tinyIds)` + auto-propagation
- `_auto_propagate_bare_patterns()`: bracketed `[TAG]` with tinyIds → bare `TAG` with same scope
- Both `strip_phrases` and `strip_branching` consumers updated to pass tinyIds through

### Data
- 106 patterns with corpus-derived tinyIds in `verbatim_strip_patterns.yaml`
- 16 universal patterns unchanged (temporal, boilerplate)
- 58 bare forms auto-propagated → 185 total loaded

### Validation (MTSTPT)
- 22,207 identical, 536 more-stripped, 0 regressions, 0 false positives
- 3,196 chars removed (bare tags: LTVH 65, UPPS-P 57, BFI 44, CAST 43, etc.)

### Abbreviation Dictionary Export
- `export_scoped_verbatim_yaml()` method on AbbreviationDictionary
- `--export-scoped-yaml` CLI subcommand + pipeline mode auto-export

### Tests
- 23 new tests in `test_config_loader_scoped.py` (all pass)

---

## 2. Boilerplate Definition Substitution (work directory, not committed to repo)

### Problem
30 CDEs with 300–3,851 char definitions stuffed with licensing, provenance, scoring noise.

### Approach Comparison
| Method | Output | Removed |
|--------|-------:|--------:|
| Original | 29,933 chars | — |
| Regex sentence trimming | 22,897 chars | 24% |
| LLM summary v1 | 6,818 chars | 77% |
| **LLM summary v2** | **3,727 chars** | **88%** |

v2 tightened by removing item counts, response formats, subscale enumeration per user feedback.

### Implementation
- 30 substitute patterns in `phrase_curation3/phase2_output/boilerplate_substitutes.tsv`
- Pipeline script updated with Step 2b (boilerplate sub pass before branching strip)
- Validated: all 30 applied correctly, 23,051 definition chars removed across corpus

### Key Files (work directory)
- `phrase_curation3/reports/boilerplate_trim/llm_summaries_v2.tsv`
- `phrase_curation3/phase2_output/boilerplate_substitutes.tsv`
- `phrase_curation3/scripts/run_pipeline.sh` (Step 2b added)

---

## 3. YAML-Driven LLM Prompt Registry (commit f49b270)

### Architecture
```
config/llm_prompts.yaml → load_llm_prompts(task_type) → YamlPromptModule
```

- New tasks added by editing YAML only — no Python module needed
- `get_module()` falls back to YAML for task types not in hardcoded registry
- Existing modules (instrument, temporal, instrument_family, semantic_proxy) unchanged

### boilerplate_substitution Prompts
- INCLUDE: what is measured, who it is for, administration method
- EXCLUDE: item counts, response formats, subscale names, scoring, licensing,
  publisher info, developer credits, Working Group caveats
- Output: 1-2 sentences, plain medical English

### Tests
- 16 new tests in `test_llm_prompts.py` (all pass, 377 total suite)

---

## 4. Supporting Work

### Remnant Scan
- `scan_remnants.py`: systematic scan of MTSTPT for instrument fragments + verbose boilerplate
- 49 instruments detected, ~160 true hits after excluding false positives (SCARED, FVC, FEV1, BMI, ASSIST)
- 681 parenthetical abbreviations confirmed as legitimate domain terms

### Verbatim TinyId Collation
- `collate_verbatim_tinyids.py`: per-pattern reports for all 127 verbatim patterns
- Alphabetically stemmed directory hierarchy (35 dirs, max 15 files each)
- Scope review TSV: U/S pre-filled from YAML category

### Reports & Slides Updated
- Detailed report: Sections 9 (scoped stripping) + 10 (boilerplate substitution)
- Summary report: scoped stripping + boilerplate sections
- strip_qc_reveal.html: Round 5, 12 slides (split overfull slides 6 and 9)
- abbreviation_system_reveal.html: v1.4.0 roadmap items marked done

### Version Bump
- 1.0.1 → 1.5.0 across all 10 locations (commit a11d834)

### Consolidated Checkpoint
- `checkpoint-2026-04-02-v101-consolidated.md`: full history v0.3.0 through v1.4.0
- Previous checkpoint archived to `archive/`

---

## What Remains

1. **Rerun pipeline** — with scoped verbatim + boilerplate substitutes
2. **Embedding clustering evaluation** — re-extract embed CSVs
3. **Choose production curator** — GT vs consensus3m vs ML vs MD
4. **Production run + reference ledger update**
5. **API key setup** — for automated LLM-driven boilerplate substitution on new corpora
