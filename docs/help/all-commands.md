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

## Instrument Extraction

### `instrument_miner` Command

Extract measurement instruments from CDE text fields using anchor-based pattern detection.

```bash
usage: instrument_miner [-h] --input INPUT [--output-dir OUTPUT_DIR]
                         [--fields FIELDS [FIELDS ...]]
                         [--min-tinyids N] [--min-instrument-words N]
                         [-a] [-s] [-d]
                         [--family-confidence-threshold N]
                         [--family-summary]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input JSON file (list of CDE items)
  --output-dir, -o DIR  Output directory for results (default: instrument_output)
  --fields, -f FIELDS   Field names to extract instruments from (default: designation definition)
  --min-tinyids N       Minimum distinct tinyIds (default: 2)
  --min-instrument-words N
                        Minimum words in instrument name (default: 3)
  -a, --extract-abbreviation-only
                        Extract abbreviation-only references like '(PHQ-9)'
  -s, --extract-supplementary
                        Extract non-Title-Case instruments (supplementary patterns)
  -d, --detect-families Enable instrument family detection
  --family-confidence-threshold N
                        Min confidence for automatic family assignment (default: 0.7)
  --family-summary      Generate instrument_families.tsv summary file
```

---

### `batch_expand_abbreviations` Command

Iterate over abbreviations, subset CDEs, and mine phrases to discover extended instrument names.

```bash
usage: batch_expand_abbreviations [-h] --input INPUT
                                  --abbreviations FILE
                                  [--acronym-column COL]
                                  [--output-dir DIR]
                                  [--fields FIELDS ...]
                                  [--k-max N] [--k-min N]
                                  [--min-tinyids N] [--top-phrases N]
                                  [--min-subset-size N]
                                  [--skip-abbreviations ABBREV ...]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input CDE JSON file
  --abbreviations FILE  TSV file with abbreviations (from instrument_miner)
  --acronym-column COL  Column name containing abbreviations (default: acronym)
  --output-dir, -o DIR  Output directory (default: abbreviation_expansions)
  --fields, -f FIELDS   Fields to search (default: designation definition)
  --k-max N             Maximum k-mer length (default: 15)
  --k-min N             Minimum k-mer length (default: 3)
  --min-tinyids N       Minimum tinyIds for reporting (default: 2)
  --top-phrases N       Top phrases per abbreviation (default: 10)
  --min-subset-size N   Min CDEs in subset to run mining (default: 3)
  --skip-abbreviations ABBREV
                        Abbreviations to skip
```

---

## Phrase Detection

### `phrase_miner` Command

Advanced k-mer phrase mining with iterative detection and masking.

```bash
usage: phrase_miner [-h] --input INPUT [--output-dir OUTPUT_DIR]
                    [--fields FIELDS [FIELDS ...]] [-K K_MAX] [-k K_MIN]
                    [-n FREQ_MIN] [-t MIN_TINYIDS]
                    [--lemmatize | --no-lemmatize] [--remove-stopwords]
                    [--skip-debruijn] [--skip-anchor]
                    [--dedup | --no-dedup] [--dedup-min-count N]
                    [--dedup-min-tokens N] [--verbatim-case-sensitive]
                    [--analyze-phrase-families] [--min-family-size N]
                    [--prefix-consolidation | --no-prefix-consolidation]
                    [--prefix-min-tinyids N] [--ledger-dir DIR]
                    [--histograms]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input JSON file (list of CDE items)
  --output-dir, -o DIR  Output directory for results (default: phrase_output)
  --fields, -f FIELDS   Field names to extract (default: designation definition)
  -K, --k-max K_MAX     Maximum k-mer length (default: 25)
  -k, --k-min K_MIN     Minimum k-mer length (default: 3)
  -n, --freq-min N      Minimum frequency threshold (default: 3)
  -t, --min-tinyids N   Minimum distinct tinyIds (default: 2)
  --lemmatize           Apply lemmatization (default: True)
  --remove-stopwords    Remove English stopwords
  --skip-debruijn       Skip de Bruijn contig extension
  --skip-anchor         Skip anchor-based extension
  --dedup               Enable whole-text dedup pre-pass (default: on)
  --dedup-min-count N   Min CDEs sharing text for dedup (default: 2)
  --dedup-min-tokens N  Min tokens for dedup emission (default: 3)
  --analyze-phrase-families
                        Analyze phrases for family groupings
  --prefix-consolidation
                        Extend phrases via right-context analysis (default: on)
  --prefix-min-tinyids N
                        Min tinyIds for prefix extension (default: 20)
  --ledger-dir DIR      Curation ledger for pre-masking remove decisions
  --histograms          Generate k-mer frequency histograms
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

### `phrase_grouper` Command

Groups phrases by shared prefix, suffix, or infix patterns for family analysis.

```bash
usage: phrase_grouper [-h] --input INPUT [--output-dir DIR]
                      [--text-column COL] [--id-column COL]
                      [--tinyid-column COL]
                      [--k-min N] [--k-max N]
                      [--min-content-words N] [--min-family-size N]
                      [--min-pattern-freq N]
                      [--trees {prefix,suffix,infix} ...]
                      [--assignment {frequency,longest,all}]
                      [--parallel] [--lowercase]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input TSV file (verbatim_phrases.tsv from phrase_miner)
  --output-dir, -o DIR  Output directory (default: phrase_families)
  --text-column COL     Column with phrase text (default: verbatim_text)
  --id-column COL       Phrase identifier column (default: phrase_id)
  --tinyid-column COL   Document ID column (default: tinyids)
  --k-min, -k N         Minimum k-mer length in tokens (default: 3)
  --k-max, -K N         Maximum k-mer length in tokens (default: 10)
  --min-content-words N Minimum non-stopword tokens (default: 1)
  --min-family-size, -n N
                        Minimum phrases to form a family (default: 3)
  --min-pattern-freq N  Minimum pattern frequency (default: 3)
  --trees TREES         Which trees to build: prefix, suffix, infix (default: all)
  --assignment METHOD   Assignment strategy: frequency, longest, all (default: frequency)
  --parallel            Build trees in parallel
  --lowercase           Normalize to lowercase before analysis
```

---

### `strip_discover` Command

Flexible regex discovery for finding verbatim pattern occurrences in CDE text fields.

```bash
usage: strip_discover [-h] [--input INPUT] [--model MODEL]
                      [--output OUTPUT] [--pattern-list FILE]
                      [--additional-patterns FILE ...]
                      [--fields FIELDS ...] [--expand-variants]
                      [--include-name-only | --no-include-name-only]
                      [--discover-bare-names] [--min-bare-words N]
                      [--allow-abbrev-variants] [--allow-embedded-abbrev]
                      [--use-expected-tinyids] [--workers N]
                      [--parent-column COL] [--discover-fails FILE]
                      [--discover-abbreviations FILE]
                      [--min-pattern-tinyids N]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Path to input JSON file (CDE records)
  --model, -m MODEL     Pydantic model: CDE, Form, Embed, EmbedText
  --output, -o OUTPUT   Path to output TSV file
  --pattern-list, -p FILE
                        TSV file with patterns. Format: 'file', 'file,col', 'file,pat_col,tid_col'
  --additional-patterns FILE
                        Additional TSV files to merge (repeatable)
  --fields, -f FIELDS   Field paths to search (default: definitions, designations)
  --expand-variants, -e Generate spelling/punctuation variants
  --include-name-only   Include bare instrument names (default: True)
  --discover-bare-names, -b
                        Second pass: discover bare names without anchor prefix
  --min-bare-words N    Minimum words for bare names (default: 2)
  --allow-abbrev-variants
                        Enable abbreviation variant matching
  --allow-embedded-abbrev
                        Allow embedded abbreviation parentheticals
  --use-expected-tinyids
                        Filter discovery by expected tinyIds from pattern list
  --workers, -w N       Parallel workers (0=auto, 1=sequential, default: 1)
  --parent-column COL   Parent phrase column for tinyId aggregation
  --discover-fails FILE Write failed patterns to TSV
  --discover-abbreviations, -a FILE
                        Extract abbreviations and discover designation patterns
  --min-pattern-tinyids N
                        Min tinyIds for abbreviation patterns (default: 2)
```

---

### `strip_phrases` Command

Remove curated phrases from specific paths in CDE documents.

```bash
usage: strip_phrases [-h] -i INPUT -m MODEL -o OUTPUT
                     {-p PATTERNS | --phrases FILE}
                     [-f FIELDS ...] [--sort-order {length,file,alpha}]
                     [-w WORKERS] [-B] [-I]
                     [--detect-remnants] [--remnant-report FILE]
                     [--clean-remnants] [-T FILE]
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
  -B, --word-boundary   Use \b word boundary anchors for matching
  -I, --ignore-case     Case-insensitive pattern matching
  --detect-remnants     Scan output for post-strip artifacts
  --remnant-report FILE Write remnant report TSV
  --clean-remnants      Apply iterative cleanup to fix artifacts
  -T, --trace-matching FILE
                        Write pattern matching trace TSV
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

### `diagnose_strip` Command

Analyze cleaned JSON for iterative stripping improvement.

```bash
usage: diagnose_strip [-h] --input INPUT --model MODEL --output OUTPUT
                      [--fields FIELDS ...] [--original FILE]
                      [--anchors ANCHORS ...] [--context-chars N]
                      [--min-count N] [--suggest-patterns] [--emit-tinyids]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Input JSON file (cleaned output from strip_phrases)
  --model, -m MODEL     Pydantic model: CDE, Form
  --output, -o OUTPUT   Output TSV with remaining patterns and frequencies
  --fields, -f FIELDS   Field paths to search (default: definitions, designations)
  --original FILE       Original JSON for comparison metrics
  --anchors ANCHORS     Anchor phrases to search for (default: 'as part of' etc.)
  --context-chars N     Context characters after anchor (default: 100)
  --min-count N         Minimum occurrence count (default: 1)
  --suggest-patterns    Output suggested patterns for supplementary_patterns.yaml
  --emit-tinyids        Include tinyIds column in output
```

---

### `strip_branching` Command

N-way branching strip producing all strip variants in a single pass.

```bash
usage: strip_branching [-h] --input INPUT --output-dir DIR
                       [--model MODEL]
                       [--inst-full-patterns FILE] [--inst-sub-patterns FILE]
                       [--temporal-patterns FILE] [--phrase-patterns FILE]
                       [--variants CODES] [--workers N] [--clean-remnants]
                       [--fields FIELDS ...] [--sort-order ORDER]

options:
  -h, --help            show this help message and exit
  --input, -i INPUT     Path to input CDE JSON file
  --output-dir, -d DIR  Output directory (writes stripped_{CODE}.json per variant)
  --model, -m MODEL     Pydantic model: CDE, Form, Embed, EmbedText (default: CDE)
  --inst-full-patterns FILE
                        Full instrument patterns TSV (_full.tsv)
  --inst-sub-patterns FILE
                        Sub-group instrument patterns TSV (_sub.tsv)
  --temporal-patterns FILE
                        Expanded temporal patterns TSV
  --phrase-patterns FILE Curated phrase patterns TSV
  --variants CODES      Comma-separated variant codes (default: all 5).
                        Valid: MTSFPF, MFSTPF, MFSFPT, MTSFPT, MFSTPT
  --workers, -w N       Parallel workers (0=auto, 1=sequential, default: 0)
  --clean-remnants      Post-strip cleanup of orphan articles, floating punctuation
  --fields, -f FIELDS   Field paths to strip (default: definitions, designations)
  --sort-order ORDER    Pattern processing order: length, file, alpha (default: length)
```

---

### `pattern_util` Command

TSV pattern utilities (merge, coalesce, field analysis, import).

```bash
usage: pattern_util [-h] [-o OUTPUT]
                    [-M FILE] [--merge-pattern-column COL]
                    [--merge-tinyids-column COL]
                    [-c FILE] [--coalesce-report FILE]
                    [--min-prefix-tinyids N] [--min-parent-tinyids N]
                    [--no-trim-anchors] [--rollup-subset-tinyids]
                    [--emit-def-variants] [--split-tiers MIN_TOKENS]
                    [-A FILE] [-i INPUT] [-m MODEL]
                    [--fields FIELDS ...] [--min-field-count N]
                    [--min-tokens N] [--exclude-patterns FILE]
                    [--group-hierarchy FILE] [--min-tinyids N]
                    [--group-semantic FILE] [--min-group-size N]
                    [--generate-strip-patterns FILE]
                    [-e FILE] [-V FILE] [-T]
                    [--add-to-supplementary FILE] [--supplementary-section NAME]
                    [-w WORKERS]

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output TSV file (required for most modes)
  -M, --merge-patterns FILE
                        Merge duplicate patterns, combine tinyIds
  -c, --coalesce-variants FILE
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
  -A, --field-analysis FILE
                        Enrich patterns with per-field counts
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
  -e, --expand-verbatim FILE
                        Expand curated patterns with variants
  -V, --validate-subsumption FILE
                        Empirical subsumption validation
  -T, --expand-temporal-seeds
                        Generate temporal seed pattern expansion
  -w, --workers N       Parallel workers (0=auto, default: 1)
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
             [--output-format {json,csv,tsv}] [-o OUTPUT]
             [--group-by PATH] [--group-type {top,path,terminal}]

options:
  -h, --help            show this help message and exit
  --input INPUT         Input JSON file
  --fields FIELDS       Fields to count
  --match-type TYPE     Match type: non_null, null, fixed, regex
  --value VALUE         Value to match (for fixed or regex)
  --output-format FMT   Output format: json, csv, tsv
  -o, --output OUTPUT   Path to store results
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

### `tsv_concat` Command

Selective column concatenation producing 2-column id+text TSV.

```bash
usage: tsv_concat [-h] -i INPUT -o OUTPUT [--id-column COL]
                  [--concat COL ...] [--drop COL ...]
                  [-s SEP] [--output-header NAME] [--skip-empty]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to input TSV/CSV file
  -o, --output OUTPUT   Path to output 2-column TSV
  --id-column COL       Column to use as ID (default: tinyId)
  --concat COL ...      Columns to concatenate (whitelist, mutually exclusive with --drop)
  --drop COL ...        Columns to exclude (blacklist, mutually exclusive with --concat)
  -s, --separator SEP   Separator between values (default: " | ")
  --output-header NAME  Header for concatenated column (default: embed_text)
  --skip-empty          Omit rows where concatenated text is empty
```

---

### `fix_underscores` Command

Fix Pydantic-incompatible field names (underscore prefix).

```bash
usage: fix_underscores [-h] --input INPUT -o OUTPUT
                       [--prefix PREFIX] [--depth DEPTH]

options:
  -h, --help       show this help message and exit
  --input INPUT    Input JSON file
  -o, --output OUTPUT
                   Output JSON file
  --prefix PREFIX  Character to prepend on underscore fields
  --depth DEPTH    Maximum nesting depth to process
```

---

## Export & Filtering

### `extract_embed` Command

Extract fields from CDE JSON for embedding text preparation.

```bash
usage: extract_embed [-h] -i INPUT -m MODEL --path-file FILE
                     [-o OUTPUT] [--output-format {json,csv,tsv}]
                     [--id-list IDS ...] [--id-file FILE]
                     [--id-type TYPE] [--exclude | --no-exclude]
                     [-c | --no-collapse]
                     [-s | --no-simplify-permissible]
                     [--concatenate SEP]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Input JSON file
  -m, --model MODEL     Pydantic model: CDE, Form, Embed, EmbedText
  --path-file FILE      Paths of interest as name:path pairs
  -o, --output FILE     Path to store results
  --output-format FMT   Output format: json, csv, tsv (default: json)
  --id-list IDS         List of tinyIds to exclude/include
  --id-file FILE        File containing tinyIds (file:column format)
  --exclude             Exclude listed IDs (default: True)
  --collapse             Collapse repeated "None;" in list items (default: on)
  --simplify-permissible Process permissibleValues heuristically (default: on)
  --concatenate SEP     Concatenate non-tinyId fields into embed_text column
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
              [-l IDS [IDS ...]] [-L FILE]
              [-t TEXT] [-f FIELDS ...] [--case-sensitive] [--regex]
              [-F PATTERN_FILE] [--match-report FILE] [--tinyid-report FILE]
              [-x | --no-exclude]

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to input JSON file
  -o, --output OUTPUT   Path to output file
  -m, --model MODEL     Pydantic model: CDE, Form, EmbedText
  --output-format FMT   Output format: json, csv, tsv (default: json)
  -l, --id-list IDS     List of tinyIds to include or exclude
  -L, --id-file FILE    File containing tinyIds (JSON, CSV, or TSV)
  -t, --text-filter TEXT
                        Text pattern to search for in specified fields
  -f, --fields FIELDS   Fields to search (default: designation definition)
  --case-sensitive      Case-sensitive text matching
  --regex               Treat --text-filter as regex
  -F, --pattern-file FILE
                        File with regex patterns (one per line)
  -x, --exclude         Exclude matching records (default: include)
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

### `pipeline_report` Command

Generate comprehensive pipeline execution reports with phase details and key metrics.

```bash
usage: pipeline_report [-h] {-s STATE_FILE | -d OUTPUT_DIR} -o OUTPUT
                       [-p {1,2,3,4}] [--title TITLE] [--version LABEL]
                       [-g FILE] [--pipeline-output FILE]
                       [--tinyid-column COL] [--source-json FILE]

options:
  -h, --help            show this help message and exit
  -s, --state-file FILE Path to workflow state file (.workflow_state.json)
  -d, --output-dir DIR  Path to pipeline output directory
  -o, --output FILE     Path to output markdown report
  -p, --phase N         Generate report for specific phase only (1-4)
  --title TITLE         Title for the report (default: Pipeline Execution Report)
  --version LABEL       Version label for this report
  -g, --ground-truth FILE
                        Ground truth pattern file for recall analysis
  --pipeline-output F   Pipeline output TSV for recall comparison
  --tinyid-column COL   Column name for tinyIds (default: tinyIds)
  --source-json FILE    Source CDE JSON file for recall analysis
```

---

### `strip_report` Command

Generate quality report for stripped JSON outputs with remnant detection and temporal phrase inventory.

```bash
usage: strip_report [-h] --output-dir OUTPUT_DIR -o OUTPUT
                    [--input-json INPUT_JSON] [--version VERSION]
                    [--embed-dir EMBED_DIR] [--no-temporal-scan]
                    [--json-pattern JSON_PATTERN]

options:
  -h, --help            show this help message and exit
  --output-dir, -d DIR  Directory containing *_stripped.json outputs
  -o, --output FILE     Path to output markdown report
  --input-json, -i FILE Original input JSON (for baseline record count)
  --version LABEL       Version label for iteration tracking
  --embed-dir DIR       Embed data directory for CSV file manifest
  --no-temporal-scan    Skip scanning for remaining temporal phrases
  --json-pattern PAT    Glob pattern to match JSON files (default: *_stripped.json)
```

---

### `recall_analyze` Command

Analyze recall and detect false negatives in instrument detection.

```bash
usage: recall_analyze [-h] -i INPUT -m MODEL -F PATTERN_FILE
                      [--pipeline-output FILE] [--pipeline-tinyid-column COL]
                      -o OUTPUT [--false-negatives-file FILE]
                      [-r FILE] [--markdown-detail FILE]
                      [--report-version LABEL] [--report-title TITLE]
                      [-f FIELDS ...] [-C]
                      [--min-recall N] [--previous-report FILE]
                      [--stopping-threshold N] [--suggest-patterns FILE]
                      [--suggest-min-matches N]

options:
  -h, --help            show this help message and exit
  -i, --input FILE      Path to source CDE JSON (ground truth)
  -m, --model MODEL     Pydantic model: CDE, Form, EmbedText
  -F, --pattern-file F  File with patterns and labels (pattern<TAB>label)
  --pipeline-output F   Pipeline output TSV with tinyIds column
  --pipeline-tinyid-column COL
                        Column name for tinyIds (default: tinyIds)
  -o, --output FILE     Path to recall report TSV
  --false-negatives-file FILE
                        Output file listing false negatives by family
  -r, --markdown-report F
                        Path to human-readable markdown report
  --markdown-detail F   Standalone detailed report for this phase
  --report-version L    Version label for iteration tracking
  --report-title TITLE  Title for markdown report
  -f, --fields FIELDS   Fields to search (default: designation definition)
  -C, --case-sensitive  Make pattern matching case-sensitive
  --min-recall N        Minimum recall threshold (default: 0.0)
  --previous-report F   Previous recall report for marginal gains
  --stopping-threshold N
                        Stop when marginal gain <= N (default: 2)
  --suggest-patterns F  Output suggested patterns for low-recall families
  --suggest-min-matches N
                        Min false negatives for suggestion (default: 2)
```

---

## Workflow Orchestration

### `workflow` Command

YAML-based workflow orchestrator for CDE analysis pipelines.

```bash
usage: workflow [-h] {run,resume,status,list,copy,scaffold,configure} ...

workflow commands:
  run                   Execute a workflow from YAML file
  resume                Resume workflow after checkpoint
  status                Show workflow execution status
  list                  List available workflow templates
  copy                  Copy a workflow template for customization
  scaffold              Generate project-specific orchestration script
  configure             Configure branching strip for specific variants
```

**Subcommands**:

```bash
# Execute a workflow
workflow run YAML [--set KEY=VALUE] [--from-step S] [--only-steps S1,S2] [--dry-run]

# Resume after curator checkpoint
workflow resume --state-file FILE

# Check pipeline state
workflow status [--state-file FILE] [-v]

# List and copy templates
workflow list
workflow copy NAME [--as FILE] [--dest DIR]

# Generate orchestration script
workflow scaffold PROJECT -i JSON -d DIR [--phases 1,2,3] [--with-iterate]

# Configure branching strip
workflow configure CODE [CODE...] [-o FILE] [--no-report] [--nway]
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
