# llm_classify Command

Multi-LLM phrase classification with confidence aggregation.

## Overview

The `llm_classify` action classifies phrases from `phrase_miner` output using multiple LLM providers (Claude, OpenAI, Gemini). It aggregates responses into confidence quintiles to assist human curation of semantic categories.

**Primary Use Cases**:

- Identify instrument and device names in CDE definitions
- Detect temporal patterns (recency windows, age ranges, durations)
- Partition frequent phrases for semantic normalization
- Prioritize human review using confidence rankings

## Usage

```bash
cde-analyzer llm_classify --input-dir <phrase_output> --module <module_name> [options]
```

## Arguments

### Required

| Argument | Description |
|----------|-------------|
| `--input-dir`, `-i` | Directory containing phrase_miner output (phrases.tsv, etc.) |
| `--module`, `-m` | Query module: `instrument`, `temporal`, or `instrument_family` |

### Output Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--output-dir`, `-o` | `llm_output` | Output directory for classification results |
| `--original-cdes` | - | Path to original CDE JSON for full context retrieval |

### Provider Configuration

| Argument | Default | Description |
|----------|---------|-------------|
| `--providers` | `claude` | LLM providers to use: `claude`, `openai`, `google` |
| `--config-file` | `~/.cde_analyzer/llm_config.json` | Path to LLM configuration file |
| `--api-keys` | - | API keys as `provider:key` pairs (least preferred) |

### Aggregation Settings

| Argument | Default | Description |
|----------|---------|-------------|
| `--aggregation-method` | `majority` | How to combine multi-LLM results |

**Aggregation Methods**:

| Method | Description |
|--------|-------------|
| `unanimous` | Requires all LLMs to agree; falls back to majority if not |
| `majority` | Simple majority vote (most common category wins) |
| `weighted_majority` | Votes weighted by provider reliability scores |
| `confidence_weighted` | Votes weighted by individual confidence scores |

### Processing Parameters

| Argument | Default | Description |
|----------|---------|-------------|
| `--batch-size` | `20` | Phrases per LLM batch request |
| `--min-frequency` | `1` | Minimum phrase frequency to process |
| `--context-window` | `200` | Characters of context around each phrase occurrence |
| `--reference-file` | - | Reference data file for the module (e.g., known instruments) |

### Instrument Adjudication Mode

| Argument | Default | Description |
|----------|---------|-------------|
| `--adjudicate-instruments` | - | Path to instruments.tsv for family adjudication |
| `--adjudicate-threshold` | `0.7` | Adjudicate instruments with confidence below threshold |

### Validation Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--skip-validation` | `False` | Skip API key validation before processing |
| `--dry-run` | `False` | Validate configuration without making LLM calls |

## Examples

### Basic Instrument Detection

```bash
# Classify phrases as instrument names using Claude
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument
```

### Multi-LLM Classification

```bash
# Use Claude and OpenAI for higher confidence
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument \
  --providers claude openai \
  --aggregation-method weighted_majority
```

### Temporal Pattern Detection

```bash
# Detect time-related expressions
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module temporal \
  --providers claude openai google
```

### High-Frequency Phrases Only

```bash
# Focus on frequent phrases (faster, cheaper)
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument \
  --min-frequency 5 \
  --batch-size 50
```

### With Reference Data

```bash
# Use known instruments list to improve accuracy
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument \
  --reference-file known_instruments.tsv
```

### Dry Run (Validation Only)

```bash
# Check configuration without making API calls
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --providers claude openai \
  --dry-run
```

### Instrument Family Adjudication

```bash
# Adjudicate instruments with low family confidence
cde-analyzer llm_classify \
  --adjudicate-instruments instrument_output/instruments.tsv \
  --adjudicate-threshold 0.7 \
  --module instrument_family \
  --providers claude \
  --output-dir adjudicated_output
```

This reads instruments with `needs_review=True` or `family_confidence < 0.7` and submits them to the LLM for family classification.

## Output Files

### classified_[module].tsv

Main classification results.

| Column | Description |
|--------|-------------|
| `phrase_id` | Reference to phrases.tsv |
| `phrase_text` | Lemmatized phrase text |
| `category` | Assigned category (module-specific) |
| `quintile` | Confidence level: `highly_likely`, `likely`, `indeterminate`, `unlikely`, `highly_unlikely` |
| `confidence` | Aggregated score (0.000-1.000) |
| `agreement` | LLM agreement: `unanimous`, `majority`, `split` |
| `llm_votes` | Per-provider votes: `claude:instrument_name,openai:instrument_name` |
| `reasoning` | Combined LLM reasoning (truncated) |
| `verbatim_forms` | Pipe-separated original surface forms |
| `n_tinyids` | Number of distinct CDE documents |

**Example** (`classified_instrument.tsv`):
```tsv
phrase_id	phrase_text	category	quintile	confidence	agreement	llm_votes	reasoning	verbatim_forms	n_tinyids
phrase_00042	beck depression inventory	instrument_name	highly_likely	0.950	unanimous	claude:instrument_name,openai:instrument_name	[claude]: Well-known depression screening tool...	Beck Depression Inventory|beck depression inventory	23
phrase_00108	blood pressure	not_instrument	likely	0.720	majority	claude:not_instrument,openai:not_instrument	[claude]: Physiological measurement, not device...	Blood Pressure|blood pressure|BP	156
phrase_00215	imaging study	possible_instrument	indeterminate	0.480	split	claude:possible_instrument,openai:not_instrument	[claude]: Could refer to MRI, CT, etc...	imaging study|Imaging Study	12
```

### llm_run_log.json

Run statistics and metadata.

```json
{
  "run_id": "a1b2c3d4",
  "timestamp": "2025-01-24T10:30:00",
  "module": "instrument",
  "providers": ["claude", "openai"],
  "aggregation_method": "majority",
  "phrases_processed": 500,
  "total_api_calls": 1000,
  "tokens_used": {
    "claude": 125000,
    "openai": 118000
  },
  "processing_time_seconds": 245.3,
  "quintile_distribution": {
    "highly_likely": 45,
    "likely": 82,
    "indeterminate": 156,
    "unlikely": 127,
    "highly_unlikely": 90
  },
  "category_distribution": {
    "instrument_name": 127,
    "possible_instrument": 156,
    "not_instrument": 217
  },
  "error_count": 0,
  "errors": []
}
```

## Workflow Patterns

### Two-Phase Instrument Curation

```bash
# Phase 1: Extract instruments with phrase_miner
cde-analyzer phrase_miner \
  --input cdes.json \
  --output-dir phase1_output \
  --instruments-only

# Phase 2: Classify phrases with LLMs
cde-analyzer llm_classify \
  --input-dir phase1_output \
  --output-dir phase2_output \
  --module instrument \
  --providers claude openai

# Phase 3: Human review of high-confidence results
grep "highly_likely" phase2_output/classified_instrument.tsv > review_queue.tsv
```

### Progressive Classification

```bash
# Start with single provider for quick results
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir quick_results \
  --module instrument \
  --providers claude

# Add providers for uncertain cases
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir refined_results \
  --module instrument \
  --providers claude openai google \
  --aggregation-method confidence_weighted
```

### Temporal Pattern Analysis

```bash
# Identify all temporal expressions
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir temporal_output \
  --module temporal \
  --providers claude

# Filter by category
grep "recency_window" temporal_output/classified_temporal.tsv > recency_phrases.tsv
grep "age_range" temporal_output/classified_temporal.tsv > age_phrases.tsv
```

## Cost Estimation

API costs depend on:

- Number of phrases processed
- Average context length per phrase
- Number of providers used
- Provider pricing tiers

**Rough Estimates** (as of 2025):

| Scenario | Phrases | Providers | Est. Tokens | Est. Cost |
|----------|---------|-----------|-------------|-----------|
| Quick test | 100 | 1 (Claude) | 50K | ~$0.15 |
| Medium run | 500 | 2 | 500K | ~$1.50 |
| Full dataset | 2000 | 3 | 3M | ~$9.00 |

Use `--dry-run` to estimate phrase counts before committing to API calls.

## Error Handling

### Rate Limiting

The classifier includes automatic retry with exponential backoff:

- Retries up to 3 times on rate limit errors
- Waits 1s, 2s, 4s between retries
- Uses `retry_after` hints when provided

### Partial Failures

- Failed phrases are logged but don't stop processing
- Failed responses receive confidence=0.0
- Check `llm_run_log.json` for error details

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| "No valid LLM providers" | Missing or invalid API keys | Check configuration, run `--dry-run` |
| "Rate limit exceeded" | Too many requests | Reduce `--batch-size`, add delays |
| "Input directory not found" | Wrong path | Verify phrase_miner output exists |

## Technical Details

### Key Files

| File | Description |
|------|-------------|
| `actions/llm_classify/cli.py` | Argument parsing |
| `actions/llm_classify/run.py` | Orchestration and output |
| `logic/llm_classifier.py` | Core classification pipeline |
| `utils/llm/provider_base.py` | Abstract LLM provider interface |
| `utils/llm/provider_claude.py` | Claude API implementation |
| `utils/llm/provider_openai.py` | OpenAI API implementation |
| `utils/llm/provider_google.py` | Google Gemini implementation |
| `utils/llm/result_aggregator.py` | Multi-LLM aggregation |
| `utils/query_modules/module_base.py` | Query module interface |
| `utils/query_modules/instrument_detector.py` | Instrument detection |
| `utils/query_modules/temporal_detector.py` | Temporal pattern detection |
| `utils/query_modules/instrument_family_detector.py` | Instrument family adjudication |

### Data Flow

```
phrase_miner output          LLM Classification Pipeline
─────────────────           ──────────────────────────────

phrases.tsv ─────┐
                 │
verbatim_      ──┼──▶ Load Phrases ──▶ Build PhraseContext
phrases.tsv      │          │
                 │          ▼
occurrences.tsv ─┘    Query LLMs (parallel)
                            │
                      ┌─────┼─────┐
                      ▼     ▼     ▼
                   Claude OpenAI Gemini
                      │     │     │
                      └─────┼─────┘
                            ▼
                      Aggregate Results
                            │
                            ▼
                    Compute Quintiles
                            │
                      ┌─────┴─────┐
                      ▼           ▼
               classified_*.tsv  llm_run_log.json
```

### Provider-Specific Notes

**Claude (Anthropic)**:

- Uses `anthropic.AsyncAnthropic` client
- Default model: `claude-sonnet-4-20250514`
- Supports system prompts natively

**OpenAI (ChatGPT)**:

- Uses `openai.AsyncOpenAI` client
- Default model: `gpt-4o`
- JSON mode enabled via `response_format`

**Google (Gemini)**:

- Uses `google-generativeai` with async wrapper
- Default model: `gemini-1.5-pro`
- Concurrency limited to 5 parallel requests

## See Also

- [Configuration](configuration.md) - API key setup
- [Query Modules](query_modules.md) - Available classification modules
- [phrase_miner](../help/phrase_miner.md) - Generate input data
- [LLM Overview](index.md) - Module introduction
