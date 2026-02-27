# Contributing

Guidelines for contributing to CDE Analyzer.

## Development Setup

### Prerequisites

- Python 3.8+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/cde-clustering.git
cd cde-clustering/cde_analyzer

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install pydantic nltk

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"
```

## Project Structure

```
cde_analyzer/
├── cde_analyzer.py      # Entry point
├── actions/             # CLI actions
├── logic/               # Business logic
├── utils/               # Utilities
├── CDE_Schema/          # Data models
├── core/                # Core engine
├── tests/               # Unit tests
└── docs/                # Documentation
```

## Adding a New Action

### 1. Create Action Directory

```bash
mkdir -p actions/my_action
touch actions/my_action/__init__.py
```

### 2. Create CLI Module

```python
# actions/my_action/cli.py
"""
My Action - Brief description.

Detailed description of what the action does.
"""

from argparse import ArgumentParser
from .run import run_action

help_text = "Brief help text for --help listing"
description_text = __doc__


def register_subparser(subparser: ArgumentParser):
    """Register arguments for my_action."""

    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSON file"
    )

    subparser.add_argument(
        "--output", "-o",
        default="output.json",
        help="Output file (default: output.json)"
    )

    # Add more arguments...

    subparser.set_defaults(func=run_action)
```

### 3. Create Orchestration Module

```python
# actions/my_action/run.py
"""Orchestration layer for my_action."""

import json
import logging
from argparse import Namespace
from typing import List

from CDE_Schema.CDE_Item import CDEItem
from logic.my_action import process_items  # Your business logic

logger = logging.getLogger(__name__)


def run_action(args: Namespace) -> int:
    """
    Execute my_action.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Load input
    logger.info(f"Loading input from {args.input}")
    with open(args.input) as f:
        data = json.load(f)

    items = [CDEItem.model_validate(item) for item in data]
    logger.info(f"Loaded {len(items)} CDE items")

    # Process
    results = process_items(items)

    # Write output
    logger.info(f"Writing output to {args.output}")
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    return 0
```

### 4. Create Business Logic

```python
# logic/my_action.py
"""Business logic for my_action."""

from typing import List, Dict, Any
from CDE_Schema.CDE_Item import CDEItem


def process_items(items: List[CDEItem]) -> Dict[str, Any]:
    """
    Process CDE items.

    Args:
        items: List of CDEItem objects

    Returns:
        Processing results
    """
    results = {}

    for item in items:
        # Your algorithm here
        pass

    return results
```

### 5. Register in ACTION_REGISTRY

```python
# cde_analyzer.py
ACTION_REGISTRY = {
    # ... existing actions ...

    "my_action": {
        "module": "actions.my_action.cli",
        "help": "Brief help text",
        "description": "Detailed description"
    },
}
```

## Code Style

### General Guidelines

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions focused and small

### Example

```python
def extract_phrases(
    text: str,
    min_length: int = 2,
    max_length: int = 10
) -> List[str]:
    """
    Extract phrases from text.

    Args:
        text: Input text to process
        min_length: Minimum phrase length in words
        max_length: Maximum phrase length in words

    Returns:
        List of extracted phrases

    Raises:
        ValueError: If min_length > max_length
    """
    if min_length > max_length:
        raise ValueError(f"min_length ({min_length}) > max_length ({max_length})")

    # Implementation...
    return phrases
```

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_my_action.py

# Run with coverage
python -m pytest --cov=. tests/
```

### Writing Tests

```python
# tests/test_my_action.py
import pytest
from logic.my_action import process_items
from CDE_Schema.CDE_Item import CDEItem


def test_process_items_basic():
    """Test basic processing."""
    items = [
        CDEItem(tinyId="test1", designations=[...]),
        CDEItem(tinyId="test2", designations=[...]),
    ]

    results = process_items(items)

    assert "test1" in results
    assert "test2" in results


def test_process_items_empty():
    """Test with empty input."""
    results = process_items([])
    assert results == {}
```

## Documentation

### Building Docs

```bash
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

### Documentation Structure

```
docs/
├── index.md              # Home page
├── commands/             # Command documentation
│   ├── index.md
│   └── my_action.md
├── help/                 # CLI reference
├── architecture.md
└── data-models.md
```

## Git Workflow

### Branches

- `main` - Stable release
- `feature/*` - New features
- `fix/*` - Bug fixes

### Commits

Use descriptive commit messages:

```bash
# Good
git commit -m "Add phrase_miner action with iterative k-mer detection"

# Bad
git commit -m "Added stuff"
```

### Pull Requests

1. Create feature branch
2. Make changes
3. Run tests
4. Update documentation
5. Submit PR with description

## Questions?

- Open an issue on GitHub
- Check existing documentation
