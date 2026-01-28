# LLM-Assisted Classification

AI-powered phrase classification for intelligent data curation.

## Overview

The LLM Classification module extends CDE Analyzer with multi-provider AI capabilities for classifying phrases extracted by `phrase_miner`. Unlike other CDE Analyzer commands that operate locally, this module queries external LLM APIs (Claude, ChatGPT, Gemini) and aggregates their responses.

!!! info "External API Requirement"
    This module requires API keys for one or more LLM providers. See [Configuration](configuration.md) for setup instructions.

## Key Features

- **Multi-LLM Querying**: Query Claude, OpenAI, and Google Gemini in parallel
- **Result Aggregation**: Combine responses using configurable voting methods
- **Confidence Quintiles**: Rank classifications from highly_likely to highly_unlikely
- **Modular Query Types**: Extensible framework for different classification tasks
- **Batch Processing**: Efficient async processing with rate limiting

## Workflow Integration

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  phrase_miner   │────▶│  llm_classify   │────▶│  Human Curation │
│                 │     │                 │     │                 │
│  Extract        │     │  Classify with  │     │  Review high-   │
│  repeated       │     │  multiple LLMs  │     │  confidence     │
│  phrases        │     │  + aggregate    │     │  predictions    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

The `llm_classify` command takes output from `phrase_miner` and classifies each phrase using one or more LLM providers. Results are aggregated into confidence quintiles to prioritize human review.

## Available Query Modules

| Module | Categories | Purpose |
|--------|------------|---------|
| **instrument** | `instrument_name`, `possible_instrument`, `not_instrument` | Detect measurement instruments, medical devices, and assessment tools |
| **temporal** | `recency_window`, `age_range`, `time_point`, `duration`, `frequency`, `not_temporal` | Identify temporal patterns and time-related expressions |

See [Query Modules](query_modules.md) for detailed category definitions.

## Confidence Quintiles

Classifications are ranked into five confidence levels:

| Quintile | Score Range | Interpretation |
|----------|-------------|----------------|
| **highly_likely** | 81-100% | Strong agreement, high confidence |
| **likely** | 61-80% | Moderate agreement, likely correct |
| **indeterminate** | 41-60% | Mixed signals, needs review |
| **unlikely** | 21-40% | Weak support for classification |
| **highly_unlikely** | 0-20% | Low confidence, likely incorrect |

## Quick Start

### 1. Configure API Keys

Create `~/.cde_analyzer/llm_config.json`:

```json
{
  "claude": {
    "api_key": "sk-ant-...",
    "model": "claude-sonnet-4-20250514"
  },
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4o"
  }
}
```

Or set environment variables:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

### 2. Run phrase_miner

```bash
cde-analyzer phrase_miner \
  --input cdes.json \
  --output-dir phrase_output
```

### 3. Classify Phrases

```bash
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument \
  --providers claude openai
```

### 4. Review Results

```bash
# High-confidence instrument names
grep "highly_likely\|likely" llm_output/classified_instrument.tsv

# Check run statistics
cat llm_output/llm_run_log.json
```

## Documentation

| Page | Description |
|------|-------------|
| [llm_classify Command](llm_classify.md) | Complete command reference and examples |
| [Configuration](configuration.md) | API key setup and provider configuration |
| [Query Modules](query_modules.md) | Available classification modules and categories |

## Architecture

```
utils/llm/                    # LLM provider infrastructure
├── config.py                 # API key resolution (config → env → CLI)
├── provider_base.py          # Abstract LLM provider interface
├── provider_claude.py        # Anthropic Claude implementation
├── provider_openai.py        # OpenAI ChatGPT implementation
├── provider_google.py        # Google Gemini implementation
├── rate_limiter.py           # Token bucket rate limiting
└── result_aggregator.py      # Multi-LLM result aggregation

utils/query_modules/          # Classification modules
├── module_base.py            # Abstract query module interface
├── instrument_detector.py    # Instrument name detection
└── temporal_detector.py      # Temporal pattern detection

logic/llm_classifier.py       # Core orchestration
actions/llm_classify/         # CLI action
CDE_Schema/LLM_Classification.py  # Data models
```

## Comparison with Local Commands

| Aspect | Local Commands | LLM Classification |
|--------|----------------|-------------------|
| **Execution** | Local processing | External API calls |
| **Cost** | Free | API usage fees |
| **Speed** | Fast | Network-dependent |
| **Accuracy** | Rule-based | AI-assisted |
| **Configuration** | Minimal | API keys required |
| **Use Case** | Data transformation | Semantic classification |

## See Also

- [phrase_miner](../commands/phrase_miner.md) - Generate input for classification
- [Architecture](../architecture.md) - System design overview
