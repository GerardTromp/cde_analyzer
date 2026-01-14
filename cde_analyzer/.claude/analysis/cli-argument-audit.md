# CLI Argument Standardization Audit

**Date**: 2026-01-13
**Purpose**: Analyze current CLI arguments across all actions and propose standardization

## Executive Summary

**Findings**:
- 9 actions analyzed with significant inconsistencies
- 4 categories of common arguments identified
- 23 unique argument patterns found
- Inconsistencies in naming, short flags, and boolean handling

**Recommendations**:
1. Standardize common arguments (input/output/format/model)
2. Create shared argument groups for reuse
3. Establish naming conventions document
4. Implement gradually to avoid breaking changes

---

## Current Argument Analysis

### Common Arguments Across Actions

| Argument | Actions Using | Variations | Standard Proposal |
|----------|---------------|------------|-------------------|
| Input file | 9/9 | `--input`, `-i` | `--input`, `-i` |
| Output file | 7/9 | `--output`, `-o` | `--output`, `-o` |
| Output format | 4/9 | `--output-format`, `--format` | `--output-format` |
| Model selection | 5/9 | `--model`, `-m` | `--model`, `-m` |
| Verbosity | 2/9 | `--verbose`, `--verbosity` `-v` | `--verbosity`, `-v` |

### Action-by-Action Breakdown

#### 1. **count** (9 arguments)
```
--input                  ✓ Standard
--fields                 ✓ Action-specific (space-separated list)
--match-type            ✓ Action-specific
--value                 ✓ Action-specific
--output-format         ✓ Standard (json/csv/tsv)
--output                ✓ Standard
--group-by              ✓ Action-specific
--group-type            ✓ Action-specific
--logic                 ✓ Action-specific
--verbose               ⚠️  Should be --verbosity
--count-type            ✓ Action-specific
--char-limit            ✓ Action-specific
--output-flat           ✓ Action-specific
```

**Issues**:
- Uses `--verbose` (boolean) instead of `--verbosity` (count)
- No short flags for common args

#### 2. **fix_underscores** (4 arguments)
```
--input                 ✓ Standard
--output                ✓ Standard
--prefix                ✓ Action-specific
--depth                 ✓ Action-specific
```

**Issues**: None (simple action)

#### 3. **strip_html** (11 arguments)
```
--input                 ✓ Standard (accepts multiple: nargs="+")
--model, -m             ✓ Standard
--outdir                ⚠️  Differs from --output (directory vs file)
--format                ⚠️  Should be --output-format
--dry-run               ✓ Action-specific
--verbosity, -v         ✓ Standard (count action)
--logfile               ✓ Standard
--pretty                ✓ Action-specific (BooleanOptionalAction)
--set-keys              ✓ Action-specific (BooleanOptionalAction)
--tables                ✓ Action-specific (BooleanOptionalAction)
--colnames              ✓ Action-specific
```

**Issues**:
- `--format` instead of `--output-format`
- `--outdir` instead of `--output` (special case: directory)
- Good: Uses `-v` short flag and count action for verbosity

#### 4. **phrase** (9 arguments)
```
--input, -i             ✓ Standard (has short flag)
--fields, -f            ✓ Action-specific
--min-words             ✓ Action-specific
--min-ids               ✓ Action-specific
--remove-stopwords      ✓ Action-specific
--lemmatize, -l         ✓ Action-specific (BooleanOptionalAction)
--prune, -p             ✓ Action-specific
--output-format         ✓ Standard
--output, -o            ✓ Standard (has short flag)
--verbatim              ✓ Action-specific
```

**Issues**: None (well-structured)

#### 5. **extract_embed** (11 arguments)
```
--input                 ✓ Standard
--id-list               ✓ Action-specific
--id-file               ✓ Action-specific
--id-type               ✓ Action-specific
--output-format         ✓ Standard
-o, --output            ✓ Standard
-m, --model             ✓ Standard
--path-file             ✓ Action-specific
--exclude               ✓ Action-specific (BooleanOptionalAction)
-c, --collapse          ✓ Action-specific (BooleanOptionalAction)
-s, --simplify-permissible  ✓ Action-specific (BooleanOptionalAction)
```

**Issues**: None (well-structured with short flags)

#### 6. **subset** (1 argument)
```
--input                 ✓ Standard
```

**Issues**: Minimally implemented (placeholder action?)

#### 7. **strip_phrases** (9 arguments)
```
-i, --input             ✓ Standard (short flag first)
-m, --model             ✓ Standard
-p, --phrases           ✓ Action-specific
-o, --output            ✓ Standard
-d, --diff              ✓ Action-specific
--diff-output           ✓ Action-specific
-c, --color             ✓ Action-specific
--summary               ✓ Action-specific
-C, --context           ✓ Action-specific
```

**Issues**:
- Inconsistent: short flag before long (`-i, --input` vs `--input, -i`)

#### 8. **lemma_fasta** (11 arguments)
```
--input                 ✓ Standard
--id-list               ✓ Action-specific (mutually exclusive with --id-file)
--id-file               ✓ Action-specific
--id-type               ✓ Action-specific
-o, --output            ✓ Standard
--output-format         ✓ Standard (pfasta/lfasta)
-m, --model             ✓ Standard
--path-file             ✓ Action-specific
--exclude               ✓ Action-specific (BooleanOptionalAction)
--remove-spaces         ✓ Action-specific (BooleanOptionalAction)
--remove-stopwords      ✓ Action-specific
--min-freq              ✓ Action-specific
```

**Issues**: None (well-structured)

#### 9. **phrase_builder** (3 arguments)
```
-i, --input             ✓ Standard
-m, --model             ✓ Standard
-o, --output            ✓ Standard
```

**Issues**: None (minimal but consistent)

---

## Inconsistencies Identified

### 1. Short Flag Convention
- **Inconsistent order**: Some use `-i, --input`, others use `--input, -i`
- **Recommendation**: Always use `--long, -short` format

### 2. Verbosity Handling
- **count** uses `--verbose` (boolean, action="store_true")
- **strip_html** uses `--verbosity, -v` (count action)
- **Recommendation**: Standardize on `--verbosity, -v` with count action

### 3. Output Format Naming
- **Most actions** use `--output-format`
- **strip_html** uses `--format`
- **Recommendation**: Standardize on `--output-format`

### 4. Output Directory vs File
- **Most actions** use `--output` for file path
- **strip_html** uses `--outdir` for directory (special case: batch processing)
- **Recommendation**: Keep `--output` for file, allow `--outdir` as exception

### 5. Boolean Argument Patterns
- **Modern actions** use `BooleanOptionalAction` (--flag / --no-flag)
- **Older actions** use `action="store_true"` (--flag only)
- **Recommendation**: Migrate to `BooleanOptionalAction` for new flags

---

## Standardization Proposal

### Tier 1: Universal Arguments (All Actions)
```python
# Standard Input/Output
--input, -i              # Input JSON file (required unless specified)
--output, -o             # Output file path (optional: defaults to stdout)
--output-format          # Output format: json, csv, tsv (default: json)

# Model Selection (where applicable)
--model, -m              # Pydantic model: CDE, Form, etc.

# Verbosity and Logging
--verbosity, -v          # Verbosity level (action="count": -v, -vv, -vvv)
--logfile                # Optional log file path
```

### Tier 2: Common Action-Specific Patterns
```python
# Field Selection
--fields, -f             # Space-separated list of fields

# ID Filtering
--id-list                # List of IDs (space-separated)
--id-file                # File containing IDs
--id-type                # Type of ID (e.g., tinyId)
--exclude                # Exclude (--exclude) vs include (--no-exclude) IDs

# Phrase Processing
--lemmatize, -l          # Lemmatize text (BooleanOptionalAction)
--remove-stopwords       # Remove stopwords (store_true)
--min-words              # Minimum phrase length
--min-ids                # Minimum number of objects sharing phrase

# Path Specification
--path-file              # File with paths of interest
--group-by               # Field to group results by
--group-type             # Interpretation: top, path, terminal
```

### Tier 3: Action-Specific Arguments
Keep as-is, but follow naming conventions:
- Lowercase with hyphens
- Descriptive names
- Short flags for frequently used args

---

## Shared Argument Groups (Proposed)

Create reusable argument group functions in `utils/cli_args.py`:

```python
# utils/cli_args.py

def add_input_output_args(parser, input_required=True, output_required=False):
    """Add standard input/output arguments"""
    parser.add_argument(
        "--input", "-i",
        required=input_required,
        help="Input JSON file"
    )
    parser.add_argument(
        "--output", "-o",
        required=output_required,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Output format"
    )

def add_model_arg(parser, required=True):
    """Add model selection argument"""
    from utils.constants import MODEL_REGISTRY
    parser.add_argument(
        "--model", "-m",
        required=required,
        choices=MODEL_REGISTRY.keys(),
        help="Pydantic model for validation"
    )

def add_verbosity_args(parser):
    """Add verbosity and logging arguments"""
    parser.add_argument(
        "--verbosity", "-v",
        action="count",
        default=1,
        help="Increase verbosity (-v, -vv, -vvv)"
    )
    parser.add_argument(
        "--logfile",
        help="Optional log file path"
    )

def add_id_filter_args(parser):
    """Add ID filtering arguments"""
    ids = parser.add_mutually_exclusive_group()
    ids.add_argument(
        "--id-list",
        nargs="+",
        help="List of IDs (space-separated)"
    )
    ids.add_argument(
        "--id-file",
        help="File containing list of IDs"
    )
    parser.add_argument(
        "--id-type",
        default="tinyId",
        help="Type of ID (default: tinyId)"
    )
    parser.add_argument(
        "--exclude",
        action=BooleanOptionalAction,
        default=True,
        help="Exclude (--exclude) or include (--no-exclude) IDs"
    )
```

---

## Migration Plan

### Phase 1: Non-Breaking Additions (Immediate)
1. Create `utils/cli_args.py` with shared argument groups
2. Add new standard arguments to actions (keep old ones for compatibility)
3. Document standard arguments in developer guide

### Phase 2: Deprecation Warnings (Next Release)
1. Add deprecation warnings for non-standard argument names
2. Update documentation to show preferred arguments
3. Update examples and help text

### Phase 3: Breaking Changes (Major Version)
1. Remove deprecated argument names
2. Enforce standard naming across all actions
3. Update all documentation

---

## Priority Actions for Immediate Fix

### High Priority (User-Facing Inconsistencies)
1. **count**: Change `--verbose` → `--verbosity, -v` (with count action)
2. **strip_html**: Change `--format` → `--output-format`

### Medium Priority (Internal Inconsistencies)
3. Standardize short flag order: `--long, -short` (not `-short, --long`)
4. Add missing short flags to frequently used arguments:
   - count: Add `-i` for `--input`, `-o` for `--output`

### Low Priority (Nice-to-Have)
5. Migrate old `action="store_true"` to `BooleanOptionalAction` where appropriate
6. Add `--verbosity` and `--logfile` to actions that lack them

---

## Documentation Requirements

### 1. Developer Guide Addition
Create `docs/development/cli-conventions.md`:
- Standard argument naming
- Short flag conventions
- Boolean argument handling
- Argument group usage

### 2. User-Facing Changes
Update `README.md` and help text to reflect standardization

### 3. Migration Guide
For users of deprecated arguments, provide migration guide

---

## Benefits of Standardization

1. **User Experience**: Predictable argument names across actions
2. **Maintainability**: Shared argument groups reduce code duplication
3. **Documentation**: Easier to document common patterns
4. **Testing**: Shared argument groups can be tested once
5. **Extensibility**: New actions can quickly adopt standards

---

## Implementation Checklist

- [ ] Create `utils/cli_args.py` with shared argument groups
- [ ] Update `count` action: `--verbose` → `--verbosity`
- [ ] Update `strip_html` action: `--format` → `--output-format`
- [ ] Add short flags to `count` action
- [ ] Standardize short flag order in all actions
- [ ] Create developer guide for CLI conventions
- [ ] Add deprecation warnings for old argument names
- [ ] Update all documentation and help text
- [ ] Add tests for argument parsing
- [ ] Update CHANGELOG with migration notes

---

## Appendix: Complete Argument Matrix

| Action | Input | Output | Format | Model | Verbosity | Fields | Other Args |
|--------|-------|--------|--------|-------|-----------|--------|------------|
| count | --input | --output | --output-format | - | --verbose ⚠️ | --fields | 7 action-specific |
| fix_underscores | --input | --output | - | - | - | - | 2 action-specific |
| strip_html | --input | --outdir ⚠️ | --format ⚠️ | --model | --verbosity ✓ | - | 7 action-specific |
| phrase | --input, -i ✓ | --output, -o ✓ | --output-format | - | - | --fields, -f | 5 action-specific |
| extract_embed | --input | --output, -o ✓ | --output-format | --model, -m ✓ | - | - | 7 action-specific |
| subset | --input | - | - | - | - | - | 0 (minimal) |
| strip_phrases | --input, -i ✓ | --output, -o ✓ | - | --model, -m ✓ | - | - | 6 action-specific |
| lemma_fasta | --input | --output, -o ✓ | --output-format | --model, -m ✓ | - | - | 7 action-specific |
| phrase_builder | --input, -i ✓ | --output, -o ✓ | - | --model, -m ✓ | - | - | 0 |

**Legend**:
- ✓ = Well-structured
- ⚠️ = Inconsistent with standard
- `-` = Not applicable
