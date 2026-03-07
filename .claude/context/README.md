# Claude Code Context Files

This directory contains structured context files for session recovery.

## Quick Recovery (Recommended)

For most session recovery, read these in order:
1. **`CLAUDE.md`** (project root) — authoritative current state (v0.9.4)
2. **`.claude/checkpoints/checkpoint-2026-02-27-v090-consolidated.md`** — full history
3. **`08-progress.md`** — current progress summary

Files 01-07 below are **deep reference** from early project phases (2026-01-07). They describe foundational architecture, patterns, and gotchas that are still largely valid, but file listings and dependency info are stale (pre-v0.6.0). Use them for understanding *how the architecture works*, not *what the current state is*.

## Context Files

### [01-architecture.md](01-architecture.md)
**Core system architecture and design**
- Architectural style and patterns
- Major components and their responsibilities
- Technology stack
- Component communication patterns
- Data flow
- Scalability considerations
- Key architectural decisions

### [02-codebase-map.md](02-codebase-map.md)
**File and directory structure**
- Annotated directory tree
- Entry points (main, utilities, analysis)
- Module dependency graph
- Hot files (frequently changed)
- Stable files (rarely changed)
- Navigation tips

### [03-data-models.md](03-data-models.md)
**Data structures and schemas**
- PostgreSQL schema (MLflow tables)
- In-memory data structures (SweepConfig, DictConfig)
- CVI registry structure
- Result dictionaries
- Data validation patterns
- Data flow examples
- Critical constraints

### [04-patterns.md](04-patterns.md)
**Design patterns and coding conventions**
- Plugin Registry Pattern (CVIs)
- Factory Pattern (algorithms)
- Configuration Composition (Hydra)
- Context Manager Pattern (resources)
- Graceful Degradation Pattern (errors)
- Dataclass Pattern (data transfer)
- Import patterns and conventions
- Type hints and protocols
- Testing patterns
- Performance optimization patterns
- Anti-patterns to avoid

### [05-decisions.md](05-decisions.md)
**Architectural Decision Records (ADRs)**
- Why Hydra for configuration
- Why PostgreSQL over SQLite
- Why Pareto multi-objective optimization
- Why Transparent Huge Pages
- Why code/data separation
- Why plugin registry for CVIs
- Why graceful error handling
- Why direct SQL for analysis
- Future considerations

### [06-dependencies.md](06-dependencies.md)
**External and internal dependencies**
- Python package dependencies (purpose, version, usage)
- Third-party algorithm libraries (UMAP, HDBSCAN)
- Internal module dependencies
- Third-party integrations (PostgreSQL, MLflow)
- Dependency management best practices
- Installation guides

### [07-gotchas.md](07-gotchas.md)
**Known issues, pitfalls, and workarounds**
- Critical gotchas (parameter grid syntax, hierarchical names)
- Common pitfalls (paths, MLflow artifacts, nesting)
- Configuration gotchas (composition, struct mode)
- Performance gotchas (memory, API slowness)
- Error handling gotchas (silent failures, partial results)
- Data gotchas (CSV format, noise labels)
- System gotchas (ports, disk space)
- Known limitations
- Quick fixes reference

### [08-progress.md](08-progress.md)
**Project progress and current state**
- Recent development timeline (last 30 days)
- Branch status and readiness
- Development velocity metrics
- Current work focus
- Known issues and workarounds
- Performance improvements achieved
- Documentation status
- Testing status
- Future considerations
- Recent lessons learned

## Usage

### For Session Recovery

1. **Quick Scan** (2-3 minutes):
   - Read `08-progress.md` for current state and recent work
   - Skim `02-codebase-map.md` for file locations
   - Check `07-gotchas.md` for immediate concerns

2. **Detailed Recovery** (10-15 minutes):
   - Read all context files in order (01-08)
   - Cross-reference with actual code as needed
   - Check git log for changes since last update

3. **Targeted Recovery**:
   - **Current status**: `08-progress.md`
   - **Understanding architecture**: `01-architecture.md`, `05-decisions.md`
   - **Finding code**: `02-codebase-map.md`
   - **Debugging issues**: `07-gotchas.md`, `04-patterns.md`
   - **Data problems**: `03-data-models.md`
   - **Adding features**: `04-patterns.md`, `06-dependencies.md`

### For New Contributors

Read in order:
1. `01-architecture.md` - Understand the system
2. `02-codebase-map.md` - Navigate the code
3. `04-patterns.md` - Learn conventions
4. `07-gotchas.md` - Avoid common mistakes

### For Specific Tasks

- **Adding new CVI**: `04-patterns.md` (Plugin Registry), `02-codebase-map.md` (cvi/)
- **Fixing parameter bugs**: `07-gotchas.md` (#1, #2), `03-data-models.md`
- **Optimizing performance**: `04-patterns.md` (Performance), `05-decisions.md` (ADR-004)
- **Adding dependencies**: `06-dependencies.md`
- **Understanding data flow**: `01-architecture.md`, `03-data-models.md`

## Maintenance

### When to Update

Update context files when:
- Major architectural changes occur
- New patterns are introduced
- Critical bugs/gotchas discovered
- Dependencies added or changed
- Significant refactoring completed
- New subsystems added

### How to Update

```bash
# 1. Review changes since last update
git log --oneline --since="2026-01-07"

# 2. Update relevant context files
# - Add new sections for new features
# - Update existing sections for changes
# - Add new gotchas as discovered
# - Update dependency versions

# 3. Commit context updates
git add .claude/context/
git commit -m "Update checkpoint context files"
```

### Update Schedule

- **Major changes**: Update immediately
- **Minor changes**: Batch updates weekly
- **Bug discoveries**: Add to `07-gotchas.md` as found
- **Dependencies**: Update when requirements.txt changes

## File Formats

All files use Markdown format with:
- Clear heading hierarchy
- Code examples in fenced blocks
- Cross-references using relative links
- Tables for structured information
- Emoji indicators for critical items (⚠️, 🔥, ✓, ✗)

## Context File Size

Current sizes (as of 2026-01-07):
- `01-architecture.md`: ~10 KB (40-50 min read)
- `02-codebase-map.md`: ~18 KB (30-40 min read)
- `03-data-models.md`: ~14 KB (25-35 min read)
- `04-patterns.md`: ~18 KB (35-45 min read)
- `05-decisions.md`: ~18 KB (30-40 min read)
- `06-dependencies.md`: ~17 KB (30-40 min read)
- `07-gotchas.md`: ~17 KB (35-45 min read)
- `08-progress.md`: ~25 KB (15-20 min read)
- **Total**: ~137 KB (4-5 hours full read)

## Integration with Development Workflow

### Daily Use
1. Before coding: Check `07-gotchas.md` for related pitfalls
2. While coding: Reference `04-patterns.md` for conventions
3. After coding: Update context if new patterns/gotchas discovered

### Code Review
- Reference architecture decisions (`05-decisions.md`)
- Check compliance with patterns (`04-patterns.md`)
- Verify against known gotchas (`07-gotchas.md`)

### Onboarding
- Day 1: Read `01-architecture.md`, `02-codebase-map.md`
- Day 2: Read `04-patterns.md`, `07-gotchas.md`
- Day 3: Read `03-data-models.md`, `05-decisions.md`, `06-dependencies.md`
- Ongoing: Reference as needed

## Additional Resources

Beyond these context files, see also:
- [README.md](../../README.md) - Project overview
- [docs/](../../docs/) - Comprehensive documentation (91 files)
- [docs/INDEX.md](../../docs/INDEX.md) - Documentation index
- [CLAUDE.md](../../CLAUDE.md) - Claude-specific instructions
- Git history - Evolution of decisions and implementations

## Version History

- **2026-01-07**: Initial creation of checkpoint system
  - Created 8 comprehensive context files (01-08)
  - Comprehensive analysis of codebase
  - Captured all architectural decisions
  - Documented patterns and gotchas
  - Added progress tracking (08-progress.md)

---

**Note**: These files represent a snapshot in time. Always cross-check with actual code and git history for most recent changes.
