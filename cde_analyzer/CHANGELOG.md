# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PyPI packaging support with `pyproject.toml`
- `requirements.txt` for production dependencies
- `requirements-dev.txt` for development dependencies
- CLI argument standardization audit and documentation
- Package `__init__.py` files for proper module structure
- MIT License
- This CHANGELOG file
- Version management via `__version__.py`

### Changed
- Prepared for `pip install cde-analyzer` distribution
- Documentation updates for installation

## [0.2.0] - 2026-01-13

### Added
- PyPI packaging configuration
- Comprehensive dependency specification
- Package metadata and entry points
- CLI argument standardization plan
- Packaging and deployment documentation

### Changed
- Repository structure prepared for PyPI distribution
- Added proper Python package initialization files

### Fixed
- Launcher fixes post lazy-load refactoring (commits 4e601c7, 57b9437)
- Repository cleanup (commit 83f1df2)

## [0.1.0] - 2024-12-XX

### Added
- Lazy loading architecture for fast CLI startup (commit 4400bf7)
- Action-based plugin system
- Nine CLI actions:
  - `fix_underscores` - Fix Pydantic-incompatible field names
  - `strip_html` - Remove HTML markup from CDE fields
  - `phrase` - Find repeated phrases across CDE records
  - `count` - Count structural elements and field occurrences
  - `extract_embed` - Extract fields for transformer model embedding
  - `strip_phrases` - Remove literal phrases at specified paths
  - `lemma_fasta` - Create FASTA format from lemma sequences
  - `phrase_builder` - Incremental phrase construction
  - `subset` - Extract subsets using filters

### Changed
- Major refactoring to lazy loading architecture
- Dramatic startup performance improvement
- CLI structure inspired by git/pip command model

### Technical Details
- Pydantic 2.x models for NLM CDE API schema
- Recursive descent visitor pattern for nested data traversal
- Multiple output formats (JSON, CSV, TSV)
- Optional HTML table parsing
- Lemmatization support for phrase extraction
- FASTA format export for bioinformatics tools

## [0.0.1] - 2024-XX-XX (Initial Development)

### Added
- Initial implementation of CDE data models
- Basic CLI structure
- Recursive descent engine (core/recursor.py)
- HTML stripping functionality
- Field counting capabilities
- Phrase extraction (experimental kmer approaches)

---

## Version History Notes

### Version Numbering
- **0.x.x** - Pre-1.0 development releases
- **0.1.0** - Initial implementation (pre-lazy loading)
- **0.2.0** - Lazy loading + PyPI packaging (current)
- **1.0.0** - Planned stable release (future)

### Deprecations
None yet (pre-1.0 development)

### Security
No known security issues

### Known Issues
- Test coverage minimal (needs expansion before 1.0)
- CLI argument naming inconsistent (standardization planned for 0.3.0)
- Legacy kmer_*.py files retained but not actively maintained
- Documentation incomplete (comprehensive docs planned)

---

## Migration Guides

### Migrating from 0.1.x to 0.2.x
No breaking changes. All existing usage patterns continue to work.

**New features available**:
- Can now install via `pip install cde-analyzer` (once published)
- New command-line entry point: `cde-analyzer` (in addition to `python cde_analyzer.py`)

### Future Breaking Changes (0.3.0)
Planned CLI argument standardization may deprecate some argument names.
Deprecation warnings will be added before removal.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information on how to contribute to this project.

---

## Links

- **GitHub**: https://github.com/gtromp/cde-analyzer
- **PyPI**: https://pypi.org/project/cde-analyzer/ (pending publication)
- **Documentation**: https://cde-analyzer.readthedocs.io (planned)
- **Issue Tracker**: https://github.com/gtromp/cde-analyzer/issues

[Unreleased]: https://github.com/gtromp/cde-analyzer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gtromp/cde-analyzer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gtromp/cde-analyzer/releases/tag/v0.1.0
