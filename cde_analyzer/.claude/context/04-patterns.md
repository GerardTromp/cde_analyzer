# Patterns and Conventions

## Design Patterns

### 1. Lazy Loading / Plugin Architecture
**Location**: `cde_analyzer.py`

**Pattern**: Lazy initialization with registry-based dispatch

**Implementation**:
```python
ACTION_REGISTRY = {
    "action_name": {
        "module": "actions.action_name.cli",
        "help": "Short description",
        "description": "Longer description"
    }
}

def load_action_module(module_path: str):
    return importlib.import_module(module_path)

# Only load when user invokes the action
if hasattr(args, "_module_path"):
    module = load_action_module(args._module_path)
    args.func(args)
```

**Benefits**:
- Fast CLI startup (no heavy imports)
- Memory efficient
- Easy to add new actions
- Inspired by git/pip architecture

**Recent Refactoring**: Commit 4400bf7 converted from eager loading to max-lazy loading due to startup performance issues.

### 2. Visitor Pattern
**Location**: `core/recursor.py`

**Pattern**: Recursive visitor for tree traversal

**Implementation**:
```python
def recursive_descent(item, path, visitor, *, context=None, depth=0):
    if isinstance(item, dict):
        for k, v in item.items():
            recursive_descent(v, f"{path}.{k}", visitor, context, depth+1)
    elif isinstance(item, list):
        for elem in item:
            recursive_descent(elem, f"{path}.*", visitor, context, depth+1)
    else:
        visitor(path, item, context)  # Process leaf node
```

**Usage**:
```python
def my_visitor(path, value, context):
    if "designation" in path:
        context['designations'].append(value)

recursive_descent(cde_item, "", my_visitor, context={'designations': []})
```

**Benefits**:
- Single traversal engine for all nested structures
- Path tracking for context
- Separates traversal from processing logic

**Used By**:
- logic/counter.py - Field counting
- logic/phrase_extractor.py - Phrase detection
- logic/html_stripper.py - HTML removal
- Most actions requiring deep traversal

### 3. Three-Layer Action Pattern
**Location**: `actions/*/`

**Pattern**: CLI → Orchestration → Logic separation

**Structure**:
```
actions/<action_name>/
  ├── cli.py         # Argument parsing, no business logic
  ├── run.py         # Orchestration, file I/O, result formatting
  └── __init__.py    # Package marker
```

**cli.py Template**:
```python
def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", help="Input JSON file")
    subparser.add_argument("--output", help="Output file")
    # ... more arguments
    subparser.set_defaults(func=run_action)
```

**run.py Template**:
```python
from .cli import help_text
from logic.<action_logic> import process_data

def run_action(args):
    # 1. Load data
    data = load_json(args.input)

    # 2. Call business logic
    result = process_data(data, args.fields, args.options)

    # 3. Format and write output
    write_output(result, args.output, args.output_format)
```

**Benefits**:
- Clear separation of concerns
- Testable business logic (no CLI dependencies)
- Consistent structure across actions
- Easy to understand and extend

### 4. State Management Pattern
**Location**: `utils/analyzer_state.py`

**Pattern**: Module-level singleton state

**Implementation**:
```python
_verbosity = 1

def set_verbosity(level: int):
    global _verbosity
    _verbosity = level

def get_verbosity() -> int:
    return _verbosity
```

**Usage**:
- Set once in `cde_analyzer.py` main()
- Accessed throughout the application
- Controls logging verbosity

**Rationale**: Avoids passing verbosity through every function call.

### 5. Strategy Pattern (Implicit)
**Location**: `logic/counter.py`

**Pattern**: Different matching strategies for field counting

**Strategies**:
- `non_null`: Field has a value
- `null`: Field is None, "", or []
- `fixed`: Field equals specific value
- `regex`: Field matches regex pattern

**Implementation**:
```python
def match_condition(value, match_type, pattern):
    if value is None or value == "" or value == []:
        return match_type == "null"
    if match_type == "fixed":
        return value == pattern
    if match_type == "regex":
        return bool(re.search(pattern, str(value)))
    return False
```

### 6. Factory Pattern (Implicit)
**Location**: `utils/output_writer.py`

**Pattern**: Format-specific output generation

**Formats**:
- JSON
- CSV
- TSV

**Implementation** (inferred):
```python
def write_output(data, path, format):
    if format == "json":
        write_json(data, path)
    elif format == "csv":
        write_csv(data, path)
    elif format == "tsv":
        write_tsv(data, path)
```

## Coding Conventions

### File Organization

**Standard Structure**:
```
module.py starts with:
  1. Standard library imports
  2. Third-party imports (pydantic, etc.)
  3. Local imports (utils, core, CDE_Schema)
  4. Type aliases (if needed)
  5. Module-level constants
  6. Function/class definitions
```

**Example** (logic/counter.py):
```python
import re
import json
import logging
from collections import defaultdict
from core.recursor import recursive_descent
from typing import TypeAlias, Union, Dict, List
from utils.datatype_check import check_number_type, is_string_shorter
from utils.helpers import safe_nested_increment
from utils.analyzer_state import get_verbosity

IntDict: TypeAlias = Dict[str, int]
NestedDict: TypeAlias = Dict[str, Union[IntDict, "NestedDict"]]

logger = logging.getLogger(__name__)

def match_condition(value, match_type, pattern):
    ...
```

### Naming Conventions

**Files & Directories**:
- Lowercase with underscores: `phrase_extraction.py`, `output_writer.py`
- Action directories: Singular nouns (`count`, `phrase`, not `counts`)

**Functions**:
- Lowercase with underscores: `recursive_descent`, `match_condition`, `find_group_value`
- Verb-noun structure: `load_json`, `write_output`, `check_number_type`

**Classes**:
- PascalCase: `CDEItem`, `ValueDomain`, `RegistrationState`
- Descriptive nouns: `CreatedBy`, `UpdatedBy` (not `Creator`, `Updater`)

**Variables**:
- Lowercase with underscores: `match_type`, `output_format`, `group_by`
- Descriptive: `visitor`, `context`, `path` (not `v`, `ctx`, `p`)

**Constants**:
- UPPERCASE with underscores: `ACTION_REGISTRY`
- Defined at module level

**Private Functions**:
- Leading underscore: `_module_path` (for internal use)
- Not widely used in this codebase

### Argument Naming

**Common CLI Arguments** (should be standardized):
- `--input`: Input JSON file
- `--output`: Output file path
- `--fields`: Field names to process (space-separated list)
- `--output-format`: `{json,csv,tsv}`
- `--verbosity` / `-v`: Logging level
- `--logfile`: Log file path

**Action-Specific Arguments**:
- `--match-type`: Type of matching (count action)
- `--min-words`: Minimum phrase length (phrase action)
- `--lemmatize`: Text normalization (phrase action)
- `--model`: CDE or Form (strip_html action)

**Note from README**: "The project would greatly benefit from consolidating some functions and refactoring to improve consistency of the codebase. For example, the arguments and flags (Boolean arguments) for actions should have identical names, where relevant, and similar names where functionality is semantically related."

### Type Hints

**Usage Pattern**:
- Type hints used for function signatures
- Optional fields in Pydantic models
- Type aliases for complex types

**Examples**:
```python
from typing import List, Optional, Union, Dict, TypeAlias

# Type aliases
IntDict: TypeAlias = Dict[str, int]
NestedDict: TypeAlias = Dict[str, Union[IntDict, "NestedDict"]]

# Function signatures
def find_group_value(
    data: dict,
    group_by: str,
    group_type: str = "top",
    verbose: bool = False
) -> str:
    ...

# Pydantic models
class Source(BaseModel):
    sourceName: Optional[str]
    created: Optional[str] = None
```

### Error Handling

**Logging Over Exceptions**:
- Use `logging` module for messages
- `logger = logging.getLogger(__name__)`
- `logger.info()`, `logger.warning()`, `logger.error()`

**Verbosity-Controlled Logging**:
```python
from utils.logger import log_if_verbose

log_if_verbose(f"[GROUP-BY] top-level '{group_by}' = {value}", 2)
```
- Level 1: Normal output
- Level 2: Debug details
- Level 3+: Verbose debugging

**Error Handling Pattern** (inferred):
- Validate inputs at action orchestration layer (run.py)
- Let Pydantic handle model validation
- Raise RuntimeError for configuration errors (see cde_analyzer.py:133)

### Documentation

**Docstring Style**: Not consistently used in sampled code
- Some files have module-level comments
- Function docstrings appear to be minimal
- Inline comments for complex logic

**Help Text Pattern**:
```python
# In cli.py
help_text = "Short description for --help"
description_text = "Longer description for command overview"
```

**Documentation Files**:
- README.md: User-facing project overview
- docs/help/all-commands.md: CLI reference (generated)
- CLAUDE.md: AI assistant context

## Testing Patterns

**Current State**: Minimal testing infrastructure

**Test Structure**:
- `tests/test_helpers.py` exists
- Uses standard Python unittest or pytest (not determined)

**Needs Expansion**: The README acknowledges "Much more needs to be done on that front."

**Testable Design**:
- Business logic separated from CLI (testable independently)
- Pure functions in utils/ (easy to unit test)
- Visitor pattern allows mock data traversal

## Data Processing Patterns

### 1. Recursive Descent for Nested Data
**All actions** processing CDE data use this pattern:
```python
from core.recursor import recursive_descent

def process_cde(cde_item):
    results = []

    def visitor(path, value, context):
        if meets_criteria(path, value):
            results.append((path, value))

    recursive_descent(cde_item, "", visitor, context={})
    return results
```

### 2. Path-Based Field Selection
**Pattern**: Dot notation with wildcards for nested fields
```python
"designations.*.designation"  # All designation text values
"valueDomain.datatype"         # Specific nested field
"*.tinyId"                     # Any tinyId at any level
```

### 3. Grouping and Aggregation
**Pattern**: Group results by field value
```python
from collections import defaultdict

results = defaultdict(int)

def visitor(path, value, context):
    group_key = find_group_value(data, "tinyId", "top")
    results[group_key] += 1
```

### 4. Multi-Format Output
**Pattern**: Single internal representation, multiple serializations
```python
# Internal: Python dict/list
results = {"field1": 10, "field2": 20}

# Output based on format
if output_format == "json":
    json.dump(results, file, indent=2)
elif output_format == "csv":
    writer.writerows(flatten_dict(results))
```

### 5. Phrase Processing Pipeline
**Pattern**: Multi-stage text processing

**Stages** (inferred from action names):
1. **Extract** (phrase action)
   - Find repeated n-grams
   - Lemmatize text
   - Count occurrences
2. **Build** (phrase_builder action)
   - Incrementally construct phrase models
   - Merge shorter phrases into longer ones
3. **Prune** (utils/phrase_pruning.py)
   - Remove subphrases
   - Apply frequency thresholds
4. **Strip** (strip_phrases action)
   - Remove identified phrases from data
5. **Export** (lemma_fasta action)
   - Convert to FASTA format for bioinformatics tools

### 6. Field Extraction for ML
**Pattern**: Extract specific fields for downstream processing

**Use Case**: `extract_embed` action prepares data for transformer models
```python
# Input: Complex nested CDE structure
# Output: Flat text for embedding
{
    "tinyId": "CDE123",
    "text": "concatenated designation and definition text"
}
```

## Framework-Specific Patterns

### Pydantic Patterns

**1. Optional Everything**:
```python
class MyModel(BaseModel):
    field1: Optional[str] = None
    field2: Optional[int] = None
```
- Handles sparse API responses
- Avoids validation errors

**2. Field Aliases**:
```python
class CDEForm(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    x__v: Optional[int] = None  # Maps to "__v" in API
```
- Handles MongoDB naming (_id)
- Handles Python-incompatible names (__v)

**3. Union Types for Polymorphism**:
```python
class Property(BaseModel):
    value: Union[str, dict]  # Can be simple or nested
```

**4. Self-Referential Models**:
```python
class ElementInner(BaseModel):
    elements: Optional[List[Optional[dict]]]  # Recursive structure
    name: Optional[str]
```

### Argparse Patterns

**1. Subcommand Registration**:
```python
subparsers = parser.add_subparsers(dest="command", required=True)

for action_name, meta in ACTION_REGISTRY.items():
    action_parser = subparsers.add_parser(action_name, help=meta["help"])
    module = load_action_module(meta["module"])
    module.register_subparser(action_parser)
```

**2. Action Function Binding**:
```python
# In cli.py
def register_subparser(subparser):
    subparser.add_argument(...)
    subparser.set_defaults(func=run_action)

# In cde_analyzer.py
args.func(args)  # Calls the bound action function
```

**3. Boolean Flags**:
```python
from argparse import BooleanOptionalAction

subparser.add_argument("--lemmatize", action=BooleanOptionalAction)
# Creates --lemmatize and --no-lemmatize flags
```

**4. Formatter Class**:
```python
action_parser = subparsers.add_parser(
    action_name,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
# Shows default values in help text
```

## Anti-Patterns and Technical Debt

### 1. Duplicated Code in Actions
**Issue**: Each action implements similar I/O patterns
**Evidence**: Multiple `cli.py` files with similar structure
**Recommendation**: Extract common CLI argument sets to shared functions

### 2. Inconsistent Argument Names
**Issue**: Similar functionality uses different argument names across actions
**Evidence**: README note about "consolidating some functions and refactoring"
**Examples**: `--fields` vs `--field`, `--verbose` vs `--verbosity`

### 3. Legacy Kmer Modules
**Issue**: Multiple experimental implementations retained in utils/
**Evidence**: kmer_build_longest_phrases*.py (4 versions!)
**Status**: Noted as "LEGACY" but not removed
**Recommendation**: Archive in separate branch or document why retained

### 4. Minimal Test Coverage
**Issue**: Only test_helpers.py exists
**Impact**: Refactoring risk, potential bugs
**Recommendation**: Add tests for core.recursor, logic modules

### 5. Global State for Verbosity
**Issue**: Module-level mutable state
**Impact**: Potential issues in multi-threaded contexts
**Justification**: CLI tool, single-threaded execution

### 6. Mixed Responsibilities in utils/
**Issue**: Some utils/ files contain business logic (phrase_extraction.py - 9.4 KB)
**Recommendation**: Consider moving complex logic to logic/ directory

## Best Practices Followed

1. **Lazy Loading**: Excellent startup performance
2. **Separation of Concerns**: CLI/Logic/Utils layers
3. **Type Hints**: Good use of typing module
4. **Pydantic Validation**: Strong data modeling
5. **Single Recursive Engine**: DRY principle for traversal
6. **Logging Framework**: Proper use of logging module
7. **Flexible Output Formats**: User choice of JSON/CSV/TSV
