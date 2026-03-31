# Curator Briefing — Efficient Pattern Curation

> **Version**: v1.0.1 &nbsp;|&nbsp; **Quick reference**: [TSV Editor Cheatsheet](tsv-editor-cheatsheet.md) &nbsp;|&nbsp; **Print version**: [`cheatsheets/tsv-editor.html`](cheatsheets/tsv-editor.html)

This document explains *how to curate efficiently*, not just which buttons to press. It assumes you have the editor open and a `needs_review.tsv` loaded.

---

## What You're Looking At

Each row is a **text pattern** that the pipeline detected as repeated across multiple CDEs (Common Data Elements). The `tinyid_count` column tells you how many CDEs contain that pattern. Your job is to decide, for each pattern, whether stripping it from CDE text will improve downstream analysis — or whether removing it would destroy meaningful content.

**The goal**: Remove boilerplate and instrument names so that when CDEs are embedded for clustering, they cluster by *semantic meaning* rather than by shared questionnaire text.

---

## The 5 Decisions — When and Why

| Decision | Shortcut | Rationale |
|----------|:--------:|-----------|
| **strip** | `S` | This pattern is a real instrument name, scale name, or boilerplate phrase. Stripping it improves clustering. *This is the safe default — blank rows are treated as strip.* |
| **skip** | `K` | This is a false positive — not actually an instrument or boilerplate phrase. It's meaningful clinical/scientific text that should remain in the CDE. Skipping it means it will **not** be stripped. |
| **modify** | `M` | The detected text is partially correct but the boundaries are wrong. You'll type the corrected pattern text in the `modification` column. The corrected text gets stripped instead. |
| **substitute** | `U` | The matched text should be *replaced* with something else, not deleted. Type the replacement in `modification`. Use this when deletion would leave broken grammar but a shorter phrase would be clean. |
| **followup** | `F` | You're unsure. Flag it for later discussion. Counts as undecided — the status bar tracks these. |

**The key distinction**: `strip` = "yes, strip this from CDEs." `skip` = "no, leave CDE text alone — this pattern shouldn't be in our strip list."

---

## Mass Selection Techniques

Efficient curation means working in *batches*, not row by row.

### Range selection with Shift+click

1. Click the checkbox on the **first** row of interest
2. **Shift+click** the checkbox on the **last** row of interest
3. All rows between are now selected
4. Press `S`, `K`, `M`, `U`, or `F` to assign the decision to all selected rows at once

### Select-all visible rows

1. Apply a filter (e.g., filter the pattern column for `scale` to see all scale-related patterns)
2. Press **Ctrl+A** — selects all *visible* (filtered) rows, not all rows in the file
3. Assign a decision
4. Clear filter (**Ctrl+Shift+F**) and move to the next group

### The "blank sweep" finishing move

After triaging the patterns you recognize:

1. Set the **decision filter** dropdown to `blank` — shows only undecided rows
2. **Ctrl+A** to select all remaining
3. Press `S` to mark them all as strip (the safe default — these patterns will be stripped)
4. Reset filter to `(all)` to verify — the status bar should show `?0` (zero undecided)

---

## Working with the Containment Tree

The containment tree is the most powerful tool for efficient curation. It reveals **hierarchical relationships** between patterns: when a short pattern is a word-level prefix of a longer pattern, and the short pattern's CDEs are a superset of the longer pattern's CDEs, the short pattern *contains* the longer one.

### Why this matters

If you decide to **strip** the pattern `Scale of` (which appears in 409 CDEs), then every CDE that contains `Scale of the difficulty of regulating emotions` (133 CDEs) will *already* have that longer text stripped — because removing `Scale of` from the beginning also removes it from longer phrases that start with those words.

This means: **if you strip a parent, you can safely skip all its children** — they're redundant.

### Reading the tree column

| Display | Meaning |
|---------|---------|
| **▶ 12** (purple badge) | Root pattern with 12 descendants. Click ▶ to expand. |
| **▼ 12** (expanded) | Expanded root — children visible below. |
| **· ⊃ Scale of** | Child at depth 1 — this pattern is contained by "Scale of" |
| **·· ⊃ Scale of the** | Grandchild at depth 2 — contained by "Scale of the" |
| *(empty)* | Singleton — no containment relationship with other patterns |

### The tree curation workflow

This is the recommended approach for datasets with containment trees:

**Step 1: Enable tree sort.**
Press `T` to activate tree sort. This groups children directly below their parents in depth-first order, sorted by tinyid_count (highest-impact patterns first).

**Step 2: Evaluate the root pattern.**
Look at the root (e.g., `Scale of` — 409 tinyIds, ▶ 12 descendants). Ask: *"If I strip 'Scale of' from every CDE where it appears, does that cause semantic loss?"*

- If **no** (it's a real instrument/scale prefix): Mark it `strip`. Then its children are redundant — you'll skip them in step 4.
- If **yes** (stripping it would destroy meaning): Mark it `skip`. Then move to step 3.

**Step 3: Evaluate sub-roots (the next level down).**
When you skip a root, its children are *not* automatically handled — they're independent patterns that still need decisions. Expand the tree (click ▶) and look at the next level:

- `Scale of the difficulty of regulating emotions` (133 tinyIds)
- `Scale of Prodromal Symptoms` (87 tinyIds)
- `Scale of Independent Behavior` (45 tinyIds)

Each sub-root is a longer, more specific phrase. Ask the same question: *"Does stripping this cause semantic loss?"* Often the longer phrase *is* a real instrument name and should be stripped, even though the shorter prefix was too generic.

**Rinse and repeat** at each depth level. In practice, most trees are 2-3 levels deep and this takes seconds per tree.

**Step 4: Bulk-skip redundant children.**
After deciding on the root and sub-roots:

1. Click the ▶ on the root to expand its subtree
2. Select the root row's checkbox, then **Shift+click** the last child's checkbox — the entire subtree is now selected
3. Set the decision filter to `blank` — now only the *undecided* rows within your selection are visible
4. **Ctrl+A** to select all visible (undecided children)
5. Press `K` to skip them all — they're redundant because their parent is being stripped

Alternatively, use the **⊃ Propagate** button: if a parent has a decision, clicking ⊃ Propagate copies that decision to all its descendants. This is fastest when you want all children to inherit the parent's decision.

### When children should NOT inherit the parent's decision

- **Parent is `skip` but a child is a real instrument name**: The child needs its own `strip` decision. Set the parent to `skip`, then individually mark the meaningful children as `strip`.
- **Parent is `strip` but a child has wrong boundaries**: The child might need `modify` to correct the pattern text before stripping.
- **Mixed semantics**: `Scale of` might be too generic (skip), but `Scale of Independent Behavior` is a real instrument (strip). Evaluate each level independently.

### Tree filter for focused review

Use the **tree filter dropdown** to focus:

| Filter | Shows | When to use |
|--------|-------|-------------|
| `root` | Only root patterns (parents with children) | First pass — decide on the high-level patterns |
| `child` | Only contained patterns | After roots are decided — clean up descendants |
| `none` | Singletons (no tree relationships) | Independent patterns that need individual review |

**Efficient sequence**: Filter to `root` → decide all roots → filter to `child` → bulk-skip redundant children → filter to `none` → handle singletons → blank sweep.

---

## Recognizing Common Pattern Categories

Knowing what you're looking at speeds up decisions:

### Strip (strip these) — high confidence

- **Full instrument names**: "Patient Health Questionnaire", "Brief Pain Inventory", "Neuro-QOL"
- **Scale/subscale names**: "Scale of Independent Behavior", "SF-12 Health Survey"
- **Instructional boilerplate**: "Please respond to each item", "Check all that apply", "For each of the following"
- **Response anchors in definitions**: "Not at all / Extremely", "0 = Never, 4 = Always"

### Skip (false positives) — these are NOT patterns to strip

- **Generic English phrases**: "I felt", "Return to", "How often" — too common, not instrument-specific
- **Clinical content**: Disease names, symptoms, procedures that carry semantic meaning
- **Short acronyms without context**: "PET" (imaging), "OMB" (government), "MRI" unless part of a questionnaire name
- **Fragments under 3 tokens**: Higher false-positive risk; review carefully

### Modify — boundaries are wrong

- Detected `I got enough sleep in the past 7 days` but only `in the past 7 days` is boilerplate → modify to the shorter phrase
- Detected `Patient Health Questionnaire depression` — the last word isn't part of the instrument name → modify to remove it

### Substitute — replace, don't delete

- Detected `Considering your level of difficulty, you have` — deleting leaves broken grammar. Substitute with a clean connector phrase if needed.
- Rare in practice (typically <2% of decisions)

---

## Semantic Retention: When NOT to Delete

The goal of stripping is to remove **noise** (repeated instrument names, boilerplate
preambles) without destroying **signal** (clinical content, semantic meaning). Two
decisions help preserve meaning when pure deletion would cause information loss:

### Use substitute when deletion loses meaning

If a pattern like `Patient-Reported Outcomes Measurement Information System (PROMIS)`
appears at the start of many definitions, deleting it entirely removes the instrument
reference. If downstream analysis benefits from knowing *which instrument family* a
CDE belongs to, **substitute** with a short form (e.g., `PROMIS`) instead of deleting.

**When to substitute**:
- Deletion would leave orphaned grammar ("the" before a deleted name)
- The pattern contains both boilerplate *and* a meaningful identifier
- You want a shorter reference preserved, not total removal

### Use modify when boundaries are wrong

If the miner detected `Patient Health Questionnaire depression screening` but
`depression screening` is meaningful clinical content, **modify** to trim the
pattern to just `Patient Health Questionnaire`. Only the modified (shorter) text
gets stripped; the clinical content stays.

**When to modify**:
- The detected pattern extends beyond the actual instrument/boilerplate boundary
- A shorter prefix or suffix is the real repeated element
- The "extra" text carries clinical or semantic meaning

### The principle

Ask: *"After stripping this pattern from every CDE where it appears, does each
CDE still make sense on its own?"* If not, use substitute or modify to preserve
the meaningful portion.

---

## Efficient Workflow Summary

1. **Sort by tinyid_count** (click header twice for descending) — highest-impact patterns first
2. **Enable tree sort** (`T`) — see containment hierarchy
3. **Filter to `root`** — decide on parent patterns first
4. **Evaluate each root**: strip (real instrument/boilerplate) or skip (false positive / too generic)
5. **Propagate or bulk-skip** children of decided roots
6. **Filter to `child`** — handle any children that need different decisions than their parents
7. **Filter to `none`** — handle singleton patterns (no tree relationships)
8. **Blank sweep**: filter decision to `blank`, Ctrl+A, `S`
9. **Verify**: status bar shows `?0` and `tinyIds: N/N` (full coverage)
10. **Save**: Ctrl+S (server mode) or Save As (standalone)

### Time expectation

For a typical `needs_review.tsv` with ~1,300 high-priority patterns:

- Tree roots: ~100-150 decisions (many are obvious instrument families)
- Tree children: mostly bulk-skipped after root decisions
- Singletons: ~400-600 individual decisions (but many fall into recognizable categories)
- Blank sweep: covers the remaining obvious strips

An experienced curator can process a high-priority file in 1-2 hours using this workflow.

---

## Tracking Your Progress

The **status bar** at the bottom shows real-time progress:

```
needs_review.tsv — 1320 rows (5 selected) | ✓800  ✗120  ✎4  ⇄2  ⚑10  ?384  | tinyIds: 14,200/18,502  server
                                             strip skip  mod sub  flup undecided   decided/total
```

- **`?384`** = 384 rows still undecided — this is your countdown
- **`⚑10`** = 10 flagged for followup — these count as undecided
- **`tinyIds: 14,200/18,502`** = your decisions cover 14,200 of 18,502 unique CDE identifiers
- When `?0` and tinyIds shows full coverage, you're done

---

## References

- [TSV Editor Cheatsheet](tsv-editor-cheatsheet.md) — keyboard shortcuts, filters, visual cues
- [Print Cheatsheet](cheatsheets/tsv-editor.html) — two-page landscape PDF with interface mockup
- [Pattern Curation Guide](curation-guide.md) — deeper technical context on pattern types and pipeline mechanics
- [Distributed Curation](vignettes/distributed-curation.md) — multi-curator setup and merge workflow
