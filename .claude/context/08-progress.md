# Progress and Current State

## Current Branch: main

**Focus**: Post-convergence QC fixes, CDE construction recommendations

**Version**: 1.5.1 (2026-04-03)

## Current State (v1.5.1)

### v1.5.1: REGEX Fix + ? Cleanup + New Verbatim Patterns (2026-04-03)

**Bug Fixes**:
- REGEX prefix parsing: `phrase[6:]` → `phrase[6:].lstrip()` in branching_stripper + phrase_stripper (PROMIS 35→2)
- `?` separator remnant cleanup: added `?` to leading punctuation in remnant_detector (201→0)
- NOS-TBI spacing variant: `(NOS - TBI)` added to verbatim patterns (34→0)

**New Verbatim Patterns** (192→199):
- GOS-E Peds (17→0), QOLIBRI-OS (16→0), ADAPTABLE (7→0)
- Likert scale regex in definitions (45→0)
- (STOP) prefix (11 CDEs), CAMPHOR (7), (FFQ)/(FFQ)- (24), CHAT screening suffix (15)

**R7 Pipeline Verified**: 22,743 CDEs × 7 variants, 199 verbatim patterns, leakage 335→~257

**CDE Construction Recommendations** expanded to 19 items:
- §12: Undefined abbreviations in Names (162 abbrevs, 899 CDEs)
- §13: References/URLs in definitions (37 CDEs)
- §14: Noise phrases (Question N, 30D shorthand, CDE bundling opportunities)
- Scope-variant near-duplicate analysis: 288 groups / 798 CDEs (3.5%)
- Verbose definition LLM candidates: 210 remaining >300 chars

### v1.5.0: Scoped Stripping + Boilerplate Substitution + LLM Prompts (2026-04-02)

**tinyId-Scoped Verbatim Stripping**:
- `verbatim_strip_patterns.yaml` gains optional `tinyIds` field; 106 patterns scoped
- Auto-propagation: bracketed `[TAG]` → bare `TAG` with same tinyId scope
- 127 YAML entries → 185 loaded (58 auto-propagated bare forms)
- Validation: 536 CDEs additionally stripped, 0 regressions, 0 false positives

**Boilerplate Definition Substitution**:
- 30 verbose definitions (300–3,851 chars) replaced by LLM-generated plain-language summaries
- 29,933 → 3,727 chars (88% reduction); regex-only achieved 24%
- Substitute TSV applied as pre-pass before branching strip

**YAML-Driven LLM Prompt Registry**:
- `config/llm_prompts.yaml`: per-task prompt templates (system + user)
- `YamlPromptModule`: loads from YAML, no Python module needed for new tasks
- `get_module()` falls back to YAML for tasks not in hardcoded registry
- `boilerplate_substitution` task: instructs LLM to keep what is measured, exclude how/licensing/scoring

**Abbreviation Disambiguation** (v1.1–v1.4 feature iterations):
- Three-tier resolution: internal expansion, external lookup, adjudication dictionary
- Acronym-alignment heuristic, permanent skip list, k-fold re-evaluation
- `--export-scoped-yaml`: generates scoped YAML from abbreviation dictionary

**v1.0.1 changes** (2026-03-13):
- Decision terminology: keep→strip, remove→skip (backwards compat)
- Instrument leakage scan in `strip_report`; 297 tests (+132%)

**v1.0.0 changes** (2026-03-12):
- `pattern_util` split into focused actions: `curation`, `instrument_util`, `pattern_diag`, `supplementary`
- Config-driven pipeline scaffold (`workflow scaffold --from-config`)
- Reference curation ledger shipped at `data/reference_ledger/`
- Development Status upgraded to Production/Stable

### All Pipeline Phases — Complete

**Phase 1: Instrument Pipeline** — 1,342 raw → 591 coalesced → 458 validated patterns → field-aware splits (383 full + 252 sub)
**Phase 2: Phrase Pipeline** — 4,023 patterns curated (171 strip, 3,743 skip, 102 modify, 7 substitute)
**Phase 3: Branching Strip** — 7 variant outputs; N-way 3-step single-pass with field-aware splits (all 7 distinct)

### Curation Infrastructure — Complete

- **5 decision types**: strip, skip, modify, substitute, followup
- **Containment tree** (v0.9.5): prefix+tinyId hierarchy for curation efficiency
- **Multi-curator workflow** (v0.6.0): init/merge with inter-rater stats
- **Standalone TSV editor** (v0.7.0): zipapp distribution (`cde_editor.pyz`, ~59 KB)
- **Centralized curation server** (v0.7.0): HMAC token auth, TLS, rate limiting
- **Incremental curation ledger** (v0.8.0): auto-resolve from prior decisions, gate/finalize
- **Zipf priority split** (v0.9.0): triage needs_review by word frequency
- **Reference ledger** (v1.0.0): `data/reference_ledger/` — bootstrap new projects

### Production Tooling — Complete

- **N-way branching strip** (v0.9.2): `strip_branching` — single-pass engine, all 7 variants
- **Field-aware splits** (v0.9.8): genuinely independent inst_full/inst_sub text spans
- **Strip configurator** (v0.9.1): `workflow configure CODE [-o FILE] [--nway]`
- **Config-driven scaffold** (v1.0.0): `workflow scaffold --from-config pipeline_config.yaml`
- **Documentation**: 8 vignettes, 28 help files, 4 cheatsheets, MkDocs site

## Recent Versions

| Version | Date | Summary |
|---------|------|---------|
| 1.5.1 | 2026-04-03 | REGEX fix, ? cleanup, 7 new verbatim patterns, CDE construction recommendations (19 items) |
| 1.5.0 | 2026-04-02 | Scoped stripping, boilerplate substitution, LLM prompt registry, abbreviation v1.1–v1.4 |
| 1.0.1 | 2026-03-13 | Decision rename (keep→strip, remove→skip), leakage scan, 297 tests |
| 1.0.0 | 2026-03-12 | Production release: action split, config scaffold, reference ledger |
| 0.9.8 | 2026-03-11 | Field-aware splits, 7-way branching strip, group-scoped re-matching |
| 0.9.6 | 2026-03-09 | 5-way branching strip, allcde03 production run (104s), curator briefing |
| 0.9.5 | 2026-03-09 | Containment tree view in TSV editor (prefix+tinyId hierarchy) |
| 0.9.4 | 2026-03-07 | Deferred parent filter, anchor trim control, followup decision, doc audit |
| 0.9.2 | 2026-03-03 | N-way single-pass branching strip engine, tinyid_count column |
| 0.9.1 | 2026-03-03 | Production strip configurator, --only-steps |
| 0.9.0 | 2026-02-26 | Zipf priority split, editor UX, version sync |
| 0.8.0 | 2026-02-24 | Incremental curation with ledger and gate |
| 0.7.0 | 2026-02-23 | Standalone editor zipapp, centralized server, synthetic QC |
| 0.6.0 | 2026-02-21 | Multi-curator, workflow scaffold, 7 vignettes |

## Post-v1.0.0 Work (2026-03-17 — 2026-03-24)

### Inter-Rater Agreement Analysis (4 curators)
- **4-curator merge**: GT, MD, MLEACH, BP2 — 1,331 patterns, Krippendorff's α = 0.039
- **Collapsed agreement** (modify/substitute → strip): 405 unanimous (30.7%), 510 majority
- **Stratified analysis**: High-frequency patterns (201+ CDEs) have best agreement; mid-range (11-200) concentrates disagreement
- **Containment tree analysis**: 37.4% of disagreements involve framing/functional language ("whether", "participant/subject")
- **Cluster consequence study**: GT achieves 86% cluster stability (best); MD matches baseline at 57% (over-stripping = no stripping)
- **Key finding**: "subject/participant" framing carries 1st vs 3rd person structure useful for clustering; domain noun phrases should be retained

### Per-Curator Stripping Comparison
- **7 strip variants**: Baseline (MTSTPF), Consensus, ConsMaj, GT, BP2, MLEACH, MD
- **Noise analysis**: GT on cm embedding is the only net-negative noise variant (-35); 90% of CDEs lost to noise retained 70%+ text
- **Cluster splits/joins**: GT#28 (fatigue) splits cleanly by intensity vs frequency in MD; 6/14 large clusters immune to curation differences

### Verbatim Strip Pattern Updates
- **[PROMIS] tag**: 41 CDEs with bracketed `[PROMIS]`/`[PROMIS.PEDS]` tags
- **PROMIS regex**: `PROMIS\s+.*?v\d+[\d.]*\s+\S+` for instrument prefix with form/version/item code (31 CDEs)
- **Repository typos**: "Information Measurement" transposition (2 CDEs), "Patient- Reported" spurious hyphen-space (1 CDE)

### Oracle Strip for Synthetic Data
- `scripts/oracle_strip_synthetic.py`: Reverses known injections per-dataset using manifest metadata
- Combined oracle-stripped JSON (900 CDEs) for embedding comparison

### Codebase Quality Improvements
- **Test coverage**: 128 → 297 tests (+132%), test-to-code ratio 1:30 → 1:15
  - New: `test_phrase_miner.py` (41 tests), `test_flexible_pattern_matcher.py` (68 tests), `test_workflow_engine.py` (60 tests)
  - Fixed 4 failing tests, removed stale `test_smart_strip_order.py`
- **Shared utilities**: `scripts/synthetic_common.py` (injection engine, CLI scaffold, manifest builder)
- **`parse_tinyid_set()`**: Added to `pattern_tsv_utils.py` — consolidates 27 duplicate parsing patterns
- **.gitignore**: Fixed overly broad `test*` pattern that excluded all test files
- **Codebase metrics report**: `docs/codebase-metrics-report.md`

### Embedding Feature Selection (New Codebase)
- **`clone_git/embedding_feature_selection/`**: Sibling repo for identifying boilerplate-encoding vs signal-carrying embedding dimensions
- Two orthogonal lenses: curator stripping (real data, no ground truth) + synthetic injection (controlled, known ground truth)
- **Finding**: minilm (384 dims) provides best clustering anecdotally — smallest model may naturally filter boilerplate

## What Remains

- **Rerun pipeline** — with scoped verbatim patterns + boilerplate substitutes
- **Embedding clustering evaluation** — re-extract embed CSVs from scoped/substituted output
- **Choose production curator** — GT vs consensus3m vs ML vs MD
- **Production run + reference ledger update**
- **API key setup** — for automated LLM-driven boilerplate substitution on new corpora
- **Position-specific field-aware stripping** — architecture ready in branching_stripper
- **tinyId parsing migration** — 27 call sites → `parse_tinyid_set()` (gradual)
- **Complexity reduction** — top 5 files, ~40-50 helper extractions possible (gradual)
