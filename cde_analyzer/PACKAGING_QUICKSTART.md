# Quick Start: PyPI Packaging for cde_analyzer

This guide will walk you through testing and publishing the `cde_analyzer` package to PyPI.

## Prerequisites

```bash
# Install build tools
pip install build twine

# Verify you have the required Python version
python --version  # Should be 3.9 or higher
```

## Step 1: Build the Package

```bash
# From the project root directory
python -m build
```

**Expected Output**:
```
Successfully built cde_analyzer-0.2.0.tar.gz and cde_analyzer-0.2.0-py3-none-any.whl
```

**Files Created**:
- `dist/cde_analyzer-0.2.0.tar.gz` - Source distribution
- `dist/cde_analyzer-0.2.0-py3-none-any.whl` - Wheel distribution

## Step 2: Verify the Build

```bash
# Check the distribution files
twine check dist/*
```

**Expected Output**:
```
Checking dist/cde_analyzer-0.2.0.tar.gz: PASSED
Checking dist/cde_analyzer-0.2.0-py3-none-any.whl: PASSED
```

## Step 3: Test Installation Locally

```bash
# Create a test virtual environment
python -m venv test-env

# Activate it (Windows)
test-env\Scripts\activate

# Activate it (Linux/Mac)
# source test-env/bin/activate

# Install the package
pip install dist/cde_analyzer-0.2.0-py3-none-any.whl

# Test the command-line tool
cde-analyzer --help
cde-analyzer count --help
cde-analyzer phrase --help

# Deactivate when done testing
deactivate
```

## Step 4: Upload to Test PyPI (Recommended First)

```bash
# Create an account at https://test.pypi.org/ if you don't have one

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# You'll be prompted for:
# - Username: Your Test PyPI username
# - Password: Your Test PyPI password (or token)
```

**Test Installation from Test PyPI**:
```bash
# Create a fresh virtual environment
python -m venv test-pypi-env
test-pypi-env\Scripts\activate  # Windows
# source test-pypi-env/bin/activate  # Linux/Mac

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ cde-analyzer

# Test it
cde-analyzer --help

# Deactivate
deactivate
```

**Note**: The `--extra-index-url` is needed because Test PyPI doesn't have all the dependencies (pydantic, spacy, etc.), so pip will fetch them from the real PyPI.

## Step 5: Upload to Production PyPI

**ONLY after thoroughly testing on Test PyPI!**

```bash
# Create an account at https://pypi.org/ if you don't have one

# Upload to PyPI
twine upload dist/*

# You'll be prompted for:
# - Username: Your PyPI username
# - Password: Your PyPI password (or token)
```

**Verify on PyPI**:
- Visit: https://pypi.org/project/cde-analyzer/
- Check that all metadata looks correct

**Test Installation**:
```bash
# Anyone can now install with:
pip install cde-analyzer

# Test
cde-analyzer --help
```

## Using API Tokens (Recommended)

Instead of username/password, use API tokens for better security.

### For Test PyPI:
1. Go to https://test.pypi.org/manage/account/token/
2. Create a new API token
3. Scope it to the cde-analyzer project
4. Save the token (starts with `pypi-`)

### For Production PyPI:
1. Go to https://pypi.org/manage/account/token/
2. Create a new API token
3. Scope it to the cde-analyzer project
4. Save the token

### Using the Token:
```bash
# When prompted for username, enter: __token__
# When prompted for password, paste your token (including the pypi- prefix)
```

Or create a `.pypirc` file in your home directory:
```ini
[testpypi]
  username = __token__
  password = pypi-YOUR-TEST-TOKEN-HERE

[pypi]
  username = __token__
  password = pypi-YOUR-PRODUCTION-TOKEN-HERE
```

## Common Issues and Solutions

### Issue: Package name already taken

**Error**: `HTTPError: 403 Client Error: The name 'cde-analyzer' is too similar to an existing project`

**Solution**:
1. Check https://pypi.org/project/cde-analyzer/ to see if the name exists
2. If taken, choose an alternative name:
   - `nlm-cde-analyzer`
   - `cde-analysis-tools`
   - `cdeanalyzer`
3. Update the name in `pyproject.toml`:
   ```toml
   [project]
   name = "your-new-name-here"
   ```
4. Rebuild: `python -m build`

### Issue: Missing dependencies

**Error**: `ModuleNotFoundError: No module named 'pydantic'`

**Solution**: This shouldn't happen if you installed from the wheel, but if it does:
```bash
pip install pydantic spacy nltk PyYAML
```

### Issue: spaCy language model missing

**Error**: `OSError: [E050] Can't find model 'en_core_web_sm'`

**Solution**:
```bash
python -m spacy download en_core_web_sm
```

## Updating the Package (Future Versions)

1. **Update version** in `pyproject.toml` and `cde_analyzer/__version__.py`
2. **Update CHANGELOG.md** with changes
3. **Clean old builds**:
   ```bash
   rm -rf dist/ build/ *.egg-info
   ```
4. **Rebuild**:
   ```bash
   python -m build
   ```
5. **Upload**:
   ```bash
   # Test PyPI first
   twine upload --repository testpypi dist/*

   # Then production
   twine upload dist/*
   ```

## Development Installation

For development, install in editable mode:

```bash
# Clone the repository
git clone https://github.com/gtromp/cde-analyzer.git
cd cde-analyzer

# Install in editable mode with dev dependencies
pip install -e .[dev]

# Now any changes to the code are immediately reflected
# without needing to reinstall
```

## Next Steps After Publishing

1. **Update README.md** with installation instructions
2. **Announce the release** on relevant forums/communities
3. **Set up CI/CD** for automated testing and publishing
4. **Monitor** for issues and bug reports
5. **Plan next version** based on user feedback

## Resources

- **Test PyPI**: https://test.pypi.org/
- **Production PyPI**: https://pypi.org/
- **Packaging Guide**: https://packaging.python.org/
- **Twine Docs**: https://twine.readthedocs.io/
- **Build Docs**: https://pypa-build.readthedocs.io/

## Questions?

See the detailed documentation in:
- [`.claude/analysis/packaging-plan.md`](.claude/analysis/packaging-plan.md) - Complete packaging roadmap
- [`.claude/analysis/implementation-summary.md`](.claude/analysis/implementation-summary.md) - What was done
- `CHANGELOG.md` - Version history

---

**Remember**: Always test on Test PyPI before uploading to production PyPI!
