# CDE Analyzer - PyPI Packaging and Deployment Plan

**Date**: 2026-01-13
**Version**: 0.2.0 (proposed)
**Status**: Ready for implementation

---

## Executive Summary

This document outlines the complete plan to convert `cde_analyzer` from a local script-based tool to a pip-installable PyPI package.

**Goals**:
1. Enable `pip install cde-analyzer`
2. Provide `cde-analyzer` command-line entry point
3. Support both local development and production installation
4. Maintain backward compatibility
5. Prepare for future 1.0.0 release

---

## Current State Analysis

### What Exists
✅ Python package structure (cde_analyzer/)
✅ Modular action-based architecture
✅ Lazy loading for fast startup
✅ Main entry point with `main()` function
✅ Pydantic data models
✅ Unit test structure (minimal)

### What's Missing
❌ No requirements.txt or pyproject.toml
❌ No package metadata
❌ No installation instructions
❌ No version management
❌ No distribution configuration
❌ No CI/CD pipeline
❌ No comprehensive tests

### What's Been Created (This Session)
✅ `requirements.txt` - Production dependencies
✅ `requirements-dev.txt` - Development dependencies
✅ `pyproject.toml` - Modern Python packaging metadata
✅ CLI argument standardization audit
✅ This packaging plan

---

## Package Structure

### Proposed Directory Tree
```
cde_analyzer/
├── pyproject.toml          # ✅ Created - Package metadata
├── requirements.txt        # ✅ Created - Production deps
├── requirements-dev.txt    # ✅ Created - Dev deps
├── setup.py               # ⏭️  Optional - Legacy support
├── MANIFEST.in            # 📝 TODO - Include non-Python files
├── LICENSE                # 📝 TODO - License file
├── README.md              # ✅ Exists - Needs update
├── CHANGELOG.md           # 📝 TODO - Version history
├── .gitignore             # ✅ Exists
├── cde_analyzer.py        # ✅ Exists - Entry point
├── CDE_Schema/            # ✅ Exists
│   ├── __init__.py       # 📝 TODO - Package init
│   ├── CDE_Item.py
│   ├── CDE_Form.py
│   └── classes.py
├── actions/               # ✅ Exists
│   ├── __init__.py       # 📝 TODO - Package init
│   ├── count/
│   ├── phrase/
│   └── ...
├── core/                  # ✅ Exists
│   ├── __init__.py       # 📝 TODO - Package init
│   └── recursor.py
├── logic/                 # ✅ Exists
│   ├── __init__.py       # 📝 TODO - Package init
│   └── ...
├── utils/                 # ✅ Exists
│   ├── __init__.py       # 📝 TODO - Package init
│   └── ...
├── tests/                 # ✅ Exists - Needs expansion
│   ├── __init__.py
│   └── test_*.py
└── docs/                  # ✅ Exists - Needs expansion
    └── ...
```

---

## Dependencies

### Production Dependencies (requirements.txt)

**Core (CRITICAL)**:
- `pydantic>=2.11.0,<3.0.0` - Data modeling and validation

**NLP (HIGH - for phrase actions)**:
- `spacy>=3.8.0,<4.0.0` - Lemmatization and NLP
- `nltk>=3.9.0,<4.0.0` - Text processing

**Data Processing (MEDIUM - for phrase_builder)**:
- `pandas>=2.0.0,<3.0.0` - Data manipulation

**Format Support (LOW)**:
- `PyYAML>=6.0.0,<7.0.0` - YAML output format

**Standard Library (No installation needed)**:
- argparse, json, csv, re, collections, logging, pathlib, typing, importlib, etc.

### Development Dependencies (requirements-dev.txt)

**Testing**:
- pytest>=8.0.0
- pytest-cov>=4.1.0
- pytest-mock>=3.12.0

**Code Quality**:
- black>=24.0.0 (formatting)
- ruff>=0.1.0 (linting)
- mypy>=1.8.0 (type checking)
- pre-commit>=3.6.0 (git hooks)

**Documentation**:
- sphinx>=7.2.0
- sphinx-rtd-theme>=2.0.0

**Build/Deploy**:
- build>=1.0.0
- twine>=5.0.0
- setuptools>=69.0.0
- wheel>=0.42.0

### Optional Dependencies

Consider creating optional dependency groups in pyproject.toml:

```toml
[project.optional-dependencies]
dev = [...]           # Development tools
docs = [...]          # Documentation generation
ml = [               # Machine learning features
    "scikit-learn>=1.3.0",
    "torch>=2.0.0",
]
viz = [              # Visualization
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
]
```

---

## Version Management

### Versioning Strategy

Use **Semantic Versioning** (SemVer): `MAJOR.MINOR.PATCH`

**Current Proposal**: `0.2.0` (pre-1.0 beta)

**Version History**:
- `0.1.0` - Initial implementation (pre-lazy loading)
- `0.2.0` - Lazy loading refactoring + PyPI packaging (current)
- `0.3.0` - CLI argument standardization
- `0.4.0` - Comprehensive testing
- `0.5.0` - Documentation complete
- `1.0.0` - Stable release

### Version File

Create `cde_analyzer/__version__.py`:
```python
__version__ = "0.2.0"
__author__ = "Gerard Tromp"
__email__ = "gerard.tromp@example.com"
```

Update `cde_analyzer.py` to import:
```python
from cde_analyzer.__version__ import __version__
```

---

## Package Metadata (pyproject.toml)

**Created**: ✅ `pyproject.toml`

**Key Sections**:
1. `[build-system]` - Build requirements
2. `[project]` - Package metadata
3. `[project.scripts]` - Entry point: `cde-analyzer`
4. `[project.optional-dependencies]` - Dev/docs extras
5. `[tool.setuptools]` - Package configuration
6. `[tool.black]` / `[tool.ruff]` / `[tool.mypy]` - Tool configs
7. `[tool.pytest]` - Test configuration

---

## Installation Methods

### For End Users

**From PyPI (after publishing)**:
```bash
# Basic installation
pip install cde-analyzer

# With optional dependencies
pip install cde-analyzer[ml,viz]

# Specific version
pip install cde-analyzer==0.2.0
```

### For Developers

**Editable installation**:
```bash
# Clone repository
git clone https://github.com/gtromp/cde-analyzer.git
cd cde-analyzer

# Install in editable mode with dev dependencies
pip install -e .[dev]

# Or using requirements files
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### For Contributors

```bash
# Install with pre-commit hooks
pip install -e .[dev]
pre-commit install

# Run tests
pytest

# Run linting
ruff check .
black --check .
mypy cde_analyzer/
```

---

## Entry Point Configuration

### Command-Line Entry Point

**Configured in pyproject.toml**:
```toml
[project.scripts]
cde-analyzer = "cde_analyzer:main"
```

**What this does**:
- Creates `cde-analyzer` command in PATH
- Calls `main()` function from `cde_analyzer.py`
- Works on all platforms (Windows, Linux, macOS)

**Usage after installation**:
```bash
# Instead of: python cde_analyzer.py count --input data.json
# Users can run: cde-analyzer count --input data.json
```

---

## Build and Distribution

### Building the Package

**Using modern build tool**:
```bash
# Install build tool
pip install build

# Build distribution packages
python -m build

# Creates:
# dist/cde_analyzer-0.2.0-py3-none-any.whl
# dist/cde_analyzer-0.2.0.tar.gz
```

### Testing the Build Locally

```bash
# Install from local wheel
pip install dist/cde_analyzer-0.2.0-py3-none-any.whl

# Test the command
cde-analyzer --help
cde-analyzer count --help
```

### Publishing to PyPI

**Test PyPI first (recommended)**:
```bash
# Install twine
pip install twine

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ cde-analyzer
```

**Production PyPI**:
```bash
# Upload to PyPI
twine upload dist/*

# Verify
pip install cde-analyzer
```

---

## Pre-Publication Checklist

### Code Preparation
- [ ] Add `__init__.py` to all packages (CDE_Schema, actions, core, logic, utils)
- [ ] Create `__version__.py` with version info
- [ ] Update `cde_analyzer.py` to use version from `__version__.py`
- [ ] Add `py.typed` marker file for type hint support
- [ ] Clean up or remove legacy kmer files (or document as legacy)

### Documentation
- [ ] Update README.md with installation instructions
- [ ] Create CHANGELOG.md with version history
- [ ] Add LICENSE file (MIT or appropriate)
- [ ] Create CONTRIBUTING.md for contributors
- [ ] Update docstrings in public APIs
- [ ] Add examples/ directory with usage examples

### Testing
- [ ] Expand test coverage (currently minimal)
- [ ] Add tests for core/recursor.py
- [ ] Add tests for each action
- [ ] Add integration tests
- [ ] Set up CI/CD (GitHub Actions)
- [ ] Achieve >80% code coverage

### Quality Checks
- [ ] Run black formatting: `black cde_analyzer/`
- [ ] Run ruff linting: `ruff check cde_analyzer/`
- [ ] Run mypy type checking: `mypy cde_analyzer/`
- [ ] Fix all errors and warnings
- [ ] Set up pre-commit hooks

### Metadata
- [ ] Choose appropriate license (MIT recommended)
- [ ] Set correct author email in pyproject.toml
- [ ] Update GitHub repository URL
- [ ] Add project keywords for discoverability
- [ ] Write clear package description

---

## Post-Publication Tasks

### Documentation Site
- [ ] Set up ReadTheDocs or GitHub Pages
- [ ] Generate Sphinx documentation
- [ ] Add API reference
- [ ] Add user guide with examples
- [ ] Add developer guide

### CI/CD Pipeline
- [ ] GitHub Actions workflow for tests
- [ ] Automatic version bumping
- [ ] Automatic PyPI publishing on release
- [ ] Code quality checks on PR

### Maintenance
- [ ] Set up issue templates
- [ ] Create pull request template
- [ ] Define release process
- [ ] Set up security scanning (Dependabot)
- [ ] Monitor PyPI download stats

---

## Implementation Phases

### Phase 1: Immediate (Pre-Publishing)
**Duration**: 1-2 weeks
**Goal**: Prepare package for PyPI

Tasks:
1. ✅ Create pyproject.toml (DONE)
2. ✅ Create requirements.txt (DONE)
3. ✅ Create requirements-dev.txt (DONE)
4. Add `__init__.py` files to all packages
5. Create `__version__.py`
6. Add LICENSE file
7. Update README.md
8. Create CHANGELOG.md
9. Create MANIFEST.in for non-Python files

### Phase 2: Testing and Quality (Week 3-4)
**Goal**: Ensure package quality

Tasks:
1. Expand test coverage to >80%
2. Set up pre-commit hooks
3. Run and fix all linting issues
4. Run and fix all type checking issues
5. Test local installation
6. Test on clean Python environment

### Phase 3: Documentation (Week 5)
**Goal**: Comprehensive documentation

Tasks:
1. Update README with installation instructions
2. Add usage examples
3. Create CONTRIBUTING.md
4. Add docstrings to public APIs
5. Set up Sphinx documentation

### Phase 4: Publishing (Week 6)
**Goal**: Publish to PyPI

Tasks:
1. Build distribution packages
2. Test on Test PyPI
3. Publish to PyPI
4. Announce release
5. Update documentation with installation instructions

### Phase 5: Post-Publication (Ongoing)
**Goal**: Maintain and improve

Tasks:
1. Set up CI/CD pipeline
2. Monitor issues and PRs
3. Regular dependency updates
4. Feature enhancements
5. Bug fixes

---

## Backward Compatibility

### Maintaining Script Usage

Users who currently run `python cde_analyzer.py` should continue to work:

**Keep these files**:
- `cde_analyzer.py` - Entry point script (keep in root)
- Existing directory structure

**Migration path**:
1. Old way still works: `python cde_analyzer.py count --input data.json`
2. New way after install: `cde-analyzer count --input data.json`
3. Document both in README

### Deprecation Strategy

For future breaking changes:
1. Announce deprecation in CHANGELOG
2. Add deprecation warnings in code
3. Maintain backward compatibility for 1+ major versions
4. Remove in next major version

---

## File Checklist

### Must Create
- [ ] `CDE_Schema/__init__.py`
- [ ] `actions/__init__.py`
- [ ] `core/__init__.py`
- [ ] `logic/__init__.py`
- [ ] `utils/__init__.py`
- [ ] `cde_analyzer/__version__.py`
- [ ] `LICENSE`
- [ ] `CHANGELOG.md`
- [ ] `MANIFEST.in`
- [ ] `.github/workflows/test.yml` (CI/CD)
- [ ] `.github/workflows/publish.yml` (PyPI publish)

### Already Exist
- [x] `pyproject.toml` (created this session)
- [x] `requirements.txt` (created this session)
- [x] `requirements-dev.txt` (created this session)
- [x] `README.md`
- [x] `.gitignore`
- [x] `cde_analyzer.py`

### Should Update
- [ ] `README.md` - Add installation instructions
- [ ] `.gitignore` - Add build artifacts (dist/, build/, *.egg-info/)
- [ ] `CLAUDE.md` - Update with packaging info

---

## Example Usage After Installation

### As End User
```bash
# Install
pip install cde-analyzer

# Use
cde-analyzer count --input cdes.json --fields tinyId --output-format csv
cde-analyzer phrase --input cdes.json --fields designations --min-words 3
cde-analyzer strip-html --input cdes.json --model CDE --outdir cleaned/
```

### As Developer
```bash
# Clone and install in editable mode
git clone https://github.com/gtromp/cde-analyzer.git
cd cde-analyzer
pip install -e .[dev]

# Develop
# ... make changes ...

# Test
pytest
ruff check .
mypy cde_analyzer/

# Build
python -m build

# Publish
twine upload dist/*
```

---

## Risks and Mitigation

### Risk 1: Missing Dependencies
**Risk**: Users can't install due to missing system dependencies (e.g., spaCy language models)
**Mitigation**:
- Document spaCy model installation in README
- Provide installation script
- Consider bundling common models

### Risk 2: Breaking Changes
**Risk**: PyPI version breaks existing scripts
**Mitigation**:
- Maintain backward compatibility
- Use deprecation warnings
- Follow semantic versioning strictly

### Risk 3: Name Collision
**Risk**: `cde-analyzer` name already taken on PyPI
**Mitigation**:
- Check PyPI before publishing: https://pypi.org/project/cde-analyzer/
- Alternative names: `nlm-cde-analyzer`, `cde-tools`, `cdeanalyzer`

### Risk 4: Incomplete Testing
**Risk**: Publishing without adequate tests
**Mitigation**:
- Expand test coverage before publishing
- Set minimum coverage threshold (80%)
- Test on clean environments

---

## Success Metrics

**Pre-1.0 Release**:
- [ ] Published to PyPI
- [ ] >80% test coverage
- [ ] All linting/type checking passing
- [ ] Installation works on Windows/Linux/macOS
- [ ] Documentation complete
- [ ] At least 5 GitHub stars

**Post-1.0 Release**:
- [ ] >1000 PyPI downloads/month
- [ ] No critical bugs reported
- [ ] Active contributor community
- [ ] Used in published research

---

## Next Steps

**Immediate Actions** (This Week):
1. Create all missing `__init__.py` files
2. Add LICENSE file (MIT recommended)
3. Create `__version__.py`
4. Update `.gitignore` for build artifacts
5. Create MANIFEST.in

**Short-Term Actions** (Next 2 Weeks):
1. Expand test coverage
2. Run and fix linting issues
3. Update README.md
4. Create CHANGELOG.md
5. Test local build and installation

**Medium-Term Actions** (Next Month):
1. Set up CI/CD pipeline
2. Complete documentation
3. Publish to Test PyPI
4. Get feedback from beta testers
5. Publish to production PyPI

**Long-Term Actions** (Next Quarter):
1. Maintain package
2. Address user issues
3. Add new features
4. Prepare for 1.0.0 stable release

---

## Resources

**Python Packaging**:
- https://packaging.python.org/
- https://peps.python.org/pep-0517/ (pyproject.toml)
- https://peps.python.org/pep-0621/ (Project metadata)

**PyPI**:
- https://pypi.org/
- https://test.pypi.org/ (for testing)
- https://pypi.org/help/

**Tools**:
- Build: https://pypa-build.readthedocs.io/
- Twine: https://twine.readthedocs.io/
- Setuptools: https://setuptools.pypa.io/

**Best Practices**:
- https://python-poetry.org/docs/ (alternative to setuptools)
- https://github.com/pypa/sampleproject (example project)
