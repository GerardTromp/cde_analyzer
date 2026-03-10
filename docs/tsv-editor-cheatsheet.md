# TSV Pattern Editor — Cheatsheet

> **Version**: v0.9.6 &nbsp;|&nbsp; **Visual reference**: [`cheatsheets/tsv-editor.html`](cheatsheets/tsv-editor.html) (print-friendly, includes interface mockup)

---

## Launch

```bash
# Full installation — server mode (Ctrl+S saves in-place)
cde-analyzer pattern_util --edit needs_review.tsv

# Standalone zipapp — no dependencies beyond Python 3.10+
python cde_editor.pyz needs_review.tsv
```

Opens at `http://localhost:8777`. The editor auto-detects curation columns (`decision`, `modification`) and moves them to the front of the grid.

---

## 5-Minute Curation

### 1. Remove false positives

Scan patterns. Select bad rows (click checkboxes, Shift+click for ranges). Press **R**.

Common false positives: generic phrases ("I felt", "Return to"), imaging techniques (PET, MRI unless actual questionnaire names), government agencies (OMB), overly short acronyms.

### 2. Fix partial matches

Select partially correct rows. Press **M** to mark as `modify`. Double-click the **modification** column and type the corrected pattern text.

For multiple rows sharing the same modification, **group** them first (select 2+ rows → click **[Group]** → set one member's modification → click **[Propagate]**).

### 3. Substitute instead of delete

For patterns that should be *replaced* rather than deleted, select and press **S**. Double-click the **modification** column and type the replacement text that will appear in the output.

### 4. Mass keep — approve the rest

1. Set the decision filter to **`blank`** (dropdown in the filter row)
2. **Ctrl+A** to select all visible (undecided) rows
3. Press **K** to set them all to `keep`
4. Reset filter to `(all)` to verify

### 5. Save

**Ctrl+S** (server mode) or **Save As** button (standalone mode).

---

## The 5 Decisions

| Decision | When to use | What happens |
|----------|-------------|--------------|
| **keep** | Real instrument/scale name | Stripped (deleted) from CDE text |
| **remove** | False positive — not an instrument | Excluded from final pattern set |
| **modify** | Partially correct text | `modification` becomes the new pattern to strip |
| **substitute** | Replace, don't delete | `modification` replaces the matched text in output |
| **followup** | Needs more evaluation | Flagged for later review; counts as undecided |

!!! note "modify vs substitute"
    Both use the `modification` column with different semantics.
    **Modify** changes *what gets stripped* (corrects the pattern text before deletion).
    **Substitute** changes *what appears in the output* (matched text is replaced, not deleted).

Blank decision = treated as `keep` by the pipeline (safe default). Followup = treated as undecided.

---

## Keyboard Shortcuts

### Decision Assignment

| Key | Action |
|-----|--------|
| **K** | Set selected → `keep` |
| **R** | Set selected → `remove` |
| **M** | Set selected → `modify` |
| **S** | Set selected → `substitute` |
| **F** | Set selected → `followup` |
| **T** | Toggle tree sort (no rows selected) |

Requires rows selected and not editing a cell (except T which requires no selection).

### Navigation

| Shortcut | Action |
|----------|--------|
| **Ctrl+A** | Select all visible rows |
| **Ctrl+U** | Deselect all |
| **Ctrl+Z** / **Ctrl+Shift+Z** | Undo / Redo (50 levels) |
| **Ctrl+S** | Save (server mode) |
| **Ctrl+F** | Focus first filter |
| **Ctrl+Shift+F** | Clear all filters |
| **Delete** | Delete selected rows |
| **Double-click** | Edit cell inline |
| **Tab** / **Shift+Tab** | Next / previous column while editing |
| **Enter** / **Escape** | Commit / cancel edit |
| **Shift+click** checkbox | Range-select rows |

---

## Merge Groups

When several patterns share the same modification:

1. Select 2+ related rows → click **[Group]** → they get tagged `G1`
2. Set **one** member's decision + modification text
3. Click **[Propagate]** → all group members receive the same decision + modification

Propagation copies the source row's actual decision type — works with both `modify` and `substitute`. Multiple groups (G1, G2, G3…) propagate independently.

---

## Containment Tree

The editor automatically detects **prefix-containment relationships** between patterns. Pattern A *contains* pattern B when:

1. A is a **word-level prefix** of B (e.g., "Scale of" is a prefix of "Scale of the difficulty…")
2. A's **tinyIds ⊇ B's tinyIds** (every CDE matching B also matches A)

When containment is found, a virtual **tree** column appears as column #3. This column is not saved to the TSV file.

### Reading the Tree Column

| Display | Meaning |
|---------|---------|
| **▶ 12** (purple badge) | Root/parent with 12 descendants — click ▶ to expand |
| **▼ 12** (purple badge) | Expanded parent — click ▼ to collapse |
| **· ⊃ Scale of** | Child at depth 1 — contained by "Scale of" |
| **·· ⊃ Scale of the** | Child at depth 2 — contained by "Scale of the" |
| *(empty)* | Singleton — no containment relationship |

### Tree Controls

| Control | Action |
|---------|--------|
| **☰ Tree** button / **T** key | Toggle tree sort — groups children under parents (DFS order, sorted by tinyid_count) |
| **⊃ Propagate** button | Copy decision from parent(s) to all contained children |
| **Tree filter** dropdown | Filter to `root`, `child`, or `none` (singletons) |
| **Click ▶/▼** | Collapse/expand individual subtrees |

### Tree-Assisted Curation Workflow

1. Press **T** to enable tree sort — parents appear above their children
2. Set **keep** on the parent pattern (e.g., "Scale of" with 409 tinyIds)
3. Children are visible below — most are longer phrases whose tinyIds are fully contained
4. Select children → **R** to remove (since the parent already covers them)
5. Or use **⊃ Propagate** to bulk-copy the parent's decision to all descendants

!!! tip "Why containment matters"
    If "Scale of" (409 tinyIds) fully contains "Scale of the difficulty…" (133 tinyIds), keeping the parent and removing the children is safe — the parent pattern already strips all text matched by its children.

### Status Bar

When containment trees exist, the status bar shows: `⊃N trees, M contained`

---

## Column Filters

Each column has a filter below the header. The **decision column** uses a dropdown; other columns use text input.

| Filter | Matches |
|--------|---------|
| `abc` | Contains "abc" (case-insensitive) |
| `!abc` | NOT containing "abc" |
| `=blank` | Empty cells only |
| `!blank` | Non-empty cells only |
| `>10` / `<5` | Numeric comparisons |
| `=10` / `!=5` | Numeric equals / not-equals |
| `foo\|bar` | "foo" OR "bar" |

Decision dropdown: `(all)` · `blank` · `filled` · `keep` · `remove` · `modify` · `substitute` · `followup`

---

## Visual Cues

| Element | Meaning |
|---------|---------|
| Green / Red / Amber / Cyan / Purple badge | Decision: keep / remove / modify / substitute / followup |
| Blue left border | `def-only` field profile |
| Orange left border | `desig-only` field profile |
| Green left border | `both` / `both-all` field profile |
| Purple left border | `mixed` field profile |
| Colored right border + badge | Merge group membership (G1, G2… 8 rotating colors) |

---

## Status Bar

```
needs_review.tsv -- 458 rows (3 selected) | ✓430  ✗24  ✎4  ⇄2  ⚑1  ?0  | tinyIds: 18,240/18,502  server
                                             keep  rem  mod sub  flup undecided   decided/total
```

- **Counts update in real-time** as you assign decisions
- **`⚑N`** = flagged for followup (counts as undecided)
- **`?0`** = all rows decided — you're done
- **`tinyIds: N/M`** = tinyId coverage (decided / total)
- **`server`** / **`standalone`** = save mode indicator

---

## Toolbar Reference

| Button | Action |
|--------|--------|
| **Save** | Write to file (server mode only) |
| **Save As** | Download current TSV |
| **Open** | Load a different TSV file |
| **+ Add** | Insert new empty row |
| **x Del** | Delete selected rows |
| **Up / Down** | Move selected rows |
| **Categorize** | Set column value for selected (modal) |
| **Merge** | Combine rows (merge tinyIds, keep longest pattern) |
| **Split** | Download separate TSVs by `field_profile` |
| **☰ Tree** | Toggle tree sort (groups children under parents) |
| **⊃ Propagate** | Propagate decision from parents to contained children |

---

## After Curation

Return your curated TSV. The pipeline will:

1. **Merge** your edits with auto-resolved patterns
2. **Apply decisions**: keep → strip, modify → rewrite + strip, substitute → replace, remove → exclude
3. **Update the curation ledger** for future incremental runs
4. **Strip/substitute** from CDE text fields

```bash
# Resume the pipeline after curation
cde-analyzer workflow resume --state-file output/.workflow_state.json
```

Multiple curators? The coordinator runs `--merge-curation` to reconcile decisions with inter-rater agreement statistics.

---

## Quote Escaping Across Formats

When searching the source JSON for patterns you see in the editor, be aware that quote characters are escaped differently in each format:

| Context | How `"` appears |
|---------|-----------------|
| JSON file | `\"` (backslash escape) |
| TSV file | `""` (doubled quote inside quoted field) |
| Editor / Python | `"` (literal — escapes are parsed away) |

If a pattern contains quotes (e.g., `COVID-19 Mitigation Policy`), search the JSON for the surrounding text without quotes to avoid escaping mismatches.

---

## Tips

- **Undo is generous** — 50 levels. Don't fear mistakes.
- **Shift+click** checkboxes for range selection — much faster than individual clicks.
- **Double-click** a decision badge to edit via dropdown (single row).
- **The `K` shortcut is your friend** — after triaging removes/modifies, filter to blank, Ctrl+A, K. Done.
- **TinyId columns** collapse to 3 IDs + count badge. Click to expand.
- **`tinyid_count`** — read-only column auto-computed from `tinyIds`. Displayed as column 2.
- **`tree`** — virtual column showing containment hierarchy. Displayed as column 3 when containment exists. Not saved to TSV.
- **Drag row numbers** to reorder by drag-and-drop.
- **Column sorting** — click any column header to sort ascending/descending. Activating tree sort disables column sort.
- **Column layout** — `decision`, `tinyid_count`, `tree`, and `modification` are auto-moved to front. Save order unchanged.
