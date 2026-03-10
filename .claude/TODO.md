# Development TODO List

This file tracks development tasks and enhancements for future sessions.

## High Priority

### LLM Pipeline Integration
**Date Added**: 2026-01-26 | **Status**: Implemented but not integrated

`llm_classify` action exists (async providers: Claude, OpenAI, Gemini; query modules; confidence aggregation) but is not yet wired into workflow pipelines. Consider adding as optional post-gate classification step.

---

### Position-Specific Field-Aware Stripping
**Date Added**: 2026-01-29 | **Status**: Architecture ready

Architecture in `branching_stripper.py` supports position-specific stripping (e.g., strip only from definitions, not designations). Not yet exposed via CLI or workflow YAML.

---

## Medium Priority

### Embedding Evaluation on Branching Strip Outputs
**Date Added**: 2026-03-03

Run `extract_embed` on all 7 branching-strip variant outputs from allcde03 to evaluate downstream impact of different stripping configurations.

---

### Full Regression Test: Legacy vs N-way
**Date Added**: 2026-03-03

After phrase curation is complete, run both legacy (14-step) and N-way (3-step) branching strip on allcde03 and verify identical outputs.

---

### strip_branching Verbatim Patterns
**Date Added**: 2026-03-07

N-way engine (`strip_branching`) doesn't load verbatim patterns from `config/verbatim_strip_patterns.yaml` — only `strip_phrases` does. Consider adding `--verbatim-patterns` support to the N-way engine.

---

## Completed

*(Move completed items here with date)*

- 2026-01-28: TinyId loading with `file:column` format and multi-value parsing
- 2026-01-28: Split strip_discover into focused commands (v0.4.2)
- 2026-02-10: Field-specificity across tools (field_profile, field_analysis, --fields)
- 2026-02-12: Split temporal/curated strip pipeline
- 2026-02-26: Zipf priority split (supersedes phrase curation partitioning)
- 2026-03-07: Deferred parent filter + anchor trim control (phrase pipeline correctness)
- 2026-03-07: Iterative discovery with diagnostic reports (discovery_report action)
- 2026-03-09: Containment tree in TSV editor (semantic span hierarchy)
- 2026-03-09: 7th variant MTSTPF + allcde03 production run
- 2026-03-10: Curator briefing document
