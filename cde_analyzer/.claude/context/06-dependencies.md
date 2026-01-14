# Dependencies

## External Dependencies

### Core Dependencies

**pydantic**
- **Purpose**: Data modeling and validation
- **Usage**: All CDE_Schema models (CDEItem, CDEForm, all classes)
- **Version**: Unknown (no requirements file present)
- **Criticality**: CRITICAL - entire data model depends on this
- **Notes**:
  - Used for BaseModel, Field, type hints
  - Handles JSON serialization/deserialization
  - Provides validation framework

**importlib** (Standard Library)
- **Purpose**: Dynamic module loading for lazy loading architecture
- **Usage**: cde_analyzer.py dispatcher
- **Criticality**: CRITICAL for action loading

**argparse** (Standard Library)
- **Purpose**: Command-line argument parsing
- **Usage**: All CLI layers (cde_analyzer.py, actions/*/cli.py)
- **Criticality**: CRITICAL for CLI interface

### Data Processing Dependencies

**json** (Standard Library)
- **Purpose**: JSON serialization/deserialization
- **Usage**: All file I/O operations, output formatting
- **Criticality**: CRITICAL

**csv** (Standard Library)
- **Purpose**: CSV/TSV output generation
- **Usage**: utils/helpers.py, output formatting
- **Criticality**: HIGH for alternative output formats

**re** (Standard Library)
- **Purpose**: Regular expression matching
- **Usage**: logic/counter.py (regex matching), phrase processing
- **Criticality**: HIGH

**collections** (Standard Library)
- **Purpose**: defaultdict for counting operations
- **Usage**: logic/counter.py, aggregation operations
- **Criticality**: MEDIUM

**logging** (Standard Library)
- **Purpose**: Application logging
- **Usage**: All modules, utils/logger.py
- **Criticality**: MEDIUM

### Likely Dependencies (Not Confirmed in Sampled Code)

**requests** (Inferred)
- **Purpose**: HTTP requests to NLM CDE API
- **Usage**: API interaction (not visible in sampled files)
- **Criticality**: HIGH if API calls needed
- **Status**: Not confirmed - may be used in unsampled files or user handles API separately

**spacy** or **nltk** (Inferred)
- **Purpose**: NLP for lemmatization in phrase action
- **Usage**: phrase action (--lemmatize flag)
- **Criticality**: HIGH for phrase analysis
- **Notes**:
  - README mentions lemmatization
  - phrase action has --lemmatize flag
  - Actual NLP library not confirmed in sampled code
  - Could be spacy, nltk, or other

**scikit-learn** (Possible)
- **Purpose**: Possible use in phrase detection algorithms
- **Usage**: Kmer-based phrase detection (legacy modules)
- **Criticality**: LOW (legacy code)
- **Status**: Speculative

## Internal Dependencies

### Module Dependency Matrix

```
Module                    Imports From
------------------------- -----------------------------------------
cde_analyzer.py          utils.logger, utils.analyzer_state
actions/*/cli.py         .run (sibling module)
actions/*/run.py         logic.*, utils.*, CDE_Schema.*
logic/counter.py         core.recursor, utils.datatype_check,
                         utils.helpers, utils.analyzer_state,
                         utils.logger
logic/*                  core.recursor, utils.*, CDE_Schema.*
core/recursor.py         (none - pure recursion)
utils/*                  (various utils, some interdependencies)
CDE_Schema/*.py          pydantic
```

### Dependency Layers

**Layer 0 (No Internal Dependencies)**:
- core/recursor.py - Pure recursive algorithm
- CDE_Schema/*.py - Only depends on pydantic

**Layer 1 (Depends on Layer 0)**:
- Most utils/*.py - May use core/recursor
- Some utils have no dependencies (logger.py, analyzer_state.py)

**Layer 2 (Depends on Layers 0-1)**:
- logic/*.py - Uses core, utils, CDE_Schema

**Layer 3 (Depends on Layers 0-2)**:
- actions/*/run.py - Uses logic, utils, CDE_Schema

**Layer 4 (Top Level)**:
- actions/*/cli.py - Uses actions/*/run.py
- cde_analyzer.py - Coordinates everything

### Internal Module Dependencies

**Most Depended Upon**:
1. **core/recursor.py** - Used by most logic modules
2. **utils/logger.py** - Used throughout for logging
3. **utils/analyzer_state.py** - Verbosity used throughout
4. **utils/helpers.py** - General utilities
5. **CDE_Schema/classes.py** - Type definitions

**Least Depended Upon**:
1. Legacy kmer_*.py modules - Not imported elsewhere
2. Test modules - Standalone
3. Script modules - Utilities not part of main flow

### Circular Dependencies

**None Detected** - Clean layered architecture

## Third-Party Integration Points

### NLM CDE API
- **URL**: https://cde.nlm.nih.gov/api
- **Purpose**: Source of CDE data
- **Documentation**: Well-documented RESTful API
- **Data Format**: JSON
- **Integration**:
  - Users fetch data via API (outside this tool)
  - This tool processes downloaded JSON files
  - No direct API calls in sampled code

**Potential Extension**: Could add direct API integration
- Would require requests library
- Would need authentication handling (if required)
- Could add caching layer

### File System
- **Input**: JSON files from NLM CDE API
- **Output**: JSON, CSV, TSV files
- **Logging**: Optional log files (--logfile)
- **No Database**: Pure file-based processing

### Standard Input/Output
- **stdin**: Not used (all input from files)
- **stdout**: Primary output destination (unless --output specified)
- **stderr**: Error messages and logs

## Dependency Management

### Current State: No Explicit Dependency Management
- **No requirements.txt** present in repository
- **No pyproject.toml** present
- **No setup.py** present
- **No Pipfile** (pipenv)
- **No environment.yml** (conda)

**Implication**: Users must manually install dependencies

### Recommended Dependency Management

**Option 1: requirements.txt** (Simple)
```
pydantic>=2.0.0
# Add NLP library if confirmed
# spacy>=3.0.0
# nltk>=3.8.0
```

**Option 2: pyproject.toml** (Modern)
```toml
[project]
name = "cde-analyzer"
version = "0.1.0"
dependencies = [
    "pydantic>=2.0.0",
]
```

**Option 3: setup.py** (Traditional)
```python
setup(
    name="cde-analyzer",
    install_requires=[
        "pydantic>=2.0.0",
    ],
)
```

### Development Dependencies

**Should Include**:
- pytest or unittest - Testing framework
- mypy or pyright - Type checking
- black or ruff - Code formatting
- flake8 or ruff - Linting

**Currently**: Not specified

## Version Compatibility

### Python Version
- **Assumed**: Python 3.x
- **Minimum**: Likely 3.7+ (for type hints, importlib features)
- **Recommended**: 3.9+ (for modern type hint syntax)
- **Not Specified**: No python_requires in setup

### Pydantic Version
- **V1 vs V2**: Code could work with either
- **Syntax Used**: Compatible with both versions
  - `BaseModel`
  - `Field`
  - `Optional` type hints
- **Recommendation**: Specify version in requirements

### Operating System
- **Cross-Platform**: Pure Python, should work on Windows/Linux/macOS
- **File Paths**: Uses standard library path handling
- **No OS-Specific Dependencies**: Observed in sampled code

## Dependency Risks

### Pydantic Breaking Changes
- **Risk**: V1 → V2 had significant API changes
- **Mitigation**: Pin version, test before upgrading
- **Impact**: HIGH - all models would need updates

### NLP Library Changes
- **Risk**: spacy/nltk API changes could break lemmatization
- **Mitigation**: Version pinning
- **Impact**: MEDIUM - affects phrase action only

### Python Version Sunset
- **Risk**: Python 3.7 end-of-life
- **Mitigation**: Test with newer Python versions
- **Impact**: LOW - likely compatible with modern Python

### Standard Library Changes
- **Risk**: argparse, importlib rarely change
- **Impact**: VERY LOW

## Missing Dependency Documentation

### Issues
1. **No requirements file** - Users don't know what to install
2. **No version specifications** - Compatibility unknown
3. **No installation instructions** - Setup unclear
4. **NLP library unclear** - spacy? nltk? both? neither?

### Recommendations
1. Create requirements.txt or pyproject.toml
2. Document Python version requirement
3. Add installation section to README.md
4. Clarify NLP library choice
5. Consider setup.py for installable package

## Deployment Dependencies

### As Script
- User runs `python cde_analyzer.py` or `./cde_analyzer`
- Requires Python installed
- Requires dependencies installed (pip install ...)
- No packaging needed

### As Package
- Could package with setuptools
- Could distribute via PyPI
- Would need proper dependency specification
- Would enable `pip install cde-analyzer`

### As Executable
- Could use PyInstaller or similar
- Bundle Python + dependencies
- Larger distribution size
- No Python installation needed for users

**Current State**: Script-based deployment (no packaging)

## Dependency Vulnerability Considerations

### Security Scanning
- **Recommendation**: Use pip-audit or safety
- **Currently**: No scanning in place
- **Risk**: Unknown vulnerabilities in dependencies

### Supply Chain Security
- **Recommendation**: Pin exact versions, use lock files
- **Currently**: No version pinning
- **Risk**: Dependency changes could introduce issues

### License Compliance
- **Pydantic**: MIT License (permissive)
- **Standard Library**: PSF License (permissive)
- **Unknown**: NLP library license depends on choice
- **Recommendation**: Document all licenses

## Future Dependency Considerations

### Potential Additions
1. **HTTP Client**: requests or httpx for API calls
2. **Progress Bars**: tqdm for long operations
3. **Rich**: For better CLI output formatting
4. **Click**: Alternative to argparse (more features)
5. **Pandas**: For advanced data manipulation
6. **NumPy**: If numerical analysis added

### Potential Removals
1. **Legacy kmer modules**: If removed, check their unique dependencies
2. **Experimental code**: May have dependencies not needed in production

### Dependency Minimization
- **Current Approach**: Minimize external dependencies
- **Standard Library Preference**: Good practice observed
- **Rationale**: Easier deployment, fewer conflicts
- **Trade-off**: May reinvent wheels vs using established libraries
