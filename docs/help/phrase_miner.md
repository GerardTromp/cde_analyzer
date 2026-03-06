# `phrase_miner` Command

Advanced k-mer phrase mining with iterative descending detection.

## Overview

The `phrase_miner` action detects repeated multi-word phrases across CDE records using an iterative k-mer mining algorithm. It starts with the longest phrases (k=25) and works down to the shortest (k=3), masking detected phrases to prevent re-detection.

**Implementation Status**: All phases complete (Phase 1-7 + enhancements)

## Usage

```bash
cde-analyzer phrase_miner --input <file.json> [options]
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
| `--k-max`, `-K` | `25` | Maximum k-mer length |
| `--k-min`, `-k` | `3` | Minimum k-mer length |
| `--freq-min`, `-n` | `3` | Minimum frequency threshold per k-bin |
| `--min-tinyids`, `-t` | `2` | Minimum distinct tinyIds (document support) |
| `--lemmatize` / `--no-lemmatize` | `True` | Apply lemmatization to tokens |
| `--remove-stopwords` | `False` | Remove English stopwords during tokenization |
| `--enable-debruijn`, `-D` | `False` | Enable de Bruijn graph extension (Phase 5) |
| `--enable-subsumption`, `-S` | `False` | Enable subsumption filtering (Phase 6) |
| `--enable-anchor` | `False` | Enable anchor-based extension (Phase 7) |
| `--no-aho-corasick` | `False` | Use naive pattern matching instead of Aho-Corasick |
| `--verbatim-case-sensitive` | `False` | Use case-sensitive verbatim grouping |
| `--skip-debruijn` | `False` | Skip de Bruijn contig extension (enabled by default) |
| `--skip-anchor` | `False` | Skip anchor-based extension |
| `--dedup` / `--no-dedup` | `True` | Enable/disable whole-text dedup pre-pass. Detects field texts shared by multiple CDEs, emits as phrases, then masks to prevent redundant k-mer detection |
| `--dedup-min-count N` | `2` | Minimum CDEs sharing identical text for dedup emission |
| `--dedup-min-tokens N` | `3` | Minimum tokens in dedup text to emit as phrase |
| `--analyze-phrase-families` | `False` | Analyze phrases for family groupings using prefix/suffix patterns. Outputs `phrase_families.tsv` and `phrase_family_members.tsv` |
| `--min-prefix-words N` | `2` | Minimum words for prefix pattern detection |
| `--min-suffix-words N` | `1` | Minimum words for suffix pattern detection |
| `--min-family-size N` | `3` | Minimum phrases to form a family |
| `--max-families N` | `100` | Maximum families to report |
| `--prefix-consolidation` / `--no-prefix-consolidation` | `True` | Extend high-frequency phrases by analyzing common right context in verbatim text |
| `--prefix-min-tinyids N` | `20` | Minimum tinyId coverage to attempt text extension |
| `--extension-min-pct F` | `0.5` | Minimum fraction of occurrences sharing a right-context extension |
| `--extension-max-words N` | `5` | Maximum words of right context to check for extensions |
| `--ledger-dir DIR` | - | Curation ledger directory. If provided, prior "remove" decisions are pre-masked during mining |
| `--histograms` | `False` | Generate k-mer frequency histograms |

## Examples

### Basic Usage

```bash
# Run with defaults
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output
```

### Quick Test (Smaller k Range)

```bash
# Faster execution with k=10 to k=3
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --k-max 10 \
  --k-min 3
```

### Find More Phrases (Lower Thresholds)

```bash
# Lower frequency and support thresholds
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --freq-min 2 \
  --min-tinyids 2
```

### Multiple Fields

```bash
# Extract from all text fields
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --fields designation definition valueMeaningName valueMeaningDefinition
```

### Raw Tokens (No Lemmatization)

```bash
# Process exact text without lemmatization
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --no-lemmatize
```

### With Stopword Removal

```bash
# Remove common English stopwords
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --remove-stopwords
```

### With Dedup and Ledger Pre-masking

```bash
# Mine with dedup and prior curation ledger
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --dedup \
  --ledger-dir .curation_ledger
```

### With Prefix Consolidation

```bash
# Mine with prefix consolidation (extends fragmented prefixes)
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --prefix-consolidation \
  --prefix-min-tinyids 20 \
  --extension-min-pct 0.5
```

### Phrase Family Analysis

```bash
# Analyze phrase groupings
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --analyze-phrase-families \
  --min-family-size 3
```

## Output Files

### phrases.tsv

Metadata for each detected phrase.

| Column | Description |
|--------|-------------|
| `phrase_id` | Unique identifier (e.g., `phrase_00001`) |
| `text` | Human-readable phrase text (lemmatized) |
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

Location of each phrase occurrence with verbatim text.

| Column | Description |
|--------|-------------|
| `phrase_id` | Reference to phrases.tsv |
| `tinyId` | CDE document identifier |
| `field_path` | Path to field (e.g., `designations[0].designation`) |
| `token_start` | Start token index |
| `token_end` | End token index |
| `verbatim_text` | Original surface text (pre-lemmatization) |

**Example**:
```tsv
phrase_id	tinyId	field_path	token_start	token_end	verbatim_text
phrase_00001	CDE123	designations[0].designation	5	8	Patient Reported Outcomes
phrase_00001	CDE456	definitions[0].definition	2	5	patient-reported outcome
phrase_00002	CDE789	designations[1].designation	0	4	Adverse Event Severity
```

### verbatim_phrases.tsv

Lemma-to-verbatim mappings showing all surface forms for each phrase.

| Column | Description |
|--------|-------------|
| `phrase_id` | Reference to phrases.tsv |
| `lemma_text` | Lemmatized phrase text |
| `verbatim_text` | Original surface form |
| `count` | Occurrence count for this verbatim form |
| `n_tinyids` | Number of distinct documents with this form |
| `tinyids` | Pipe-separated list of tinyIds |

### verbatim_variants.tsv

Token-level variants showing lemma-to-surface mappings.

| Column | Description |
|--------|-------------|
| `lemma` | Lemmatized token |
| `variant` | Surface form variant |
| `count` | Occurrence count |

### verbatim_templates.tsv

Structural templates extracted from verbatim variants.

| Column | Description |
|--------|-------------|
| `phrase_id` | Reference to phrases.tsv |
| `lemma_text` | Lemmatized phrase text |
| `n_variants` | Number of distinct verbatim forms |
| `core` | Longest common substring across all variants |
| `template_regex` | Full regex matching all variants |
| `prefix_slot` | Regex for prefix variations |
| `prefix_variants` | Pipe-separated prefix values |
| `suffix_slot` | Regex for suffix variations |
| `suffix_variants` | Pipe-separated suffix values |
| `infix1_slot` | Regex for first internal variation |
| `infix1_variants` | Pipe-separated infix1 values |
| `infix2_slot` | Regex for second internal variation |
| `infix2_variants` | Pipe-separated infix2 values |

Only phrases with 2+ distinct verbatim forms are included.

### extended.tsv (with --enable-anchor)

Extended phrases with context-based boundary improvement.

| Column | Description |
|--------|-------------|
| `original_phrase_id` | Reference to original phrase |
| `extended_text` | Extended phrase text |
| `left_tokens` | Tokens added on left |
| `right_tokens` | Tokens added on right |
| `score` | Extension confidence score |

### dedup_phrases.tsv (with --dedup)

Whole-text duplicates detected during the dedup pre-pass.

| Column | Description |
|--------|-------------|
| `text` | The duplicate field text |
| `n_tinyids` | Number of CDEs sharing this text |
| `tinyids` | Pipe-separated list of tinyIds |

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

### All Phases Complete

- ✅ **Phase 1: Foundation** - Data structures, vocabulary class
- ✅ **Phase 2: Action Setup** - CLI, orchestration layer
- ✅ **Phase 3: Core Mining** - K-mer counting, basic masking
- ✅ **Phase 3.5: Verbatim Recovery** - Position-based verbatim text extraction
- ✅ **Phase 4: Aho-Corasick** - O(n+m) multi-pattern matching
- ✅ **Phase 5: De Bruijn** - Graph-based phrase extension
- ✅ **Phase 6: Subsumption** - Remove phrases contained in longer ones
- ✅ **Phase 7: Anchor Extension** - Context-based boundary improvement

### Recent Enhancements

- ✅ **Whole-Text Dedup** - Pre-pass detects field texts shared across CDEs, emits as phrases, then masks
- ✅ **Prefix Consolidation** - Post-loop token-ID prefix trie recovers fragmented prefixes masked across k-levels
- ✅ **Ledger Pre-masking** - Prior "remove" decisions pre-masked during mining to reduce search space
- ✅ **Phrase Family Analysis** - Prefix/suffix-based family grouping
- ✅ **Verbatim Coalescing** - Case-insensitive grouping of verbatim forms
- ✅ **Verbatim Templates** - Regex pattern extraction from multi-form phrases
- ✅ **Unicode Normalization** - Expanded substitution table (156 entries)

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
| `actions/phrase_miner/cli.py` | Argument parsing |
| `actions/phrase_miner/run.py` | Orchestration and output generation |
| `logic/phrase_miner.py` | Core k-mer mining algorithm |
| `logic/phrase_anchor_extend.py` | Anchor-based phrase extension |
| `utils/phrase_miner_vocab.py` | Vocabulary class |
| `utils/verbatim_tracker.py` | Verbatim text recovery (PrefixTrie) |
| `utils/aho_corasick_token.py` | Token-based Aho-Corasick automaton |
| `utils/subsumption_filter.py` | Phrase subsumption filtering |
| `utils/debruijn_graph.py` | De Bruijn graph extension |
| `utils/verbatim_coalesce.py` | Case-insensitive verbatim grouping |
| `utils/verbatim_template.py` | Template extraction from verbatim variants |
| `utils/unicode.py` | Unicode normalization (156 substitutions) |
| `utils/instrument_extractor.py` | Instrument pattern detection |

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
- [phrase_miner Algorithm Documentation](../phrase_miner_logic.md)
