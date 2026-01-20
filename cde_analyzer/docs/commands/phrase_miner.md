# phrase_miner Command

Advanced k-mer phrase mining with iterative descending detection.

## Overview

The `phrase_miner` action detects repeated multi-word phrases across CDE records using an iterative k-mer mining algorithm. It starts with the longest phrases (k=25) and works down to the shortest (k=3), masking detected phrases to prevent re-detection.

**Implementation Status**: Phase 1-3 complete (core k-mer mining)

## Usage

```bash
python cde_analyzer.py phrase_miner --input <file.json> [options]
```

## Arguments

### Required

| Argument | Description |
|----------|-------------|
| `--input`, `-i` | Input JSON file (list of CDE items) |

### Optional

| Argument | Default | Description |
|----------|---------|-------------|
| `--output-dir`, `-o` | `phrase_output` | Output directory for results |
| `--fields`, `-f` | `designation definition` | Field names to extract phrases from |
| `--k-max` | `25` | Maximum k-mer length |
| `--k-min` | `3` | Minimum k-mer length |
| `--freq-min` | `3` | Minimum frequency threshold per k-bin |
| `--min-tinyids` | `2` | Minimum distinct tinyIds (document support) |
| `--lemmatize` / `--no-lemmatize` | `True` | Apply lemmatization to tokens |
| `--remove-stopwords` | `False` | Remove English stopwords during tokenization |
| `--skip-debruijn` | `False` | Skip de Bruijn contig extension (Phase 5+) |
| `--skip-anchor` | `False` | Skip anchor-based extension (Phase 7+) |
| `--histograms` | `False` | Generate k-mer frequency histograms (not yet implemented) |

## Examples

### Basic Usage

```bash
# Run with defaults
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output
```

### Quick Test (Smaller k Range)

```bash
# Faster execution with k=10 to k=3
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --k-max 10 \
  --k-min 3
```

### Find More Phrases (Lower Thresholds)

```bash
# Lower frequency and support thresholds
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --freq-min 2 \
  --min-tinyids 2
```

### Multiple Fields

```bash
# Extract from all text fields
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --fields designation definition valueMeaningName valueMeaningDefinition
```

### Raw Tokens (No Lemmatization)

```bash
# Process exact text without lemmatization
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --no-lemmatize
```

### With Stopword Removal

```bash
# Remove common English stopwords
python cde_analyzer.py phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --remove-stopwords
```

## Output Files

### phrases.tsv

Metadata for each detected phrase.

| Column | Description |
|--------|-------------|
| `phrase_id` | Unique identifier (e.g., `phrase_00001`) |
| `text` | Human-readable phrase text |
| `k` | Original k-mer length |
| `frequency` | Total occurrence count |
| `n_tinyids` | Number of distinct CDE documents |
| `extension_method` | Detection method: `kmer`, `debruijn`, or `anchor` |

**Example**:
```tsv
phrase_id	text	k	frequency	n_tinyids	extension_method
phrase_00001	patient reported outcome	3	127	45	kmer
phrase_00002	adverse event severity	4	89	38	kmer
phrase_00003	clinical trial participant	3	76	32	kmer
```

### occurrences.tsv

Location of each phrase occurrence.

| Column | Description |
|--------|-------------|
| `phrase_id` | Reference to phrases.tsv |
| `tinyId` | CDE document identifier |
| `field_path` | Path to field (e.g., `designations[0].designation`) |
| `token_start` | Start token index |
| `token_end` | End token index |

**Example**:
```tsv
phrase_id	tinyId	field_path	token_start	token_end
phrase_00001	CDE123	designations[0].designation	5	8
phrase_00001	CDE456	definitions[0].definition	2	5
phrase_00002	CDE789	designations[1].designation	0	4
```

### extended.tsv (Future - Phase 7+)

Extended phrases with context-based boundary improvement.

| Column | Description |
|--------|-------------|
| `original_phrase_id` | Reference to original phrase |
| `extended_text` | Extended phrase text |
| `left_tokens` | Tokens added on left |
| `right_tokens` | Tokens added on right |
| `score` | Extension confidence score |

## Algorithm

### Iterative Descending K-mer Mining

1. **Extract & Tokenize**
   - Extract text from specified CDE fields
   - Tokenize using NLTK
   - Optionally lemmatize with POS tagging
   - Build vocabulary (token-to-ID mapping)

2. **Iterative Mining** (k=25 down to k=3)
   - Count k-mers in unmasked regions only
   - Filter by frequency threshold (`freq_min`)
   - Filter by document support (`min_tinyids`)
   - Convert passing k-mers to phrases

3. **Masking with Ownership Tracking**
   - Mark detected phrases to prevent re-detection
   - Track which phrase "owns" each token
   - Current: Naive O(n×m) pattern matching
   - Future: Aho-Corasick O(n+m) (Phase 4)

4. **Output Generation**
   - Write phrases.tsv with metadata
   - Write occurrences.tsv with locations

### Complexity

| Phase | Current | Future |
|-------|---------|--------|
| Tokenization | O(n) | O(n) |
| K-mer counting | O(n×k) | O(n×k) |
| Masking | O(n×m) naive | O(n+m) Aho-Corasick |
| Total | O(n×k×m) | O(n×k + n+m) |

Where:
- n = total tokens
- k = k_max - k_min (k-mer range)
- m = number of detected phrases

## Implementation Phases

### Completed (Phase 1-3)

- ✅ **Phase 1: Foundation** - Data structures, vocabulary class
- ✅ **Phase 2: Action Setup** - CLI, orchestration layer
- ✅ **Phase 3: Core Mining** - K-mer counting, basic masking

### Deferred (Phase 4-7)

- ⏸️ **Phase 4: Aho-Corasick** - O(n+m) multi-pattern matching
- ⏸️ **Phase 5: De Bruijn** - Graph-based phrase extension
- ⏸️ **Phase 6: Subsumption** - Remove phrases contained in longer ones
- ⏸️ **Phase 7: Anchor Extension** - Context-based boundary improvement

## Comparison with `phrase` Command

| Feature | `phrase` | `phrase_miner` |
|---------|----------|----------------|
| Algorithm | N-gram counting | Iterative k-mer mining |
| Detection order | Shortest first | Longest first |
| Overlap handling | None | Masking with ownership |
| Output format | JSON/CSV/TSV | TSV (phrases + occurrences) |
| Implementation | Original | NEW (Phase 1-3) |

## Related Commands

- [phrase](../help/phrase.md) - Original phrase detection
- [phrase_builder](../help/phrase_builder.md) - Incremental phrase construction
- [strip_phrases](../help/strip_phrases.md) - Remove detected phrases

## Technical Details

### Key Files

| File | Description |
|------|-------------|
| `actions/phrase_miner/cli.py` | Argument parsing (109 lines) |
| `actions/phrase_miner/run.py` | Orchestration layer (122 lines) |
| `logic/phrase_miner.py` | Core algorithm (334 lines) |
| `logic/phrase_anchor_extend.py` | Anchor extension placeholder (39 lines) |
| `utils/phrase_miner_vocab.py` | Vocabulary class (54 lines) |

### Data Structures

```python
@dataclass
class Phrase:
    phrase_id: str            # "phrase_00001", "phrase_00002", ...
    token_ids: Tuple[int, ...]
    text: str
    frequency: int
    distinct_tinyids: Set[str]
    k: int                    # Original k-mer length
    occurrences: List[CDERef]
    extension_method: str     # "kmer", "debruijn", "anchor"

@dataclass
class MinerConfig:
    k_max: int = 25
    k_min: int = 3
    freq_min: int = 3
    min_distinct_tinyids: int = 2
    field_names: List[str] = ["designation", "definition"]
    lemmatize: bool = True
    remove_stopwords: bool = False
```

## See Also

- [Architecture Overview](../architecture.md)
- [Data Models](../data-models.md)
- [Checkpoint: Phase 1-3 Implementation](../../.claude/checkpoints/checkpoint-20260113-phrase-miner-phase1-3.md)
