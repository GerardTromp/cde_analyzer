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
| `--k-max` | `25` | Maximum k-mer length |
| `--k-min` | `3` | Minimum k-mer length |
| `--freq-min` | `3` | Minimum frequency threshold per k-bin |
| `--min-tinyids` | `2` | Minimum distinct tinyIds (document support) |
| `--lemmatize` / `--no-lemmatize` | `True` | Apply lemmatization to tokens |
| `--remove-stopwords` | `False` | Remove English stopwords during tokenization |
| `--enable-debruijn` | `False` | Enable de Bruijn graph extension (Phase 5) |
| `--enable-subsumption` | `False` | Enable subsumption filtering (Phase 6) |
| `--enable-anchor` | `False` | Enable anchor-based extension (Phase 7) |
| `--no-aho-corasick` | `False` | Use naive pattern matching instead of Aho-Corasick |
| `--verbatim-case-sensitive` | `False` | Use case-sensitive verbatim grouping |
| `--extract-instruments` | `False` | Extract 'as part of <Instrument>' patterns |
| `--instruments-only` | `False` | Phase 1: Extract instruments only, skip phrase mining |
| `--instrument-list` | - | Phase 2: TSV file with curated patterns to pre-mask |
| `--min-instrument-words` | `3` | Minimum words in instrument name |
| `--detect-families` | `False` | Enable instrument family detection |
| `--family-confidence-threshold` | `0.7` | Minimum confidence for family assignment |
| `--family-summary` | `False` | Generate instrument_families.tsv summary |
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

### Instrument Extraction (Two-Phase Workflow)

```bash
# Phase 1: Extract instruments only (for curation)
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir instrument_output \
  --instruments-only \
  --min-tinyids 1

# Curate instruments_verbatim.tsv (remove false positives)

# Phase 2: Full phrase mining with curated instrument pre-masking
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir phrase_output \
  --instrument-list instrument_output/instruments_verbatim.tsv \
  --min-tinyids 3
```

The `--instrument-list` argument accepts:
- `filename` - Uses the `full_match` column (default)
- `filename,column_name` - Uses the specified column

### Instrument Family Detection

```bash
# Extract instruments with family grouping
cde-analyzer phrase_miner \
  --input data/cde_records.json \
  --output-dir instrument_output \
  --instruments-only \
  --detect-families \
  --family-summary

# Output includes:
# - instruments.tsv with family_id, instrument_id columns
# - instruments_verbatim.tsv with family assignments
# - instrument_families.tsv summary (with --family-summary)
```

Family detection groups instruments into known families:
- **neuro-qol**: Neuro-QOL subscales
- **promis**: PROMIS instruments
- **mds-updrs**: MDS-UPDRS parts
- **sf-health**: SF-36, SF-12
- **beck**: Beck Depression/Anxiety Inventory
- **phq**: PHQ-9, PHQ-8, etc.
- **other**: Recognized instrument, unknown family

Instruments with `family_confidence < 0.7` are flagged with `needs_review=True` for optional LLM adjudication.

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

### instruments.tsv (with --instruments-only or --extract-instruments)

Summary of detected research instrument references.

| Column | Description |
|--------|-------------|
| `instrument_id` | Unique identifier (slug format with --detect-families) |
| `normalized_name` | Lowercase normalized name for grouping |
| `canonical_name` | Most common surface form |
| `acronym` | Extracted acronym(s) if present |
| `frequency` | Total occurrence count |
| `n_tinyids` | Number of distinct CDE documents |
| `tinyids` | Pipe-separated list of tinyIds |
| `family_id` | Family identifier (with --detect-families) |
| `family_display_name` | Human-readable family name (with --detect-families) |
| `family_confidence` | Confidence in family assignment 0.0-1.0 (with --detect-families) |
| `identification_method` | "pattern" or "llm" (with --detect-families) |
| `needs_review` | True if confidence < threshold (with --detect-families) |

### instrument_families.tsv (with --family-summary)

Summary statistics grouped by instrument family.

| Column | Description |
|--------|-------------|
| `family_id` | Family identifier (e.g., "neuro-qol") |
| `family_display_name` | Human-readable name (e.g., "Neuro-QOL") |
| `n_instruments` | Count of distinct instruments in family |
| `n_tinyids` | Total distinct CDE documents |
| `total_frequency` | Sum of all occurrences |
| `top_instruments` | Top 5 instrument names (pipe-separated) |
| `all_acronyms` | All acronyms in family (pipe-separated) |

### instruments_verbatim.tsv (with --instruments-only)

Detailed instrument variants for curation.

| Column | Description |
|--------|-------------|
| `normalized_name` | Normalized name for grouping |
| `acronym` | Extracted acronym if present |
| `verbatim_name` | Exact instrument name as found |
| `full_match` | Complete matched text (for --instrument-list) |
| `count` | Occurrence count |
| `n_tinyids` | Number of distinct documents |
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

- ✅ **Instrument Extraction** - Detect "as part of <Instrument> (<ACRONYM>)" patterns
- ✅ **Two-Phase Workflow** - Phase 1 extracts instruments, Phase 2 pre-masks curated list
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
- [Checkpoint: Phase 1-3 Implementation](../../.claude/checkpoints/checkpoint-20260113-phrase-miner-phase1-3.md)
