# Checkpoint: 2026-01-29 — phrase-curator branch

## Resume Context

**Branch**: `phrase-curator`
**Version**: 0.5.0 → 0.5.1 (patch bump this session)
**Previous commit**: `c95c529` (v0.5.0)

### What Was Done This Session

1. **Full pipeline run (scheuermann08)** — instrument detection + phrase stripping end-to-end
   - Phase 1: 136 instrument patterns (105 tier-1 + 31 tier-2), 4 false positives removed
   - Phase 2: 85 phrase patterns stripped from 535 tinyIds
   - Output: `scheuermann08/phase2_output/final_stripped.json`

2. **New action: `discovery_report`** — generates markdown summary of pipeline execution
   - Per-step metrics (row counts, tinyId coverage)
   - Subsumption summary, sanity check survivors
   - Version history tracking across iterations
   - Integrated into both workflow YAML files

3. **Code enhancements committed in this session's changes**:
   - `pattern_util`: anchor trimming, rollup-subset-tinyids, emit-def-variants, split-tiers, group-hierarchy, field-analysis, min-field-count, min-tokens, exclude-patterns
   - `strip_discover`: min-bare-words filter, discover-abbreviations subcommand
   - `strip_phrases`: two-pass stripping support
   - `flexible_pattern_matcher`: roll-down min 2-word check, rollup-subset substring match
   - `instrument_family_assigner`: family detection enhancements

### Key Configuration Learned

- `min_parent_tinyids=20` (phrase_pipeline.yaml default) is too aggressive for datasets ~1K CDEs — use 2
- Two-pass stripping (tier-1 long patterns first, tier-2 short fragments second) prevents fragment patterns from damaging instrument names

### Files Modified (uncommitted)

13 modified files + 5 new files (discovery_report action, group_hierarchy, span_boundary, branching_strip workflow, CLAUDE_full.md)

### Pending Follow-ups

1. **Verb-containing phrase filter** — automate false positive detection for phrases with verbs (e.g., "mentally tired", "think about")
2. **Post-strip article cleanup** — script removal of residual articles (`the`, `the and`) after instrument stripping
3. **Temporal pattern noise** — temporal patterns still noisy, clean up in next iteration
4. **Adjust min_parent_tinyids default** — lower from 20 or make dataset-adaptive

### How to Resume

```bash
# Check current state
cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer
git status
git log --oneline -5

# Pipeline outputs
ls /mnt/d/GT/Professional/NLM_CDE/work_202601/cde_repository/scheuermann08/

# Re-read context
cat .claude/checkpoint_20260129.md
cat .claude/notes.md
cat .claude/TODO.md
```

### Data Directories

| Directory | Contents |
|-----------|----------|
| `scheuermann04/` | Original manual process (ground truth, process notes) |
| `scheuermann07/` | Previous pipeline run (reference) |
| `scheuermann08/` | This session's full pipeline run |

### WSL Command Pattern

```bash
wsl -d Ubuntu-22.04 -- bash -c "cd /mnt/d/GT/Professional/NLM_CDE/clone_git/cde-clustering/cde_analyzer && source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate && python cde_analyzer.py <action> [args]"
```
