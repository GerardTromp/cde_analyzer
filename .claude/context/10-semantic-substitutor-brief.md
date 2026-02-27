# Semantic Substitutor: Investigation Brief

> **Purpose**: Standalone context for starting a new chat to investigate an alternative to phrase stripping.

## Problem Statement

Current approach strips long instrument/boilerplate phrases entirely from CDE text fields before embedding/clustering. This removes information that could help disambiguate CDEs. For example, "Patient Health Questionnaire-9 (PHQ-9)" is stripped, leaving no trace that the CDE relates to depression screening.

**Question**: Can we replace long phrases with short semantic proxies (1-3 words) that capture the essential meaning without causing CDEs to cluster by instrument?

## Current Stripping Pipeline

1. Mine phrases from CDE text (k-mer mining, instrument detection)
2. Discover verbatim occurrences across CDE records
3. Coalesce redundant patterns (subsumption filtering)
4. Enrich with field analysis (definition_count, designation_count, field_profile)
5. Curate (human review + automated filtering)
6. Strip phrases from text with `--clean-remnants` (removes orphan articles, floating punctuation)
7. Report remnants with `discovery_report`

**Result**: Clean text, but semantic information about instrument context is lost.

## Proposed Approach: Semantic Substitution

Instead of `strip_phrases`, create `substitute_phrases`:

1. For each curated pattern, use an LLM to generate a short semantic proxy:
   - Input: pattern text + sample CDE contexts (definitions, designations, possibly permissible values)
   - Output: 1-3 word replacement that captures the semantic role
   - Example: "Patient Health Questionnaire-9 (PHQ-9)" -> "depression-screen"
   - Example: "Unified Parkinson's Disease Rating Scale" -> "parkinson-motor"
   - Example: "as part of the Neuro-QOL Upper Extremity Function" -> "upper-limb-function"

2. Replace instead of strip:
   - "...administered as part of the Patient Health Questionnaire-9 (PHQ-9)..."
   - becomes "...administered depression-screen..."
   - With `--clean-remnants` to fix artifacts

3. Evaluate impact on downstream clustering:
   - Do CDEs with similar instruments still cluster together? (bad)
   - Does the proxy add useful semantic signal? (good)
   - Compare clustering quality: stripped vs substituted vs raw

## Key Design Questions

1. **Proxy generation**: One proxy per pattern, or context-dependent (different proxy depending on which CDE)?
2. **Field awareness**: Should proxies differ by field? Definition context may warrant different substitution than designation.
3. **Proxy vocabulary**: Free-form LLM output, or constrained to a controlled vocabulary?
4. **Evaluation metric**: How to measure "clustering quality" improvement? Need ground truth or domain expert evaluation.
5. **Granularity**: Replace at instrument family level (all PROMIS -> "patient-reported-outcome") or instrument level?

## Technical Implementation Sketch

### New files needed:
- `logic/semantic_substitutor.py` — core replacement logic
- `utils/query_modules/proxy_generator.py` — LLM query module for generating proxies
- `actions/substitute_phrases/cli.py`, `run.py` — CLI action

### Reusable infrastructure:
- `utils/llm/` — async LLM providers (Claude, OpenAI, Gemini) already implemented
- `utils/query_modules/` — modular query framework already exists
- `logic/remnant_detector.py` — `--clean-remnants` works with any text modification
- `utils/pattern_tsv_utils.py` — pattern loading

### Workflow:
```bash
# 1. Generate proxies (one-time, LLM-assisted)
cde-analyzer substitute_phrases --generate-proxies \
  --patterns curated.tsv -i cdes.json -m CDE \
  --provider claude --model claude-sonnet-4-20250514 \
  -o proxy_map.tsv

# 2. Review/edit proxy_map.tsv (human curation)

# 3. Apply substitutions
cde-analyzer substitute_phrases \
  -i cdes.json -m CDE -o substituted.json \
  --proxy-map proxy_map.tsv --clean-remnants

# 4. Compare clustering
cde-analyzer extract_embed -i substituted.json -o substituted_embed.json
# ... run clustering comparison
```

## Project Context

- **Codebase**: `cde_analyzer/` — Python CLI tool for NLM CDE analysis
- **Architecture**: Three-layer actions (`cli.py` -> `run.py` -> `logic/`), lazy loading
- **Entry point**: `cde_analyzer.py`
- **Data models**: Pydantic in `CDE_Schema/`
- **Fields of interest**: `definitions.*.definition`, `designations.*.designation`
- **Current dataset**: ~22,743 CDEs from NLM CDE repository
- **Branch**: `phrase-curator` (active development)
- **Python**: 3.13 via WSL Ubuntu-22.04

### Key existing files:
- `actions/strip_phrases/` — current stripping action (model for substitute_phrases)
- `logic/remnant_detector.py` — post-modification cleanup (reusable)
- `utils/llm/` — async LLM provider infrastructure
- `utils/query_modules/` — modular LLM query framework
- `utils/pattern_tsv_utils.py` — pattern file loading
- `logic/verbatim_discoverer.py` — `_extract_at_path()` for field traversal

### Running commands:
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```

## Success Criteria

1. Proxies are semantically meaningful (human review)
2. Substituted text reads naturally after `--clean-remnants`
3. Clustering with substituted text is at least as good as with stripped text
4. Bonus: clustering quality improves because semantic signal is preserved
