# `llm_classify` Command

Classify phrases using multi-LLM queries.

## Synopsis

```
cde-analyzer llm_classify -i <input_dir> -m <module> [options]
```

## Description

Agentic LLM-based classification for phrase curation. Uses multiple LLM providers (Claude, OpenAI, Gemini) to classify phrases from `phrase_miner` output into semantic categories.

## Options

### Required

```
-i, --input-dir DIR         Directory containing phrase_miner output files
-m, --module MODULE         Query module: instrument, temporal
```

### Output

```
-o, --output-dir DIR        Output directory (default: llm_output)
--original-cdes FILE        Original CDE JSON for full context retrieval
```

### Provider Configuration

```
--providers PROVIDERS       LLM providers: claude, openai, google (default: claude)
--config-file FILE          LLM config file (default: ~/.cde_analyzer/llm_config.json)
--api-keys KEYS             API keys as provider:key pairs (least preferred)
```

### Aggregation

```
--aggregation-method METHOD Method for combining results (default: majority)
                            Options: unanimous, majority, weighted_majority,
                                     confidence_weighted
```

### Processing

```
--batch-size N              Phrases per batch (default: 20)
--min-frequency N           Minimum phrase frequency (default: 1)
--context-window N          Context characters per occurrence (default: 200)
--reference-file FILE       Reference data for the module
```

### Validation

```
--skip-validation           Skip API key validation
--dry-run                   Validate config without LLM calls
```

## Examples

### Basic Usage

```bash
cde-analyzer llm_classify -i phrase_output -o llm_output -m instrument
```

### Multi-Provider

```bash
cde-analyzer llm_classify \
  -i phrase_output \
  -m instrument \
  --providers claude openai \
  --aggregation-method weighted_majority
```

### Temporal Detection

```bash
cde-analyzer llm_classify -i phrase_output -m temporal --providers claude
```

### Dry Run

```bash
cde-analyzer llm_classify -i phrase_output -m instrument --dry-run
```

## Output Files

- `classified_<module>.tsv` - Classification results with confidence quintiles
- `llm_run_log.json` - Run statistics and metadata

## See Also

- [Full Documentation](../llm/llm_classify.md)
- [Configuration Guide](../llm/configuration.md)
- [Query Modules](../llm/query_modules.md)
- [phrase_miner](phrase_miner.md)
