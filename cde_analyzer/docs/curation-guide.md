# Pattern Curation Guide

This document provides guidelines for the human curation steps in phrase and instrument stripping workflows. Curation bridges automated pattern discovery and final stripping — curator decisions directly impact what gets removed from CDE text.

## Where Curation Fits

```
phrase_miner / instrument_miner
        │
        ▼
  coalesced.tsv  ←── Automated: subsumption, prefix extraction
        │
        ▼
  ┌─────────────────┐
  │  HUMAN CURATION │  ◄── You are here
  └─────────────────┘
        │
        ▼
    curated.tsv   ←── Final patterns for stripping
        │
        ▼
    strip_phrases
```

## The `curated.tsv` Format

The curated file uses a **simplified two-column format** for easy editing:

| Column | Description |
|--------|-------------|
| `pattern` | The exact text to match and strip |
| `tinyIds` | Pipe-separated list of CDE tinyIds where pattern appears |

**Example:**
```tsv
pattern	tinyIds
Patient Health Questionnaire	abc123|def456|ghi789
in the past 7 days	xyz111|xyz222|xyz333
```

This format is intentionally minimal. Additional columns (like `field_profile`, `definition_count`) may exist in intermediate files but are not required for stripping.

---

## Pattern Sources

Before curation, you'll typically have several pattern files to review and merge:

| File | Contents | Notes |
|------|----------|-------|
| `coalesced.tsv` | K-mer mined patterns after subsumption | Main source |
| `abbrev_patterns.tsv` | Abbreviation-derived patterns | From `--extract-abbreviation-only` |
| `coalesced_fields.tsv` | Patterns enriched with field counts | If `--field-analysis` was run |

**Merging sources:**

The `--merge-patterns` option deduplicates within a single file. To combine multiple source files:

```bash
# Step 1: Normalize each file to minimal 2-column format (pattern, tinyIds)
cde-analyzer pattern_util --to-minimal coalesced.tsv -o coalesced_min.tsv
cde-analyzer pattern_util --to-minimal abbrev_patterns.tsv -o abbrev_min.tsv

# Step 2: Concatenate (skip header on second file)
head -1 coalesced_min.tsv > combined.tsv
tail -n +2 coalesced_min.tsv >> combined.tsv
tail -n +2 abbrev_min.tsv >> combined.tsv

# Step 3: Merge duplicate patterns (combines tinyId sets)
cde-analyzer pattern_util --merge-patterns combined.tsv -o merged.tsv
```

The `--to-minimal` step handles column name variations (e.g., `tinyIds` vs `tinyids`) and normalizes separators to pipe (`|`).

---

## Curation Decision Guide

### 1. Anchor Phrases

**What they are:** Phrases that introduce instruments or measurements:
- "as part of the..."
- "based on the..."
- "derived from the..."
- "using the..."
- "measured by the..."

**Decision: Trim or Preserve?**

| Approach | When to Use |
|----------|-------------|
| **Trim** (default) | Most cases. Strips the bare pattern everywhere it appears |
| **Preserve** | When the anchor provides important context that shouldn't be removed in isolation |

**Example:**
```
Input:  "as part of the Neuro-QOL Lower Extremity Function"
Trimmed: "Neuro-QOL Lower Extremity Function"  ← matches all occurrences
Preserved: "as part of the Neuro-QOL..."        ← only matches with anchor
```

**Recommendation:** Use trimmed patterns. The anchor phrase itself ("as part of the") can be stripped separately as a boilerplate pattern.

The `--coalesce-variants` command trims anchors by default. Use `--no-trim-anchors` to preserve them.

### 2. Abbreviation Patterns

Patterns derived from abbreviation expansion (e.g., from `abbrev_patterns.tsv`):

| Pattern Type | Example | Include? |
|--------------|---------|----------|
| Full name | `Patient Health Questionnaire` | ✓ Yes |
| Acronym only | `PHQ` | ⚠ Maybe — risk of false positives |
| With version | `PHQ-9` | ✓ Yes |
| Family prefix | `PHQ-` | ⚠ Careful — may match unrelated text |

**Guidance:**
- Include full instrument names
- Include versioned acronyms (PHQ-9, GAD-7)
- Be cautious with bare acronyms — they may appear in unrelated contexts
- Short patterns (<3 tokens) have higher false positive risk

### 3. Temporal/Boilerplate Patterns

Common boilerplate phrases that appear across many CDEs:

| Category | Examples |
|----------|----------|
| Recency windows | "in the past 7 days", "over the last 4 weeks" |
| Response prompts | "Please select one", "Check all that apply" |
| Scale anchors | "Not at all", "Extremely", "0 = Never" |
| Definition templates | "This variable represents...", "The value for..." |

**Decision factors:**

| Factor | Keep | Remove |
|--------|------|--------|
| Appears in 20%+ of CDEs | | ✓ (boilerplate) |
| Carries semantic meaning | ✓ | |
| Varies only by numbers | | ✓ (template) |
| Part of instrument name | ✓ | |

**Temporal pattern grouping:** Patterns like "in the past N days" can often be grouped:
```
in the past 7 days    → group as temporal boilerplate
in the past 30 days   → group as temporal boilerplate
in the past 4 weeks   → group as temporal boilerplate
```

Use `--group-semantic` or manual review to identify these families.

### 4. Field-Specific Patterns

Some patterns appear only in definitions or only in designations:

| Field Profile | Meaning | Curation Note |
|---------------|---------|---------------|
| `def-only` | Pattern only in definition fields | May be definition template |
| `desig-only` | Pattern only in designation fields | May be naming convention |
| `both-all` | Pattern in both fields, all occurrences | Strong stripping candidate |
| `mixed` | Pattern in both, but not consistently | Review manually |

**Field-aware stripping:** If a pattern appears only in definitions, you may want to strip it only from definitions (using `strip_phrases --fields definitions.*.definition`).

Run `--field-analysis` to add these columns:
```bash
cde-analyzer pattern_util --field-analysis coalesced.tsv \
    -i source.json -m CDE -o coalesced_fields.tsv
```

### 5. Short Patterns

Patterns with few tokens have higher false positive risk:

| Token Count | Risk Level | Guidance |
|-------------|------------|----------|
| 1 token | ⚠ High | Avoid unless very specific (e.g., instrument acronym) |
| 2 tokens | ⚠ Medium | Review context carefully |
| 3+ tokens | ✓ Lower | Generally safe to include |

Use `--min-tokens N` to filter:
```bash
cde-analyzer pattern_util --field-analysis input.tsv ... --min-tokens 3 -o filtered.tsv
```

### 6. Instrument Residuals

After instrument stripping, residual instrument-related patterns may remain:

| Residual Type | Example | Action |
|---------------|---------|--------|
| Version suffix | "Short Form 8a" | Include if instrument-specific |
| Score reference | "total score", "subscale score" | Include if boilerplate |
| Administration | "self-report", "clinician-rated" | Review — may be meaningful |

If you identify missed instruments during phrase curation, add them back to the instrument pipeline rather than including them in phrase curation.

---

## Minimum Count Thresholds

Patterns appearing in very few CDEs may not be worth stripping:

| Threshold | Rationale |
|-----------|-----------|
| `--min-field-count 3` | Pattern must appear in at least 3 CDEs in one field |
| `--min-field-count 6` | More conservative — reduces noise |

**Trade-off:** Lower thresholds catch more patterns but increase manual review burden.

---

## Common Pitfalls

### 1. Ordering Conflicts

When pattern A is a substring of pattern B, stripping order matters:

```
Pattern A: "Quality of Life"
Pattern B: "Neuro-QOL Quality of Life"

Wrong order: Strip A first → "Neuro-QOL " remains (orphaned prefix)
Right order: Strip B first → clean removal
```

**Solution:** `strip_phrases` handles this automatically by sorting patterns longest-first. But if you have conflicting patterns, the coalesce step should have subsumed the shorter one.

### 2. Over-Stripping

Removing meaningful content, not just boilerplate:

- ❌ Stripping "depression" because it appears in many CDEs
- ❌ Stripping "score" without instrument context
- ❌ Stripping disease names that are semantically important

**Test:** Would removing this pattern lose information needed to understand the CDE?

### 3. Under-Stripping

Leaving boilerplate that creates noise in downstream analysis:

- ❌ Keeping "Please select the appropriate response"
- ❌ Keeping instrument names when goal is to analyze non-instrument content

**Test:** Does this pattern add signal or noise for your analysis goal?

### 4. Variant Inconsistency

Including one variant but missing others:

```
✓ "in the past 7 days"
✗ "in the past seven days"  ← missing!
✗ "In the past 7 days"      ← missing! (case variation)
```

**Solution:** Use `strip_discover --expand-variants` to find all surface forms, then coalesce.

---

## Curation Workflow Summary

```
1. Review coalesced.tsv and abbrev_patterns.tsv
         │
         ▼
2. Merge sources: pattern_util --merge-patterns
         │
         ▼
3. Enrich with field analysis (optional): pattern_util --field-analysis
         │
         ▼
4. Apply filters:
   - --min-field-count N (drop low-frequency)
   - --min-tokens N (drop short patterns)
   - --exclude-patterns FILE (drop known exclusions)
         │
         ▼
5. Manual review: pattern_util --edit coalesced_fields.tsv
   - Remove instrument residuals → send back to instrument pipeline
   - Remove false positives (meaningful content)
   - Group temporal/boilerplate families
   - Verify anchor phrase handling
   - Save As curated.tsv, Ctrl-C to stop the server
         │
         ▼
7. Strip: strip_phrases --patterns curated.tsv
```

---

## Tools for Curation Support

| Tool | Purpose |
|------|---------|
| `pattern_util --edit FILE` | Browser-based TSV editor for reviewing and editing patterns |
| `pattern_util --field-analysis` | Add per-field counts for review |
| `pattern_util --group-semantic` | Group by shared prefix (temporal families) |
| `pattern_util --exclude-patterns` | Remove patterns from exclusion list |
| `llm_classify -m temporal` | LLM-assisted temporal pattern classification |
| `llm_classify -m instrument` | LLM-assisted instrument detection |
| `strip_analyze --analyze-conflicts` | Find ordering/containment conflicts |

---

## Checklist Before Stripping

- [ ] All pattern sources merged (`coalesced.tsv` + `abbrev_patterns.tsv`)
- [ ] Anchor phrases handled consistently (trimmed or preserved, not mixed)
- [ ] Short patterns (<3 tokens) reviewed for false positive risk
- [ ] Instrument residuals sent back to instrument pipeline (not in phrase curation)
- [ ] Temporal/boilerplate patterns grouped appropriately
- [ ] Field-specific patterns noted if field-aware stripping needed
- [ ] Minimum count threshold applied
- [ ] Output has only `pattern` and `tinyIds` columns

---

## Related Documentation

- [Phrase Miner Logic](phrase_miner_logic.md) — Algorithm internals
- [pattern_util](help/pattern_util.md) — TSV manipulation utilities
- [strip_phrases](help/strip_phrases.md) — Stripping engine
- [Instrument & Phrase Stripping Workflow](workflows/instrument-phrase-stripping-workflow.md) — Complete workflow
- [LLM Classification](llm/index.md) — Automated classification support
