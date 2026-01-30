# CDE Analyzer CLI Reference

Quick reference for all CDE Analyzer commands. For detailed documentation, see the individual command pages.

> **Note**: Command names use **hyphens** on the command line (e.g., `phrase-miner`, `strip-html`) but **underscores** in Python module names. Both forms work with argparse, but hyphens are the conventional CLI style.

---

## Launcher

The `cde-analyzer` command is a launcher that dispatches to individual commands. It does not perform any analysis itself.

```bash
# List all available commands
cde-analyzer --help

# Get help for a specific command
cde-analyzer <command> --help
```

---

## Phrase Detection

### `phrase_miner` Command

Advanced k-mer phrase mining with iterative detection and masking.

```bash
usage: phrase_miner [-h] --input INPUT [--output-dir OUTPUT_DIR]
                    [--fields FIELDS [FIELDS ...]] [--k-max K_MAX] [--k-min K_MIN]
                    [--freq-min FREQ_MIN] [--min-tinyids MIN_TINYIDS]
                    [--lemmatize | --no-lemmatize] [--remove-stopwords]
                    [--enable-debruijn] [--enable-subsumption] [--enable-anchor]
                    [--extract-instruments] [--instrument-list FILE]
                    [--detect-families] [--family-confidence-threshold N]
                    [--family-summary]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input JSON file (list of CDE items)
  --output-dir, -o DIR  Output directory for results (default: phrase_output)
  --fields, -f FIELDS   Field names to extract (default: designation definition)
  --k-max K_MAX         Maximum k-mer length (default: 25)
  --k-min K_MIN         Minimum k-mer length (default: 3)
  --freq-min FREQ_MIN   Minimum frequency threshold (default: 3)
  --min-tinyids N       Minimum distinct tinyIds (default: 2)
  --lemmatize           Apply lemmatization (default: True)
  --remove-stopwords    Remove English stopwords
  --enable-debruijn     Enable de Bruijn graph extension
  --enable-subsumption  Enable subsumption filtering
  --enable-anchor       Enable anchor-based phrase extension
  --extract-instruments Extract 'as part of <Instrument>' patterns
  --instrument-list F   TSV file with curated instrument patterns
  --detect-families     Enable instrument family detection
  --family-confidence-threshold N
                        Min confidence for family assignment (default: 0.7)
  --family-summary      Generate instrument_families.tsv summary
```

---

### `phrase` Command

Original phrase detection using n-gram counting.

```bash
usage: phrase [-h] --input INPUT --fields FIELDS [FIELDS ...]
              [--min-words N] [--min-ids N] [--remove-stopwords]
              [--lemmatize | --no-lemmatize] [--prune-subphrases]
              [--output-format {json,csv,tsv}] [--output OUTPUT] [--verbatim]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file
  --fields FIELDS       Field names from pydantic classes
  --min-words N         Minimum phrase length (discard shorter)
  --min-ids N           Minimum objects sharing a phrase
  --remove-stopwords    Remove common English stop words
  --lemmatize           Convert text to lemma form (default: True)
  --prune-subphrases    Collect longest shared phrases only
  --output-format FMT   Output format: json, csv, tsv
  --output OUTPUT       Path to store results
  --verbatim            Include verbatim phrases
```

---

### `phrase_builder` Command

K-mer analysis for phrase identification with frequency visualization.

```bash
usage: phrase_builder [-h] -i INPUT -m MODEL -o OUTPUT

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to input JSON file
  -m, --model MODEL     Pydantic model name (e.g., CDE, Form)
  -o, --output OUTPUT   Output path prefix (timestamp appended)
```

---

### `strip_phrases` Command

Remove curated phrases from specific paths in CDE documents.

```bash
usage: strip_phrases [-h] -i INPUT -m MODEL -o OUTPUT
                     {-p PATTERNS | --phrases FILE}
                     [-f FIELDS ...] [--sort-order {length,file,alpha}]
                     [-w WORKERS] [--detect-remnants] [--remnant-report FILE]
                     [--clean-remnants] [--trace-matching FILE]
                     [-d] [--diff-output FILE] [-c] [--summary] [-C N]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to input JSON file
  -m, --model MODEL     Pydantic model (CDE, Form)
  -o, --output OUTPUT   Path to output JSON file
  -p, --patterns FILE   Discovered patterns TSV (from strip_discover)
  --phrases FILE        Legacy phrase map (JSON, CSV, or TSV)
  -f, --fields FIELDS   Field paths to strip (default: definitions, designations)
  --sort-order ORDER    Pattern order: length, file, alpha (default: length)
  -w, --workers N       Parallel workers (0=auto, 1=sequential, N=exact)
  --detect-remnants     Scan output for post-strip artifacts
  --remnant-report FILE Write remnant report TSV
  --clean-remnants      Apply iterative cleanup to fix artifacts
  --trace-matching FILE Write pattern matching trace TSV
  -d, --diff            Show diff between original and cleaned JSON
  --diff-output FILE    Write diff information to a file
  -c, --color           Colorize diff output
  --summary             Show summary of changed lines
  -C, --context N       Number of context lines (default: 3)
```

---

### `strip_analyze` Command

Pattern conflict and false-negative analysis.

```bash
usage: strip_analyze [-h] [-i INPUT] [-o OUTPUT] [-p PATTERN_LIST]
                     [--analyze-conflicts FILE] [--sort-order {length,file,alpha}]
                     [--analyze-false-negatives] [--fn-anchor STRING]
                     [--expand-variants] [--include-name-only]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Cleaned JSON for false-negative analysis
  -o, --output OUTPUT   Output TSV file
  -p, --pattern-list    Pattern TSV for conflict analysis
  --analyze-conflicts F Output file for conflict report
  --sort-order ORDER    Pattern order: length, file, alpha (default: length)
  --analyze-false-negatives
                        Analyze remaining anchor patterns
  --fn-anchor STRING    Anchor phrase (default: "as part of")
  --expand-variants     Generate variants for conflict analysis
  --include-name-only   Include bare names (default: True)
```

---

### `pattern_util` Command

TSV pattern utilities (merge, coalesce, field analysis, import).

```bash
usage: pattern_util [-h] [-o OUTPUT]
                    [--merge-patterns FILE] [--merge-pattern-column COL]
                    [--merge-tinyids-column COL]
                    [--coalesce-variants FILE] [--coalesce-report FILE]
                    [--min-prefix-tinyids N] [--min-parent-tinyids N]
                    [--no-trim-anchors] [--rollup-subset-tinyids]
                    [--emit-def-variants] [--split-tiers MIN_TOKENS]
                    [--field-analysis FILE] [-i INPUT] [-m MODEL]
                    [--fields FIELDS ...] [--min-field-count N]
                    [--min-tokens N] [--exclude-patterns FILE]
                    [--group-hierarchy FILE] [--min-tinyids N]
                    [--group-semantic FILE] [--min-group-size N]
                    [--generate-strip-patterns FILE]
                    [--add-to-supplementary FILE] [--supplementary-section NAME]

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output TSV file (required for most modes)
  --merge-patterns FILE Merge duplicate patterns, combine tinyIds
  --coalesce-variants FILE
                        Remove subsumed patterns (tinyId-aware)
  --coalesce-report FILE
                        Write subsumption report
  --min-prefix-tinyids N
                        Enable prefix extraction (0 = disabled)
  --min-parent-tinyids N
                        Filter by parent phrase tinyId count (0 = disabled)
  --no-trim-anchors     Disable anchor trimming during coalesce
  --rollup-subset-tinyids
                        Enable tinyId-subset rollup
  --emit-def-variants   Emit definition-form variants
  --split-tiers N       Split output by token count threshold
  --field-analysis FILE Enrich patterns with per-field counts
  -i, --input FILE      CDE JSON for field analysis
  -m, --model MODEL     Model for JSON parsing (default: CDE)
  --min-field-count N   Filter patterns below N in both fields
  --min-tokens N        Filter patterns with fewer than N tokens
  --exclude-patterns FILE
                        Remove patterns matching exclusion file
  --group-hierarchy FILE
                        Assign group/sub_group labels by prefix
  --group-semantic FILE Semantic grouping with POS boundary detection
  --generate-strip-patterns FILE
                        Generate strip-ready files from hierarchy
  --add-to-supplementary FILE
                        Import patterns to supplementary_patterns.yaml
```

---

## Analysis

### `count` Command

Count structural elements and field occurrences.

```bash
usage: count [-h] --input INPUT --fields FIELDS [FIELDS ...]
             [--match-type {non_null,null,fixed,regex}] [--value VALUE]
             [--output-format {json,csv,tsv}] [--output OUTPUT]
             [--group-by PATH] [--group-type {top,path,terminal}]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file
  --fields FIELDS       Fields to count
  --match-type TYPE     Match type: non_null, null, fixed, regex
  --value VALUE         Value to match (for fixed or regex)
  --output-format FMT   Output format: json, csv, tsv
  --output OUTPUT       Path to store results
  --group-by PATH       Dotted path to group by (e.g., tinyId)
  --group-type TYPE     Interpret as: top, path, terminal
  --logic EXPR          Logical expression (e.g., 'A and not B')
  --count-type          Classify values by type (int, float, strN)
  --output-flat         Flatten nested result keys
```

---

## Data Cleaning

### `strip_html` Command

Remove HTML markup from CDE fields.

```bash
usage: strip_html [-h] --input INPUT --output OUTPUT -m MODEL
                  [--outdir OUTDIR] [--format {json,yaml,csv}] [--dry-run]
                  [--pretty | --no-pretty] [--tables | --no-tables]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file (with underscore tags fixed)
  --output OUTPUT       Path to store results
  -m, --model MODEL     Model for validation: CDE, Form
  --outdir OUTDIR       Directory for output files
  --format FMT          Output format: json, yaml, csv
  --dry-run             Do not write output files
  --pretty              Pretty print JSON (default: True)
  --tables              Convert HTML tables to JSON (default: True)
  --colnames            Use first row as column names
```

---

### `fix_underscores` Command

Fix Pydantic-incompatible field names (underscore prefix).

```bash
usage: fix_underscores [-h] --input INPUT --output OUTPUT
                       [--prefix PREFIX] [--depth DEPTH]

options:
  -h, --help       show this help message and exit
  --input INPUT    Input JSON file
  --output OUTPUT  Output JSON file
  --prefix PREFIX  Character to prepend on underscore fields
  --depth DEPTH    Maximum nesting depth to process
```

---

## Export & Filtering

### `extract_embed` Command

Extract fields for transformer model embeddings.

```bash
usage: extract_embed [-h] --input INPUT --fields FIELDS [FIELDS ...]
                     [--output-format {json,csv,tsv}] [--output OUTPUT]
                     [--lemmatize | --no-lemmatize] [--remove-stopwords]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file
  --fields FIELDS       Field names from pydantic classes
  --output-format FMT   Output format: json, csv, tsv
  --output OUTPUT       Path to store results
  --lemmatize           Convert to lemma form (default: True)
  --remove-stopwords    Remove common English stop words
  --verbatim            Include verbatim phrases alongside lemmas
```

---

### `lemma_fasta` Command

Create pseudo-FASTA format from lemmatized text for genomic tools.

```bash
usage: lemma_fasta [-h] --input INPUT -m MODEL -o OUTPUT
                   [--path-file FILE] [--output-format {pfasta,lfasta}]
                   [--id-list IDS] [--id-file FILE] [--exclude | --no-exclude]
                   [--remove-stopwords] [--min-freq N]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file
  -m, --model MODEL     Pydantic model (CDE, Form)
  -o, --output OUTPUT   Output path prefix (multiple files generated)
  --path-file FILE      File specifying fields as name:path pairs
  --output-format FMT   Output format: pfasta, lfasta (default: pfasta)
  --id-list IDS         List of tinyIds to process
  --id-file FILE        File containing tinyIds
  --exclude             Exclude specified IDs (default: True)
  --remove-stopwords    Remove English stop words
  --min-freq N          Minimum token frequency for uint16 encoding
```

---

### `subset` Command

Extract a subset of CDE records by tinyId with Pydantic validation.

```bash
usage: subset [-h] -i INPUT -o OUTPUT -m MODEL
              [--output-format {json,csv,tsv}]
              [--id-list IDS [IDS ...]] [--id-file FILE]
              [--exclude | --no-exclude]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to input JSON file
  -o, --output OUTPUT   Path to output file
  -m, --model MODEL     Pydantic model: CDE, Form, EmbedText
  --output-format FMT   Output format: json, csv, tsv (default: json)
  --id-list IDS         List of tinyIds to include or exclude
  --id-file FILE        File containing tinyIds (JSON, CSV, or TSV)
  --exclude             Exclude matching tinyIds (default: include)
```

---

## Reporting

### `discovery_report` Command

Generate markdown pipeline summary reports.

```bash
usage: discovery_report [-h] -d OUTPUT_DIR -p {instrument,phrase}
                        -o OUTPUT [--version LABEL] [-i INPUT_JSON]

options:
  -h, --help            show this help message and exit
  -d, --output-dir DIR  Pipeline output directory to scan
  -p, --pipeline TYPE   Pipeline type: instrument, phrase
  -o, --output FILE     Markdown report output path
  --version LABEL       Version label for iteration tracking
  -i, --input-json FILE Original input JSON (for record count)
```

---

## LLM-Assisted Classification

> **Note**: These commands require API keys for LLM providers. See [LLM Configuration](../llm/configuration.md).

### `llm_classify` Command

Multi-LLM phrase classification with confidence aggregation.

```bash
usage: llm_classify [-h] -i INPUT_DIR -m MODULE [--output-dir DIR]
                    [--providers {claude,openai,google} ...]
                    [--config-file FILE] [--api-keys KEYS ...]
                    [--aggregation-method METHOD]
                    [--batch-size N] [--min-frequency N]
                    [--context-window N] [--reference-file FILE]
                    [--adjudicate-instruments FILE] [--adjudicate-threshold N]
                    [--skip-validation] [--dry-run]

options:
  -h, --help              show this help message and exit
  -i, --input-dir DIR     Directory with phrase_miner output
  -m, --module MODULE     Query module: instrument, temporal, instrument_family
  --output-dir DIR        Output directory (default: llm_output)
  --providers PROVIDERS   LLM providers (default: claude)
  --config-file FILE      LLM config file path
  --api-keys KEYS         API keys as provider:key pairs
  --aggregation-method M  Aggregation: unanimous, majority, weighted_majority,
                          confidence_weighted (default: majority)
  --batch-size N          Phrases per batch (default: 20)
  --min-frequency N       Minimum phrase frequency (default: 1)
  --context-window N      Context chars per occurrence (default: 200)
  --reference-file FILE   Reference data for module
  --adjudicate-instruments FILE
                          Path to instruments.tsv for family adjudication
  --adjudicate-threshold N
                          Adjudicate if confidence < threshold (default: 0.7)
  --skip-validation       Skip API key validation
  --dry-run               Validate config without LLM calls
```

**Query Modules**:

| Module | Categories |
|--------|------------|
| `instrument` | `instrument_name`, `possible_instrument`, `not_instrument` |
| `temporal` | `recency_window`, `age_range`, `time_point`, `duration`, `frequency`, `not_temporal` |
| `instrument_family` | `neuro-qol`, `promis`, `mds-updrs`, `sf-health`, `beck`, `phq`, `gad`, `mmse`, `moca`, `nihss`, `pdqualif`, `dsq`, `rome`, `other_instrument`, `not_instrument` |

See [LLM Classification](../llm/index.md) for comprehensive documentation.
