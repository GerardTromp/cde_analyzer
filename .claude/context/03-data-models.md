# Data Models

> **Updated**: v1.0.0 (2026-03-12)

## Pydantic Models (`CDE_Schema/`)

### CDEItem (`CDE_Item.py`)

Primary data model representing an individual Common Data Element from the NLM CDE API.

**Key fields**:
- `tinyId: str` — unique short identifier (e.g., "Ab12cD")
- `designations: List[Designation]` — human-readable names
- `definitions: List[Definition]` — textual definitions
- `valueDomain: ValueDomain` — data type, permissible values
- `classification: List[Classification]` — hierarchical classification
- `properties: List[Property]` — key-value metadata
- `ids: List[Id]` — external identifiers
- `referenceDocuments: List[ReferenceDocument]` — citations
- `registrationState: RegistrationState` — governance status

### CDEForm (`CDE_Form.py`)

Form structure model containing grouped CDEs.

**Key fields**:
- `tinyId: str`
- `designations: List[Designation]`
- `definitions: List[Definition]`
- `formElements: List[FormElement]` — ordered CDE references
- `elementType: str`

### Shared Classes (`classes.py`)

| Class | Purpose | Key Fields |
|-------|---------|------------|
| `Designation` | Display name | `designation`, `tags`, `sources` |
| `Definition` | Text definition | `definition`, `tags`, `sources` |
| `ValueDomain` | Data constraints | `datatype`, `permissibleValues`, `uom` |
| `Classification` | Category tree | `stewardOrg`, `elements` (recursive) |
| `Property` | Metadata pair | `key`, `value` (Union[str, dict]) |
| `Source` | Provenance | `sourceName`, `created` |
| `RegistrationState` | Status | `registrationStatus`, `administrativeStatus` |
| `Id` | External ID | `source`, `id`, `version` |
| `ReferenceDocument` | Citation | `title`, `uri`, `providerOrg` |
| `CreatedBy` / `UpdatedBy` | Audit | `username` |
| `Comment` / `Reply` | Discussion | `usename` (API typo), `text` |

### EmbedText (`EmbedText.py`)

Output model for `extract_embed` action — flat text for embedding.

| Field | Type |
|-------|------|
| `tinyId` | `str` |
| `text` | `str` (concatenated designation + definition) |

### LLM Classification (`LLM_Classification.py`)

Result models for `llm_classify` action.

| Class | Purpose |
|-------|---------|
| `ClassificationResult` | Single provider result (label, confidence, reasoning) |
| `AggregatedResult` | Multi-provider reconciliation (quintile, agreement) |

## Pattern TSV Format

The primary interchange format for curation patterns. Tab-separated with header row.

### Core columns (always present)

| Column | Description |
|--------|-------------|
| `pattern` | The text pattern (literal or regex prefixed with `REGEX:`) |
| `tinyIds` | Comma-separated tinyId list where pattern occurs |
| `type` | Pattern type: `kmer`, `verbatim`, `abbreviation`, `dedup` |
| `source_pattern` | Original pattern before coalescing |

### Curation columns (added by gate/editor)

| Column | Description |
|--------|-------------|
| `decision` | `strip`, `skip`, `modify`, `substitute`, `followup` |
| `modification` | Replacement text (for `modify`/`substitute` decisions) |
| `group` | Instrument group name (for instrument patterns) |

### Enrichment columns (added by field analysis)

| Column | Description |
|--------|-------------|
| `tinyid_count` | Number of tinyIds |
| `def_count` | Count of definitions containing the pattern |
| `desig_count` | Count of designations containing the pattern |
| `field_profile` | Comma-separated field distribution (e.g., `D:5,d:3`) |
| `example_definition` | Sample definition text |
| `example_designation` | Sample designation text |

### Substitute patterns TSV

| Column | Description |
|--------|-------------|
| `pattern` | Original text to match |
| `replace_with` | Replacement text |
| `tinyIds` | Scope of application |

## CDE JSON Structure

The NLM CDE API returns JSON with deeply nested structures. Key paths used by the pipeline:

```
{tinyId}
├── designations[*].designation     # Primary text field for mining/stripping
├── definitions[*].definition       # Primary text field for mining/stripping
├── valueDomain.datatype
├── valueDomain.permissibleValues[*].permissibleValue
├── classification[*].elements[*]   # Recursive nesting
├── properties[*].key / .value
└── ids[*].source / .id
```

**Field paths** used in stripping: `definitions.*.definition` and `designations.*.designation`.

## Curation Ledger Format

Persistent storage for incremental curation (`logic/curation_ledger.py`).

### `ledger_meta.yaml`

```yaml
runs:
  - run_id: "20260312_143000"
    phase: "instrument"
    timestamp: "2026-03-12T14:30:00"
    n_patterns: 458
    n_auto_keep: 300
    n_auto_remove: 100
    n_needs_review: 58
```

### Decision TSVs (`instrument_decisions.tsv`, `phrase_decisions.tsv`)

| Column | Description |
|--------|-------------|
| `pattern` | Pattern text |
| `decision` | `strip`, `skip`, `modify`, `substitute` |
| `modification` | Replacement text (if modify/substitute) |
| `tinyIds` | TinyIds at time of decision |
| `run_id` | When decision was recorded |

## Workflow YAML Format

Pipeline definitions used by `workflow run`.

```yaml
name: "pipeline_name"
variables:
  input_json: "${INPUT_JSON}"
  output_dir: "${OUTPUT_DIR}"
steps:
  - name: step_name
    action: action_name
    args: "--flag ${variable}"
  - name: checkpoint_step
    checkpoint: true
    message: "Review output before continuing"
    skip_if_file: "${curated_tsv}"
```
