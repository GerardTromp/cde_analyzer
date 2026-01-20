# Architecture

CDE Analyzer uses a **layered monolithic** architecture with a plugin-style action system.

## Design Principles

### 1. Lazy Loading

Actions are loaded only when invoked, providing fast CLI startup regardless of how many actions exist.

```python
# cde_analyzer.py
ACTION_REGISTRY = {
    "phrase_miner": {
        "module": "actions.phrase_miner.cli",
        "help": "Iterative phrase mining using descending k-mers",
        "description": "..."
    },
    # ... other actions
}

# Module loaded only when user selects the action
module = importlib.import_module(registry[action]["module"])
```

**Benefits**:
- Fast startup (no heavy imports on launch)
- Easy to add new actions
- Inspired by git/pip subcommand pattern

### 2. Three-Layer Actions

Each action follows a consistent three-layer structure:

```
actions/<action_name>/
├── __init__.py     # Package marker
├── cli.py          # Layer 1: Argument parsing (launcher)
└── run.py          # Layer 2: Orchestration (I/O, coordination)

logic/
└── <action>.py     # Layer 3: Business logic (algorithms)
```

| Layer | Responsibility | Example |
|-------|----------------|---------|
| **CLI** (`cli.py`) | Argument parsing only | Define `--input`, `--k-max`, etc. |
| **Orchestration** (`run.py`) | File I/O, result formatting | Load JSON, write TSV, call logic |
| **Logic** (`logic/*.py`) | Core algorithms | K-mer counting, phrase detection |

**Benefits**:
- Clear separation of concerns
- Business logic testable without CLI
- Consistent structure across all actions

### 3. Visitor Pattern

A single recursive engine handles all nested data traversal:

```python
# core/recursor.py
def recursive_descent(item, path, visitor, context, depth):
    """
    Traverse nested CDE structures uniformly.

    Args:
        item: Current node (dict, list, or scalar)
        path: Current path (e.g., "designations.*.designation")
        visitor: Callback function for each node
        context: Shared context object
        depth: Current recursion depth
    """
    if isinstance(item, dict):
        for key, value in item.items():
            new_path = f"{path}.{key}" if path else key
            recursive_descent(value, new_path, visitor, context, depth + 1)
    elif isinstance(item, list):
        for i, value in enumerate(item):
            new_path = f"{path}[{i}]"
            recursive_descent(value, new_path, visitor, context, depth + 1)
    else:
        visitor(item, path, context, depth)
```

**Benefits**:
- Single point of traversal logic
- Path tracking provides context
- Separates traversal from processing

## Directory Structure

```
cde_analyzer/
├── cde_analyzer.py          # Entry point with ACTION_REGISTRY
│
├── actions/                 # CLI actions (lazy-loaded)
│   ├── phrase_miner/        # NEW: K-mer phrase mining
│   │   ├── __init__.py
│   │   ├── cli.py           # Argument registration
│   │   └── run.py           # Orchestration
│   ├── phrase/              # Original phrase detection
│   ├── count/               # Field counting
│   ├── extract_embed/       # Embedding extraction
│   ├── fix_underscores/     # Field name fixing
│   ├── strip_html/          # HTML removal
│   └── ...
│
├── logic/                   # Business logic
│   ├── phrase_miner.py      # K-mer mining algorithm
│   ├── phrase_extractor.py  # Original phrase detection
│   ├── counter.py           # Counting logic
│   └── ...
│
├── utils/                   # Utilities
│   ├── phrase_miner_vocab.py # Vocabulary for k-mer mining
│   ├── phrase_extraction.py  # Tokenization, lemmatization
│   ├── helpers.py           # General utilities
│   └── ...
│
├── CDE_Schema/              # Pydantic data models
│   ├── CDE_Item.py          # CDEItem model
│   ├── CDE_Form.py          # CDEForm model
│   └── classes.py           # 50+ supporting models
│
├── core/                    # Core engine
│   └── recursor.py          # Recursive traversal (25 lines)
│
├── tests/                   # Unit tests
│
└── docs/                    # Documentation
    ├── index.md
    ├── commands/
    └── help/
```

## Data Flow

### Typical Action Execution

```
User Command
    │
    ▼
cde_analyzer.py (entry point)
    │
    ├── Parse action name from argv
    ├── Lookup in ACTION_REGISTRY
    └── Import action module (lazy)
          │
          ▼
    actions/<action>/cli.py
          │
          ├── Register arguments
          └── Set func=run_action
                │
                ▼
    actions/<action>/run.py
          │
          ├── Load input JSON
          ├── Call logic functions
          └── Write output files
                │
                ▼
    logic/<action>.py
          │
          ├── Process data
          └── Return results
```

### phrase_miner Data Flow

```
Input JSON                 Tokenization              K-mer Mining
    │                          │                          │
    ▼                          ▼                          ▼
Load CDEItem           Extract text fields        For k=25 to k=3:
objects                Tokenize (NLTK)            - Count k-mers
    │                  Lemmatize (optional)       - Filter by freq/tinyids
    │                  Build vocabulary           - Create phrases
    │                          │                  - Mask tokens
    │                          │                          │
    └──────────────────────────┴──────────────────────────┘
                               │
                               ▼
                        Output TSV files
                        (phrases, occurrences)
```

## Key Technical Decisions

### ADR-001: Pydantic for Data Modeling

- **Context**: NLM CDE API returns complex, nested JSON
- **Decision**: Use Pydantic BaseModel classes
- **Benefits**: Type safety, validation, easy serialization

### ADR-002: Layered Action Architecture

- **Context**: Multiple operations with distinct arguments
- **Decision**: Three-layer CLI → Orchestration → Logic
- **Benefits**: Testable, maintainable, consistent

### ADR-003: Lazy Loading

- **Context**: CLI startup becoming slow
- **Decision**: Import action modules only when invoked
- **Benefits**: Fast startup, easy to extend

### ADR-004: Iterative K-mer Mining (phrase_miner)

- **Context**: Original phrase detection misses longest phrases
- **Decision**: Descending k-mer mining with masking
- **Benefits**: Finds longest phrases first, prevents overlap

## Extension Points

### Adding a New Action

1. Create `actions/<new_action>/` directory
2. Add `__init__.py`, `cli.py`, `run.py`
3. Add business logic to `logic/<new_action>.py`
4. Register in `ACTION_REGISTRY` in `cde_analyzer.py`

### Adding New Data Models

1. Define Pydantic model in `CDE_Schema/`
2. Use Optional fields for sparse data
3. Add field aliases for MongoDB/API name mapping

## Performance Considerations

### Current Bottlenecks

| Operation | Current | Future |
|-----------|---------|--------|
| K-mer masking | O(n×m) naive | O(n+m) Aho-Corasick |
| Large file I/O | Full load | Streaming (planned) |

### Optimization Opportunities

- Phase 4: Aho-Corasick for O(n+m) pattern matching
- Parallel processing for independent CDE records
- Streaming JSON for large files

## Related Documentation

- [Data Models](data-models.md)
- [Commands Overview](commands/index.md)
- [phrase_miner Implementation](commands/phrase_miner.md)
