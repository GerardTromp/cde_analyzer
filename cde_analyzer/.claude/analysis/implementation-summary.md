# Implementation Summary: PyPI Packaging Preparation

**Date**: 2026-01-13
**Author**: Claude (AI Assistant)
**Session**: Packaging preparation and CLI standardization for cde_analyzer
**Last Updated**: 2026-01-13 (CLI standardization implementation)

---

## What Was Accomplished

This session focused on preparing the `cde_analyzer` project for PyPI distribution and standardizing CLI arguments across all actions. **CLI standardization has been implemented.**

### 1. CLI Argument Analysis ✅

**File Created**: [`.claude/analysis/cli-argument-audit.md`](.claude/analysis/cli-argument-audit.md)

**Key Findings**:
- Analyzed all 9 actions (count, fix_underscores, strip_html, phrase, extract_embed, subset, strip_phrases, lemma_fasta, phrase_builder)
- Identified 23 unique argument patterns
- Found 4 major inconsistencies:
  1. Verbosity: `--verbose` (boolean) vs `--verbosity, -v` (count)
  2. Output format: `--output-format` vs `--format`
  3. Short flag order: inconsistent (`-i, --input` vs `--input, -i`)
  4. Boolean patterns: mix of `store_true` and `BooleanOptionalAction`

**Recommendations**:
- Standardize on `--verbosity, -v` with count action
- Use `--output-format` consistently
- Always use `--long, -short` order
- Migrate to `BooleanOptionalAction` for new flags
- Create shared argument groups in `utils/cli_args.py`

### 1b. CLI Argument Standardization Implementation ✅

**Status**: **COMPLETED** (2026-01-13)

**Changes Made**:

1. **`actions/count/cli.py`** - Updated verbosity argument
   - Changed: `--verbose` (store_true) → `--verbosity, -v` (count, default=0)
   - Now consistent with main launcher and other actions
   - Supports `-v`, `-vv`, `-vvv` for increasing verbosity levels

2. **`actions/strip_html/cli.py`** - Standardized output format argument
   - Changed: `--format` → `--output-format`
   - Updated `run.py` to use `args.output_format`
   - Now consistent with other actions (count, phrase, etc.)

3. **`actions/strip_phrases/cli.py`** - Reordered short flags
   - Changed all arguments from `-short, --long` to `--long, -short` pattern
   - Affected arguments: `--input, -i`, `--model, -m`, `--phrases, -p`, `--output, -o`, `--diff, -d`, `--color, -c`, `--context, -C`
   - Now consistent with project-wide standard

4. **`utils/cli_args.py`** - Created shared argument group library
   - New file with 7 reusable argument group functions:
     - `add_input_output_args()` - Standard input/output/format arguments
     - `add_verbosity_args()` - Verbosity and logging arguments
     - `add_model_arg()` - Pydantic model selection
     - `add_field_args()` - Field name list arguments
     - `add_match_args()` - Field matching/filtering arguments
     - `add_pretty_print_args()` - JSON formatting arguments
     - `add_dry_run_arg()` - Dry run testing argument
   - All functions follow consistent naming and help text patterns
   - Exported via `utils/__init__.py` for easy import

5. **`utils/__init__.py`** - Updated exports
   - Added all 7 CLI argument group functions to `__all__`
   - Functions now available for future action refactoring

6. **`CHANGELOG.md`** - Documented breaking changes
   - Added **BREAKING** tags for `count` and `strip_html` changes
   - Documented all standardization work in [Unreleased] section

**Migration Notes for Users**:
- `count` action: Users must change `--verbose` to `--verbosity` or `-v`
- `strip_html` action: Users must change `--format` to `--output-format`
- All short flags still work the same, just reordered in `--help` output

**Future Work**:
- Actions can now be refactored to use shared argument groups from `utils/cli_args.py`
- Will reduce code duplication and ensure ongoing consistency
- Recommended for next version (0.3.0)

### 2. Dependency Analysis ✅

**Files Created**:
- [`requirements.txt`](../requirements.txt) - Production dependencies
- [`requirements-dev.txt`](../requirements-dev.txt) - Development dependencies

**Dependencies Identified**:

**Production** (4 external libraries):
1. `pydantic>=2.11.0,<3.0.0` - **CRITICAL** - Data modeling
2. `spacy>=3.8.0,<4.0.0` - **HIGH** - Lemmatization/NLP
3. `nltk>=3.9.0,<4.0.0` - **HIGH** - Text processing
4. `pandas>=2.0.0,<3.0.0` - **MEDIUM** - Data manipulation (phrase_builder)
5. `PyYAML>=6.0.0,<7.0.0` - **LOW** - YAML output format

**Development** (11 libraries):
- Testing: pytest, pytest-cov, pytest-mock
- Code quality: black, ruff, mypy, pre-commit
- Documentation: sphinx, sphinx-rtd-theme
- Build/deploy: build, twine, setuptools, wheel
- Dev tools: ipython, jupyter

**Verified Installed Versions**:
- Python: 3.13.4
- pydantic: 2.11.5
- spacy: 3.8.7
- nltk: 3.9.1
- PyYAML: 6.0.2
- pandas: Not installed (optional, used only in phrase_builder)

### 3. PyPI Packaging Configuration ✅

**File Created**: [`pyproject.toml`](../pyproject.toml)

**Key Configuration**:
- **Package name**: `cde-analyzer`
- **Version**: 0.2.0
- **License**: MIT
- **Python**: >=3.9 (supports 3.9 through 3.13)
- **Entry point**: `cde-analyzer` command → `cde_analyzer:main`
- **Build system**: setuptools>=69.0.0

**Configured Tools**:
- Black: line-length=100, excludes legacy kmer files
- Ruff: Python 3.9+ linting, excludes legacy files
- MyPy: Type checking with external library ignores
- Pytest: Coverage reporting, test discovery

**Package Metadata**:
- Proper classifiers for PyPI discoverability
- Development status: Beta
- Audience: Science/Research, Healthcare
- Topic: Medical Science, Text Processing

### 4. Package Structure Files ✅

**Created**:
- `cde_analyzer/__version__.py` - Version metadata
- `core/__init__.py` - Exports `recursive_descent`
- `logic/__init__.py` - Exports main logic functions
- `utils/__init__.py` - Exports common utilities
- `LICENSE` - MIT License
- `CHANGELOG.md` - Version history and migration guides
- `MANIFEST.in` - Distribution file inclusion rules

**Already Existed**:
- `CDE_Schema/__init__.py` - Comprehensive exports (already good!)
- `actions/__init__.py` - Actions package init

**Updated**:
- `.gitignore` - Added Python build artifacts, virtual envs, test artifacts

### 5. Documentation ✅

**Files Created**:
- [`.claude/analysis/packaging-plan.md`](.claude/analysis/packaging-plan.md) - Comprehensive packaging roadmap
- [`.claude/analysis/cli-argument-audit.md`](.claude/analysis/cli-argument-audit.md) - CLI standardization analysis
- This file: Implementation summary

**Documentation Contents**:
- Complete PyPI publishing process
- Phase-by-phase implementation plan
- Pre-publication checklist
- Testing strategy
- CI/CD recommendations
- Risk mitigation strategies

---

## File Summary

### New Files (11 total)

| File | Purpose | Status |
|------|---------|--------|
| `requirements.txt` | Production dependencies | ✅ Complete |
| `requirements-dev.txt` | Development dependencies | ✅ Complete |
| `pyproject.toml` | PyPI package metadata | ✅ Complete |
| `cde_analyzer/__version__.py` | Version management | ✅ Complete |
| `core/__init__.py` | Package initialization | ✅ Complete |
| `logic/__init__.py` | Package initialization | ✅ Complete |
| `utils/__init__.py` | Package initialization | ✅ Complete |
| `LICENSE` | MIT License | ✅ Complete |
| `CHANGELOG.md` | Version history | ✅ Complete |
| `MANIFEST.in` | Distribution files | ✅ Complete |
| `.claude/analysis/` (3 docs) | Analysis & planning | ✅ Complete |

### Modified Files (1 total)

| File | Changes | Status |
|------|---------|--------|
| `.gitignore` | Added build artifacts | ✅ Complete |

---

## Next Steps

### Immediate Actions (Before Publishing)

1. **Test Installation Locally**
   ```bash
   # Build the package
   python -m build

   # Install locally
   pip install dist/cde_analyzer-0.2.0-py3-none-any.whl

   # Test the command
   cde-analyzer --help
   ```

2. **Verify Entry Point**
   ```bash
   # Make sure this works after install:
   cde-analyzer count --help
   cde-analyzer phrase --help
   ```

3. **Check Package Contents**
   ```bash
   # List package contents
   unzip -l dist/cde_analyzer-0.2.0-py3-none-any.whl
   ```

### Short-Term Actions (Next 1-2 Weeks)

4. **CLI Argument Standardization**
   - Update `count` action: `--verbose` → `--verbosity, -v`
   - Update `strip_html` action: `--format` → `--output-format`
   - Add short flags to frequently used arguments
   - Create `utils/cli_args.py` with shared argument groups

5. **Testing Expansion**
   - Write tests for `core/recursor.py`
   - Write tests for each action's logic layer
   - Add integration tests
   - Aim for >80% code coverage

6. **Code Quality**
   ```bash
   # Run formatters and linters
   black cde_analyzer/
   ruff check cde_analyzer/
   mypy cde_analyzer/
   ```

7. **Documentation Updates**
   - Update README.md with installation instructions
   - Add usage examples
   - Create CONTRIBUTING.md

### Medium-Term Actions (Next Month)

8. **CI/CD Setup**
   - Create `.github/workflows/test.yml` for automated testing
   - Create `.github/workflows/publish.yml` for PyPI publishing
   - Set up pre-commit hooks

9. **Test PyPI**
   ```bash
   # Upload to Test PyPI first
   twine upload --repository testpypi dist/*

   # Test installation
   pip install --index-url https://test.pypi.org/simple/ cde-analyzer
   ```

10. **Production PyPI**
    ```bash
    # After thorough testing, publish to PyPI
    twine upload dist/*
    ```

---

## Installation Methods (Post-Publishing)

### For End Users
```bash
pip install cde-analyzer
```

### For Developers
```bash
git clone https://github.com/gtromp/cde-analyzer.git
cd cde-analyzer
pip install -e .[dev]
```

### Using the Package
```bash
# After installation, command is available globally:
cde-analyzer count --input data.json --fields tinyId --output-format csv
cde-analyzer phrase --input data.json --fields designations --min-words 3
```

---

## CLI Argument Standardization Plan

### High Priority Fixes

1. **count action** - Change verbosity handling:
   ```python
   # OLD (incorrect):
   subparser.add_argument("--verbose", action="store_true")

   # NEW (correct):
   subparser.add_argument("--verbosity", "-v", action="count", default=1)
   ```

2. **strip_html action** - Change format argument:
   ```python
   # OLD (inconsistent):
   subparser.add_argument("--format", choices=["json", "yaml", "csv"])

   # NEW (consistent):
   subparser.add_argument("--output-format", choices=["json", "yaml", "csv"])
   ```

3. **Standardize short flag order** - Use `--long, -short`:
   ```python
   # CORRECT:
   subparser.add_argument("--input", "-i")
   subparser.add_argument("--output", "-o")

   # INCORRECT (don't use):
   subparser.add_argument("-i", "--input")
   ```

### Shared Argument Groups (Proposed)

Create `utils/cli_args.py`:
```python
from argparse import ArgumentParser, BooleanOptionalAction

def add_input_output_args(parser, input_required=True):
    """Standard input/output arguments"""
    parser.add_argument("--input", "-i", required=input_required,
                       help="Input JSON file")
    parser.add_argument("--output", "-o",
                       help="Output file (default: stdout)")
    parser.add_argument("--output-format",
                       choices=["json", "csv", "tsv"],
                       default="json")

def add_verbosity_args(parser):
    """Standard verbosity and logging"""
    parser.add_argument("--verbosity", "-v", action="count", default=1,
                       help="Increase verbosity (-v, -vv, -vvv)")
    parser.add_argument("--logfile", help="Optional log file path")
```

---

## Known Issues and TODOs

### Issues to Address
- [ ] **pandas dependency**: phrase_builder requires pandas but it's not installed
  - Option 1: Make pandas required
  - Option 2: Make phrase_builder optional (raise ImportError if pandas missing)
  - Option 3: Remove phrase_builder from main distribution

- [ ] **spaCy models**: Users need to download language models separately
  - Add to README: `python -m spacy download en_core_web_sm`
  - Consider post-install script

- [ ] **Legacy kmer files**: Decide on handling
  - Option 1: Keep in git, exclude from distribution (via MANIFEST.in)
  - Option 2: Move to separate `legacy/` directory
  - Option 3: Remove and preserve in git history

### Documentation TODOs
- [ ] Update README.md with PyPI installation instructions
- [ ] Add usage examples to README
- [ ] Create CONTRIBUTING.md for contributors
- [ ] Add API documentation (Sphinx)
- [ ] Create user guide with common workflows

### Testing TODOs
- [ ] Write tests for core/recursor.py
- [ ] Write tests for logic/counter.py
- [ ] Write tests for logic/phrase_extractor.py
- [ ] Write tests for each action
- [ ] Add integration tests
- [ ] Set up test fixtures with sample CDE data

### Quality TODOs
- [ ] Run black and fix formatting
- [ ] Run ruff and fix linting issues
- [ ] Run mypy and fix type errors
- [ ] Set up pre-commit hooks
- [ ] Add docstrings to public APIs

---

## Dependencies Decision

### pandas Handling

**Issue**: `logic/phrase_builder.py` imports pandas, but many users won't need it.

**Recommendation**: Make pandas an optional dependency

**Implementation**:
```toml
# In pyproject.toml
[project.optional-dependencies]
phrase-builder = ["pandas>=2.0.0,<3.0.0"]
```

**Installation**:
```bash
# Basic install (without phrase_builder)
pip install cde-analyzer

# With phrase_builder support
pip install cde-analyzer[phrase-builder]
```

**Code Change** (in `logic/phrase_builder.py`):
```python
try:
    import pandas as pd
except ImportError:
    raise ImportError(
        "phrase_builder requires pandas. Install with: "
        "pip install cde-analyzer[phrase-builder]"
    )
```

---

## Success Metrics

### Pre-Publication (Current Phase)
- [x] Requirements files created
- [x] pyproject.toml configured
- [x] Package structure complete
- [x] License added
- [x] Changelog created
- [ ] Local build successful
- [ ] Local installation successful
- [ ] CLI entry point works

### Publication Phase
- [ ] Test PyPI upload successful
- [ ] Test installation from Test PyPI works
- [ ] Production PyPI upload successful
- [ ] Package discoverable on PyPI

### Post-Publication
- [ ] Installation instructions in README
- [ ] Documentation site live
- [ ] CI/CD pipeline operational
- [ ] First GitHub star received
- [ ] First PyPI download recorded

---

## Commands Reference

### Build and Test
```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Check distribution
twine check dist/*

# Install locally for testing
pip install dist/cde_analyzer-0.2.0-py3-none-any.whl

# Test entry point
cde-analyzer --help
```

### Publishing
```bash
# Test PyPI
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*
```

### Development
```bash
# Install in editable mode with dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Code quality
black cde_analyzer/
ruff check cde_analyzer/
mypy cde_analyzer/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

---

## Questions for User

Before proceeding with packaging, please decide on:

1. **pandas dependency**: Required, optional, or remove phrase_builder?
2. **Legacy kmer files**: Keep in distribution or exclude?
3. **Package name**: Is `cde-analyzer` available on PyPI? (need to check)
4. **Author email**: Update `gerard.tromp@example.com` to real email?
5. **GitHub repository**: What's the actual repository URL?
6. **spaCy models**: Should we provide post-install script?

---

## Repository Status

### Branch: Repeats (Current)
- All packaging files created on this branch
- Ready to merge to main after testing

### Recommended Git Workflow
```bash
# Current state: On Repeats branch with new files

# Option 1: Merge to main
git checkout main
git merge Repeats

# Option 2: Create packaging branch
git checkout -b packaging
git add requirements.txt requirements-dev.txt pyproject.toml ...
git commit -m "Add PyPI packaging configuration"
git push origin packaging
# Then create PR: packaging → main
```

---

## Conclusion

The `cde_analyzer` project is now **ready for PyPI packaging** with all essential configuration files created AND **CLI arguments standardized**. The next critical steps are:

1. **Test the build locally** to ensure everything works
2. **Test CLI changes** to verify standardized arguments work correctly
3. **Fix pandas dependency** (make optional or required)
4. ~~**Standardize CLI arguments** for consistency~~ ✅ **COMPLETED**
5. **Expand test coverage** before publishing
6. **Publish to Test PyPI** for validation
7. **Publish to production PyPI** after thorough testing

All documentation has been created to guide through each phase of the packaging and deployment process.

---

## Files Created This Session

**Configuration Files**:
- requirements.txt
- requirements-dev.txt
- pyproject.toml
- MANIFEST.in

**Package Structure**:
- cde_analyzer/__version__.py
- core/__init__.py
- logic/__init__.py
- utils/__init__.py
- utils/cli_args.py *(NEW - CLI argument groups)*

**Documentation**:
- LICENSE
- CHANGELOG.md
- PACKAGING_QUICKSTART.md
- .claude/analysis/cli-argument-audit.md
- .claude/analysis/packaging-plan.md
- .claude/analysis/implementation-summary.md (this file)

**Updated Files**:
- .gitignore
- actions/count/cli.py *(standardized --verbosity)*
- actions/strip_html/cli.py *(standardized --output-format)*
- actions/strip_html/run.py *(updated to use args.output_format)*
- actions/strip_phrases/cli.py *(reordered short flags)*
- utils/__init__.py *(exported CLI argument functions)*
- CHANGELOG.md *(documented breaking changes)*

**Total**: 16 files created, 8 files modified = **24 files touched**

---

**End of Summary**
