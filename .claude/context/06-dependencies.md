# Dependencies

> **Updated**: v1.0.0 (2026-03-12). Source of truth: `pyproject.toml`.

## Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >=2.0.0,<3.0.0 | Data validation and CDE schema models |
| `spacy` | >=3.7.0,<4.0.0 | NLP: tokenization, lemmatization, POS tagging |
| `nltk` | >=3.8.0,<4.0.0 | Tokenization for k-mer phrase mining |
| `pandas` | >=2.0.0,<3.0.0 | TSV/CSV data manipulation |
| `PyYAML` | >=6.0.0,<7.0.0 | Workflow YAML parsing, config files |
| `beautifulsoup4` | >=4.12.0 | HTML stripping from CDE fields |
| `lxml` | >=4.9.0 | HTML parser backend for BeautifulSoup |
| `rich` | >=13.0.0 | Terminal formatting (progress bars, tables) |
| `wordfreq` | >=3.0.0,<4.0.0 | Zipf frequency scoring for priority split |

## Development Dependencies (`[project.optional-dependencies] dev`)

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=8.0.0 | Test framework |
| `pytest-cov` | >=4.1.0 | Coverage reporting |
| `pytest-mock` | >=3.12.0 | Mock utilities |
| `black` | >=24.0.0 | Code formatting |
| `ruff` | >=0.1.0 | Linting |
| `mypy` | >=1.8.0 | Static type checking |
| `pre-commit` | >=3.6.0 | Git hook management |

## Documentation Dependencies (`[project.optional-dependencies] docs`)

| Package | Version | Purpose |
|---------|---------|---------|
| `sphinx` | >=7.2.0 | Documentation generator |
| `sphinx-rtd-theme` | >=2.0.0 | ReadTheDocs theme |

**Note**: MkDocs is used for the actual documentation site (`mkdocs.yml`), but is not listed as a formal dependency. Install separately: `pip install mkdocs mkdocs-material`.

## Optional / Feature-Gated Dependencies

These are imported lazily and only required for specific actions:

| Package | Required By | Purpose |
|---------|-------------|---------|
| `anthropic` | `llm_classify` | Claude API provider |
| `openai` | `llm_classify` | OpenAI API provider |
| `google-generativeai` | `llm_classify` | Gemini API provider |
| `sentence-transformers` | Knowledge graph (experimental) | Semantic similarity |
| `networkx` | Knowledge graph (experimental) | Graph algorithms |

## spaCy Model

The phrase mining pipeline requires a spaCy language model:

```bash
python -m spacy download en_core_web_sm
```

Used for: tokenization, POS tagging, lemmatization in `phrase_miner` and related actions.

## Python Version

- **Minimum**: Python 3.9 (`requires-python = ">=3.9"`)
- **Tested**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Production environment**: Python 3.13 via WSL Ubuntu-22.04

## Build System

- **Backend**: setuptools >=69.0.0 + wheel >=0.42.0
- **Layout**: Flat (packages at root, not nested under `cde_analyzer/`)
- **Entry point**: `cde-analyzer = "cli:main"`

## Tool Configuration (in `pyproject.toml`)

| Tool | Key Setting |
|------|-------------|
| `black` | `line-length = 100`, excludes legacy kmer files |
| `ruff` | `line-length = 100`, `target-version = "py39"`, rules: E, W, F, I, B, C4, UP |
| `mypy` | `python_version = "3.9"`, `disallow_untyped_defs = false` (gradual) |
| `pytest` | `minversion = "8.0"`, markers: `slow`, `integration` |
| `coverage` | sources: actions, logic, utils, core, CDE_Schema; omits legacy kmer |
