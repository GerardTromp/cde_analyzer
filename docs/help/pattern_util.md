# `pattern_util` Command

TSV pattern utilities (merge, coalesce, field analysis, import).

## Overview

The `pattern_util` command provides TSV manipulation utilities for pattern files. Most operations work on TSV files only — no CDE JSON input required (except `--field-analysis`).

## Usage

```bash
# Merge duplicate patterns
cde-analyzer pattern_util --merge-patterns FILE -o OUTPUT.tsv

# Coalesce patterns (remove subsumed)
cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT.tsv \
    [--coalesce-report REPORT.tsv] [--min-prefix-tinyids N] \
    [--min-parent-tinyids N] [--rollup-subset-tinyids] \
    [--emit-def-variants] [--split-tiers MIN_TOKENS]

# Field analysis (enrich with per-field counts)
cde-analyzer pattern_util --field-analysis FILE \
    -i SOURCE.json -m CDE -o ENRICHED.tsv \
    [--min-field-count N] [--min-tokens N] [--exclude-patterns FILE]

# Group hierarchy
cde-analyzer pattern_util --group-hierarchy FILE -o GROUPED.tsv \
    [--min-tinyids N] [--min-tinyids-scale F]

# Semantic grouping
cde-analyzer pattern_util --group-semantic FILE -o GROUPED.tsv \
    [--min-group-size N] [--min-prefix-words N]

# Expand curated patterns with variants
cde-analyzer pattern_util --expand-verbatim FILE -o EXPANDED.tsv \
    [--no-temporal-variants] [--no-case-variants] \
    [--no-number-variants] [--no-plural-variants] \
    [--rescan -i SOURCE.json -m CDE]

# Import patterns to supplementary config
cde-analyzer pattern_util --add-to-supplementary CURATED.tsv

# Interactive browser-based TSV editor
cde-analyzer pattern_util --edit FILE [--port N] [--no-browser]

# Multi-curator curation
cde-analyzer pattern_util --init-curation FILE --curators "a,b,c" [-o DIR]
cde-analyzer pattern_util --merge-curation FILE1 FILE2 ... -o DIR

# Centralized curation server
cde-analyzer pattern_util --serve-curation CONFIG.yaml --curation-source FILE
cde-analyzer pattern_util --curation-status DIR

# Incremental curation (re-run optimization)
cde-analyzer pattern_util --curation-gate FILE --ledger-dir DIR --phase P -i JSON -o DIR
cde-analyzer pattern_util --finalize-curation DIR --ledger-dir DIR --phase P -i JSON

# Detect rare words in CDE fields
cde-analyzer pattern_util --detect-rare-words -i cdes.json -m CDE -o rare.tsv

# Split needs_review into high/low priority (Zipf-based)
cde-analyzer pattern_util --split-priority needs_review.tsv [--split-auto-skip]

# Pre-strip remnant analysis
cde-analyzer pattern_util --remnant-analysis patterns.tsv -i cdes.json -o remnants.tsv

# Generate LLM semantic proxies
cde-analyzer pattern_util --generate-proxies patterns.tsv -i cdes.json -m CDE \
    --provider claude -o proxied.tsv

# Harvest residuals from sanity check
cde-analyzer pattern_util --harvest-residuals sanity.tsv --curated curated.tsv -o harvest.tsv

# Analyze parent-filtered patterns for recovery
cde-analyzer pattern_util --recover-parent-filtered report.tsv -o recovery.tsv
```

## Modes

### Merge Mode

Combine duplicate pattern rows, merging their tinyId sets:

```bash
cde-analyzer pattern_util --merge-patterns discovered.tsv -o merged.tsv
```

Useful after removing sub-instrument details when multiple patterns become identical.

### Coalesce Mode

Remove patterns subsumed by longer patterns (tinyId-aware):

```bash
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --coalesce-report subsumption.tsv
```

A pattern is subsumed if:
1. It's a substring of longer pattern(s)
2. Its tinyIds are covered by the union of those longer patterns' tinyIds

**Anchor trimming** (default ON): Patterns containing anchor phrases (`as part of`, `based on`, etc.) are trimmed to the bare instrument name. Disable with `--no-trim-anchors`.

**Prefix extraction**: Groups patterns by common prefix and replaces them with the shortest prefix meeting the tinyId threshold.

```bash
cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \
    --min-prefix-tinyids 3
```

Example: "as part of Neuro-QOL Lower..." and "as part of Neuro-QOL Upper..." become "as part of Neuro-QOL" if it covers enough tinyIds.

**TinyId-subset rollup**: Removes short patterns whose tinyIds are a strict subset of a longer pattern's, even without text substring relation. Requires substring match to prevent unrelated subsumption.

**Definition-form variants**: Emits additional patterns without trailing separators (` -`, ` - `) for definition field matching.

**Tier splitting**: Splits output into tier-1 (≥N tokens) and tier-2 (<N tokens) for two-pass stripping.

### Field Analysis Mode

Enrich a patterns TSV with per-field tinyId counts by scanning source JSON:

```bash
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i source.json -m CDE \
    -o coalesced_fields.tsv \
    --min-field-count 6 --min-tokens 3 \
    --exclude-patterns exclusions.tsv
```

**New columns added**: `tinyid_count` (unique CDE count), `definition_count`, `designation_count`, `field_profile` (one of: `def-only`, `desig-only`, `both-all`, `mixed`), `example_name`, `example_context`

**Filters applied**:
- `--min-field-count N`: drop patterns below N in ALL fields
- `--min-tokens N`: drop patterns with fewer than N whitespace-delimited tokens
- `--exclude-patterns FILE`: remove patterns matching entries in exclusion file

### Group Hierarchy Mode

Assign `group`, `sub_group`, `suffix` labels based on shared prefix:

```bash
cde-analyzer pattern_util --group-hierarchy coalesced.tsv \
    -o grouped.tsv --min-tinyids 3
```

### Semantic Grouping Mode

Group patterns by shared prefix spans with SpaCy POS-based boundary trimming:

```bash
cde-analyzer pattern_util --group-semantic coalesced.tsv \
    -o grouped.tsv --min-group-size 2 --min-prefix-words 2
```

### Generate Strip Patterns

Produce strip-ready pattern files from a group-hierarchy TSV:

```bash
cde-analyzer pattern_util --generate-strip-patterns grouped.tsv -o strip_patterns
```

Produces `{output}_full.tsv` (full removal) and `{output}_sub.tsv` (group prefix removed, suffix retained).

### Normalize Mode

Convert any pattern TSV to minimal 2-column format for merging:

```bash
cde-analyzer pattern_util --to-minimal discovered.tsv -o minimal.tsv
```

Auto-detects column names (`pattern`/`tinyIds`/`tinyids`) and normalizes tinyId separator to pipe (`|`). Useful for combining files from different pipeline stages that may have different column structures.

### Expand Verbatim Mode

Expand curated patterns with temporal preposition, case, number, and plural variants for precise verbatim matching:

```bash
cde-analyzer pattern_util --expand-verbatim curated.tsv -o expanded.tsv
```

Generates narrow variants of each curated pattern:
- **Temporal**: preposition × tense-word variants (`In the past` → also `During the past`, `Over the last`, etc.)
- **Case**: original + all-lowercase (`In the past` → also `in the past`)
- **Number**: digit ↔ word (`7 days` ↔ `seven days`)
- **Plural**: temporal singular ↔ plural (`day` ↔ `days`, `week` ↔ `weeks`)

Optionally re-scan source JSON to discover actual tinyIds per variant:

```bash
cde-analyzer pattern_util --expand-verbatim curated.tsv \
    -i source.json -m CDE --rescan -o expanded.tsv
```

Without `--rescan`, variants inherit the source pattern's tinyIds. With `--rescan`, each variant is searched in the JSON and variants with no matches are dropped.

Output includes `source_pattern` column for tracing back to the curated pattern.

### Supplementary Import Mode

Add curated patterns to `config/supplementary_patterns.yaml`:

```bash
cde-analyzer pattern_util --add-to-supplementary curated.tsv
```

The TSV must have `pattern` and `name` (or `suggested_name`) columns. Only rows with `include` column set to `yes` are imported. The input file is deleted after successful import.

### Editor Mode

Open an interactive browser-based TSV editor for reviewing and editing pattern files:

```bash
cde-analyzer pattern_util --edit coalesced_fields.tsv
```

This starts a local HTTP server and opens your default browser with the TSV loaded. The editor supports:

- **Sort and filter** — click column headers to sort; use filter inputs to narrow rows
- **Edit cells** — click any cell to edit its value in place
- **Delete rows** — remove false positive patterns during curation
- **Save / Save As** — write changes back to the original file or to a new file (e.g., `curated.tsv`)

Press **Ctrl-C** in the terminal to stop the server when you are done.

**Options**:

- `--port N` — use a specific port instead of auto-assigning (default: auto)
- `--no-browser` — start the server without automatically opening the browser

**Without a file argument**, the editor opens blank and allows drag-and-drop loading of any TSV file.

**Typical curation workflow**:

```bash
# 1. Open the enriched patterns for review
cde-analyzer pattern_util --edit phase1_output/coalesced_fields.tsv

# 2. In the browser: review, delete false positives, Save As curated.tsv
# 3. Ctrl-C to stop the server

# 4. Resume the pipeline
cde-analyzer workflow resume --state-file phase1_output/.workflow_state.json
```

### YAML/TSV Conversion

Convert supplementary YAML patterns to TSV for editing, then back:

```bash
# YAML → TSV (for editing in the browser editor)
cde-analyzer pattern_util --yaml-to-tsv config/supplementary_patterns.yaml -o supplementary.tsv

# Edit in the browser
cde-analyzer pattern_util --edit supplementary.tsv

# TSV → YAML (after editing)
cde-analyzer pattern_util --tsv-to-yaml supplementary.tsv -o config/supplementary_patterns.yaml
```

### Multi-Curator Curation

Distribute a patterns TSV to multiple curators, then merge their independent
annotations with inter-rater agreement statistics.

**Initialize** — create per-curator copies with annotation columns:

```bash
cde-analyzer pattern_util --init-curation coalesced_fields.tsv \
    --curators "alice,bob,carol" -o curation/
```

Each curator receives a file like `coalesced_fields.alice.tsv` containing the
original columns plus `decision`, `modification`, `notes`, and `curator`.

**Merge** — combine annotated files and produce statistics:

```bash
cde-analyzer pattern_util --merge-curation \
    curation/coalesced_fields.alice.tsv \
    curation/coalesced_fields.bob.tsv \
    curation/coalesced_fields.carol.tsv \
    -o curation/results/
```

Outputs:

| File | Contents |
|------|----------|
| `consensus.tsv` | All patterns with majority decision and per-curator columns |
| `discrepancies.tsv` | Only patterns where curators disagree |
| `inter_rater_report.md` | Cohen's kappa, Krippendorff's alpha, agreement breakdown |
| `discrepancies.html` | Interactive browser-based visual diff viewer |

See [Distributed Curation](../vignettes/distributed-curation.md) for the
full workflow including the standalone editor and centralized server.

### Centralized Curation Server

Host a single server that serves per-curator editor sessions via unique
token URLs. Curators access their session in a browser — no file exchange
or `cde-analyzer` installation needed.

**Start the server:**

```bash
cde-analyzer pattern_util --serve-curation curation_server.yaml \
    --curation-source coalesced_fields.tsv
```

The server:

1. Reads curator list, TLS settings, and timespan from the YAML config
2. Generates HMAC-authenticated token URLs for each curator
3. Serves per-curator TSV editors at `https://host:port/c/{token}/`
4. Provides an admin dashboard at `https://host:port/admin/`
5. Tracks session state in `.curation_state.yaml`

**Configuration file** (`curation_server.yaml`):

```yaml
curators:
  - name: Alice Smith
    email: alice@example.com
  - name: Bob Jones
    email: bob@example.com

server:
  host: 0.0.0.0
  port: 8443
  output_dir: ./curation_output
  timespan: 24h

tls:
  mode: auto          # auto | custom | proxy

security:
  secret_key: auto    # auto-generated per session
  max_attempts: 5     # failed auth before lockout
```

**TLS modes:**

| Mode | Behavior |
|------|----------|
| `auto` | Generate self-signed cert on first run (stored in `{output_dir}/.tls/`) |
| `custom` | Use provided `cert` and `key` paths |
| `proxy` | Plain HTTP (behind nginx/caddy reverse proxy with TLS termination) |

**Check session status:**

```bash
cde-analyzer pattern_util --curation-status ./curation_output
```

See [Distributed Curation — Centralized Mode](../vignettes/distributed-curation.md#centralized-server-mode) for the full workflow.

### Standalone Editor (Zipapp)

The editor can be packaged as a self-contained `.pyz` archive for distribution
to curators who do not have `cde-analyzer` installed. Only Python 3.8+ is required.

**Build the archive:**

```bash
python scripts/build_editor_zipapp.py
# → dist/cde_editor.pyz (~59 KB)
```

**Curator usage:**

```bash
python cde_editor.pyz patterns.tsv            # edit + save
python cde_editor.pyz                          # blank editor (drag-drop)
python cde_editor.pyz patterns.tsv --port 8080 # specific port
python cde_editor.pyz --version                # show version
```

### Incremental Curation

When the CDE repository is expanded with new CDEs, the full pipeline must
re-run. The **curation gate** and **finalize curation** commands eliminate
redundant curation by persistently recording decisions in a **curation ledger**
and auto-applying them on re-runs. Only genuinely new or changed patterns are
presented to curators.

**Curation gate** — classify patterns against the ledger before a checkpoint:

```bash
cde-analyzer pattern_util --curation-gate enriched.tsv \
    --ledger-dir .curation_ledger --phase instrument \
    -i cdes.json -o gate_output/
```

Outputs:

| File | Contents |
|------|----------|
| `gate_result.json` | Classification summary: counts, file paths, skip flag |
| `auto_resolved.tsv` | Patterns resolved from prior decisions (strip/skip/modify/substitute) |
| `needs_review.tsv` | New or changed patterns requiring human curation |
| `curated.tsv` | Written ONLY when needs_review is empty (signals checkpoint skip) |
| `substitute_patterns.tsv` | Patterns with `replace_with` column (from substitute decisions) |

**Finalize curation** — merge results and update the ledger after the checkpoint:

```bash
cde-analyzer pattern_util --finalize-curation gate_output/ \
    --ledger-dir .curation_ledger --phase instrument -i cdes.json
```

If the checkpoint was skipped (all auto-resolved), `curated.tsv` and
`substitute_patterns.tsv` already exist and the ledger is updated with
timestamps. If the checkpoint paused for human review, `auto_resolved.tsv`
and the human-curated `needs_review.tsv` are merged into `curated.tsv`
(strip/modify patterns) and `substitute_patterns.tsv` (substitute patterns
with `replace_with` column), and all decisions are recorded in the ledger.

**Decision rules:**

| Prior decision | Current tinyIds vs prior | Action |
|---------------|------------------------|--------|
| (not in ledger) | — | needs_review (new pattern) |
| strip | any | auto_strip (validity is inherent) |
| skip | same or subset | auto_skip |
| skip | has new tinyIds | needs_review (new context) |
| modify | same or subset | auto_modify (apply stored modification) |
| modify | has new tinyIds | needs_review (new context) |
| substitute | same or subset | auto_substitute (apply stored replacement) |
| substitute | has new tinyIds | needs_review (new context) |

**Ledger storage** (`--ledger-dir`):

```
.curation_ledger/
  ledger_meta.yaml              # run history + tinyId hashes
  instrument_decisions.tsv      # Phase 1 pattern decisions
  phrase_decisions.tsv           # Phase 2 pattern decisions
```

**Pipeline integration** — the instrument and phrase pipeline workflows include
`curation_gate` and `finalize_curation` steps automatically. The checkpoint
between them uses `skip_if_file` to skip when all patterns are auto-resolved:

```yaml
# In instrument_pipeline.yaml / phrase_pipeline.yaml
- name: curation_gate
  action: pattern_util
  args:
    curation_gate: "${field_enriched_tsv}"
    ledger_dir: "${curation_ledger_dir}"
    phase: instrument
    input: "${input_json}"
    output: "${output_dir}"

- name: curator_review
  checkpoint: true
  skip_if_file: "${curated_tsv}"
  message: |
    Review ${output_dir}/needs_review.tsv

- name: finalize_curation
  action: pattern_util
  args:
    finalize_curation: "${output_dir}"
    ledger_dir: "${curation_ledger_dir}"
    phase: instrument
    input: "${input_json}"
```

**Typical scenarios:**

- **First run** (no ledger): All patterns go to `needs_review.tsv`. Full curation required (same as current behavior).
- **Re-run, same CDEs**: All patterns auto-resolved. Checkpoint skipped entirely.
- **Re-run, new CDEs**: Prior strip/skip/modify decisions auto-applied; only new patterns presented to curators.

## Options

### Merge Options

| Option | Description |
|--------|-------------|
| `--merge-patterns`, `-M` FILE | Deduplicate patterns within a single TSV file, merging tinyId sets for identical patterns |
| `-o, --output FILE` | Output merged TSV file (required) |
| `--merge-pattern-column` | Column name for patterns (default: `pattern`) |
| `--merge-tinyids-column` | Column name for tinyIds (default: `tinyIds`) |

**Note**: To merge multiple files, first normalize with `--to-minimal`, concatenate, then merge. See [Merge Multiple Pattern Files](#merge-multiple-pattern-files) example.

### Coalesce Options

| Option | Description |
|--------|-------------|
| `--coalesce-variants`, `-c` FILE | Input TSV file for subsumption analysis |
| `-o, --output FILE` | Output coalesced TSV file (required) |
| `--coalesce-report FILE` | Write subsumption report showing removed patterns |
| `--min-prefix-tinyids N` | Enable prefix extraction (0 = disabled) |
| `--min-parent-tinyids N` | Filter by parent phrase tinyId count (0 = disabled) |
| `--no-trim-anchors` | Disable anchor phrase trimming |
| `--rollup-subset-tinyids` | Enable tinyId-subset rollup |
| `--emit-def-variants` | Emit definition-form variants (without trailing separator) |
| `--defer-parent-filter` / `--no-defer-parent-filter` | Defer parent-tinyid filtering until after prefix extraction. Patterns rescued by a prefix group survive even if individual parent count is below threshold. Use for phrase pipelines where cross-parent aggregation matters (default: off) |
| `--split-tiers MIN_TOKENS` | Split output into tier-1/tier-2 by token count (0 = disabled) |

### Field Analysis Options

| Option | Description |
|--------|-------------|
| `--field-analysis`, `-A` FILE | Input patterns TSV to enrich |
| `-i, --input FILE` | Source CDE JSON for scanning (required) |
| `-m, --model NAME` | Pydantic model name (default: `CDE`) |
| `--fields PATHS` | Field paths to scan (default: `definitions.*.definition designations.*.designation`) |
| `--min-field-count N` | Drop patterns below N in both fields (0 = disabled) |
| `--min-tokens N` | Drop patterns with fewer than N tokens (0 = disabled) |
| `--exclude-patterns FILE` | Remove patterns matching entries in exclusion file |
| `--dedup-phrases FILE` | Remove patterns that are substrings of dedup phrases in this TSV (from phrase_miner). Prevents dedup fragments from cluttering curation |

### Group Options

| Option | Description |
|--------|-------------|
| `--group-hierarchy FILE` | Assign group/sub_group labels by shared prefix |
| `--min-tinyids N` | Drop patterns with fewer than N tinyIds (0 = disabled) |
| `--min-tinyids-scale F` | Adaptive tinyId threshold scale factor (0.0 = disabled) |
| `--generate-strip-patterns FILE` | Generate strip-ready files from group-hierarchy TSV |
| `--group-semantic FILE` | Semantic grouping with POS-based boundary trimming |
| `--min-group-size N` | Minimum patterns per group (default: 2) |
| `--min-prefix-words N` | Minimum words in shared prefix (default: 2) |
| `--no-temporal-implied` | Disable implied-ONE temporal variant generation |

### Expand Verbatim Options

| Option | Description |
|--------|-------------|
| `--expand-verbatim`, `-e` FILE | Input curated patterns TSV to expand with variants |
| `-o, --output FILE` | Output expanded TSV file (required) |
| `--no-case-variants` | Skip case variant generation (original + lowercase) |
| `--no-number-variants` | Skip digit ↔ word variants (`7` ↔ `seven`) |
| `--no-plural-variants` | Skip singular ↔ plural variants (`day` ↔ `days`) |
| `--no-temporal-variants` | Skip temporal preposition variants (in/over/during/for/within × past/last) |
| `--rescan` | Re-scan source JSON for tinyIds per variant (requires `-i` and `-m`) |

### Normalize Options

| Option | Description |
|--------|-------------|
| `--to-minimal FILE` | Normalize TSV to 2-column format (pattern, tinyIds) for merging |
| `-o, --output FILE` | Output normalized TSV file (required) |

### Import Options

| Option | Description |
|--------|-------------|
| `--add-to-supplementary FILE` | Curated TSV to import |
| `--supplementary-section` | YAML section name (default: `added_patterns`) |

### Editor Options

| Option | Description |
|--------|-------------|
| `--edit FILE` | Open interactive browser-based TSV editor. Without a file, opens blank for drag-drop |
| `--port N` | Port for the editor server (default: 0 = auto-assign) |
| `--no-browser` | Start server without opening the browser |

### Multi-Curator Options

| Option | Description |
|--------|-------------|
| `--init-curation FILE` | Initialize multi-curator curation from enriched TSV |
| `--curators "a,b,c"` | Comma-separated curator names (min 2, alphanumeric + underscore) |
| `--merge-curation FILE ...` | Merge 2+ annotated curator TSV files |
| `-o, --output DIR` | Output directory for init-curation or merge-curation |

### Centralized Server Options

| Option | Description |
|--------|-------------|
| `--serve-curation CONFIG` | Start centralized curation server from YAML config |
| `--curation-source FILE` | Source patterns TSV (required with `--serve-curation`) |
| `--curation-status DIR` | Show status of a centralized curation session |
| `--no-browser` | Start server without opening admin dashboard |

### Incremental Curation Options

| Option | Description |
|--------|-------------|
| `--curation-gate FILE` | Enriched TSV to classify against the curation ledger |
| `--finalize-curation DIR` | Gate output directory to merge and update ledger |
| `--ledger-dir DIR` | Curation ledger directory (default: `../.curation_ledger`) |
| `--phase {instrument,phrase}` | Pipeline phase for ledger key |

### Conversion Options

| Option | Description |
|--------|-------------|
| `--yaml-to-tsv FILE` | Convert supplementary YAML to editable TSV |
| `--tsv-to-yaml FILE` | Convert edited TSV back to supplementary YAML |

### LLM Proxy Generation Options

| Option | Description |
|--------|-------------|
| `--generate-proxies FILE` | Generate semantic proxies for patterns using an LLM. Reads a patterns TSV, looks up sample CDE contexts from `--input` JSON, queries the LLM for a 1-3 word semantic proxy per pattern, and writes enriched TSV with `replace_with` and `proxy_reasoning` columns. Requires `--input`, `--model`, and `--provider` |
| `--provider {claude,openai,google}` | LLM provider for proxy generation (default: `claude`) |
| `--llm-model MODEL` | LLM model identifier (e.g., `claude-sonnet-4-20250514`). Uses provider default if not specified |
| `--config-file FILE` | Path to LLM config file (default: `~/.cde_analyzer/llm_config.json`) |
| `--api-keys KEYS` | API keys in `provider:key` format |
| `--context-window N` | Characters of surrounding text to include as context (default: 150) |
| `--max-contexts N` | Maximum CDE contexts to show per pattern (default: 3) |
| `--dry-run` | Show prompts without calling LLM |

### Harvest Residuals Options

| Option | Description |
|--------|-------------|
| `--harvest-residuals FILE` | Cross-reference sanity check residuals against curated patterns. Classifies residuals as `should_have_matched`, `partial_match`, or `new_candidate`. Requires `--curated` and `--output` |
| `--curated FILE` | Curated patterns TSV for residual harvesting |
| `--update-ledger FILE` | Merge new patterns into a cumulative pattern registry. Requires `--ledger` and `--output` |
| `--ledger FILE` | Path to existing ledger TSV (created if missing) |
| `--source LABEL` | Source label for ledger entries (e.g., `mined`, `harvested`) (default: `unknown`) |
| `--round N` | Iteration round number for ledger entries (default: 1) |

### Rare Word Detection Options

| Option | Description |
|--------|-------------|
| `--detect-rare-words`, `-R` | Scan CDE fields for words frequent across CDEs but rare in general English (via wordfreq Zipf scores). Requires `--input`, `--model`, and `--output` |
| `--zipf-threshold N` | Maximum effective Zipf score to be considered rare. Lower = stricter. Scale: 0=absent, 3=uncommon, 5=common (default: 1.5) |
| `--caps-penalty N` | Zipf penalty for ALL-CAPS words (len >= 2). Catches acronyms that spell common words (default: 2.5) |
| `--rare-word-whitelist FILE` | Path to rare-word whitelist YAML. Auto-discovers `config/rare_word_whitelist.yaml` and `./rare_word_whitelist.yaml` |
| `--no-whitelist` | Skip whitelist loading entirely |

### Priority Split Options

| Option | Description |
|--------|-------------|
| `--split-priority FILE` | Split a needs_review TSV into high-priority (domain-specific) and low-priority (common English) files using wordfreq Zipf scores. Outputs `{stem}_high.tsv` and `{stem}_low.tsv` |
| `--split-auto-skip` | Pre-fill `decision=skip` in low-priority patterns (default: leave blank) |

### Remnant Analysis Options

| Option | Description |
|--------|-------------|
| `--remnant-analysis FILE` | Pre-strip diagnostic: simulate stripping and identify frequent context words around each match. Reports extensions suggesting missing longer patterns. Requires `--input` and `--output` |
| `--context-words N` | Number of context words to extract on each side of a match (default: 3) |
| `--min-context-freq N` | Minimum frequency for a context extension to be reported (default: 5) |

### Parent Filter Diagnostics

| Option | Description |
|--------|-------------|
| `--recover-parent-filtered FILE` | Analyze parent-filtered patterns from a coalesce report for prefix recovery opportunities. Groups by word-level prefix and reports candidates with high divergence. Requires `--output` |

## Examples

### Full Pipeline Example

```bash
# 1. Start with discovered patterns
cde-analyzer strip_discover -i cdes.json -m CDE -o discovered.tsv \
    --pattern-list instruments.tsv --expand-variants

# 2. Coalesce with prefix extraction and parent filtering
cde-analyzer pattern_util --coalesce-variants discovered.tsv -o coalesced.tsv \
    --coalesce-report subsumption.tsv --min-prefix-tinyids 3 --min-parent-tinyids 20

# 3. Enrich with field analysis and filter
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i cdes.json -m CDE -o coalesced_fields.tsv \
    --min-field-count 6 --min-tokens 3

# 4. Strip with cleanup
cde-analyzer strip_phrases -i cdes.json -m CDE -o cleaned.json \
    --patterns coalesced_fields.tsv --clean-remnants \
    --detect-remnants --remnant-report remnants.tsv
```

### Merge Multiple Pattern Files

To combine patterns from multiple sources (e.g., `coalesced.tsv` and `abbrev_patterns.tsv`):

```bash
# 1. Normalize each file to minimal 2-column format
#    (handles column name variations, normalizes tinyId separator to pipe)
cde-analyzer pattern_util --to-minimal coalesced.tsv -o coalesced_min.tsv
cde-analyzer pattern_util --to-minimal abbrev_patterns.tsv -o abbrev_min.tsv

# 2. Concatenate files (skip header on subsequent files)
head -1 coalesced_min.tsv > combined.tsv
tail -n +2 coalesced_min.tsv >> combined.tsv
tail -n +2 abbrev_min.tsv >> combined.tsv

# 3. Merge duplicate patterns (combines tinyId sets for identical patterns)
cde-analyzer pattern_util --merge-patterns combined.tsv -o merged.tsv

# 4. Clean up intermediate files
rm coalesced_min.tsv abbrev_min.tsv combined.tsv
```

**Note**: `--merge-patterns` operates on a single file, deduplicating rows with identical patterns and merging their tinyId sets. Use the normalize-concatenate-merge workflow above to combine multiple source files.

### Import Supplementary Patterns

After false-negative analysis:

```bash
# 1. Review false_negatives.tsv and set 'include' to 'yes' for patterns to add
# 2. Import to supplementary config
cde-analyzer pattern_util --add-to-supplementary false_negatives.tsv

# 3. Re-run phrase_miner to pick up new patterns
cde-analyzer phrase_miner -i cdes.json -o output/ --extract-supplementary
```

## Additional Capabilities (v0.5.x)

Several enhancements were added in the v0.5.x series:

- **Anchor Trimming** (default on in `--coalesce-variants`): Patterns containing anchor phrases ("as part of", "based on") are trimmed to the bare instrument name. Disable with `--no-trim-anchors`.
- **Rollup-Subset TinyIds** (`--rollup-subset-tinyids`): After text-based subsumption, removes short patterns whose tinyIds are a strict subset of a longer pattern's tinyIds.
- **Definition-Form Variants** (`--emit-def-variants`): Emits patterns both with and without trailing separators (` -`, ` - `) so that definitions are stripped alongside designations.
- **Tier Splitting** (`--split-tiers MIN_TOKENS`): Splits coalesced output into tier-1 (>=MIN_TOKENS) and tier-2 (<MIN_TOKENS) for two-pass stripping.
- **Group Hierarchy** (`--group-hierarchy`): Assigns `group`, `sub_group`, `suffix` labels based on shared prefix.
- **Verbatim Variant Expansion** (`--expand-verbatim`): Expands curated patterns with temporal/case/number/plural variants. Pipeline order: temporal -> plural -> number -> case. With `--rescan`, only variants that exist in the source data survive.

See [Extensions v0.5.x](../appendix/extensions_v0.5.x.md#2-pattern_util-enhancements) for full implementation details.

## Related Commands

- [strip_discover](strip_discover.md) — Pattern discovery
- [strip_analyze](strip_analyze.md) — Conflict and false-negative analysis
- [strip_phrases](strip_phrases.md) — Apply stripping with remnant cleanup
- [discovery_report](discovery_report.md) — Generate pipeline summary reports
