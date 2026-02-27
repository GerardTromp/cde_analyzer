# TSV Pattern Editor — Quickstart Guide

> **Version**: v0.8.1 &nbsp;|&nbsp; **Visual reference**: [`cheatsheets/tsv-editor.html`](cheatsheets/tsv-editor.html) (print-friendly, includes interface mockup)

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

## The 4 Decisions

| Decision | When to use | What happens |
|----------|-------------|--------------|
| **keep** | Real instrument/scale name | Stripped (deleted) from CDE text |
| **remove** | False positive — not an instrument | Excluded from final pattern set |
| **modify** | Partially correct text | `modification` becomes the new pattern to strip |
| **substitute** | Replace, don't delete | `modification` replaces the matched text in output |

!!! note "modify vs substitute"
    Both use the `modification` column with different semantics.
    **Modify** changes *what gets stripped* (corrects the pattern text before deletion).
    **Substitute** changes *what appears in the output* (matched text is replaced, not deleted).

Blank decision = treated as `keep` by the pipeline (safe default).

---

## Keyboard Shortcuts

### Decision Assignment

| Key | Action |
|-----|--------|
| **K** | Set selected → `keep` |
| **R** | Set selected → `remove` |
| **M** | Set selected → `modify` |
| **S** | Set selected → `substitute` |

Requires rows selected and not editing a cell.

### Navigation

| Shortcut | Action |
|----------|--------|
| **Ctrl+A** | Select all visible rows |
| **Ctrl+Z** / **Ctrl+Shift+Z** | Undo / Redo (50 levels) |
| **Ctrl+S** | Save (server mode) |
| **Ctrl+F** | Focus first filter |
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

## Column Filters

Each column has a filter below the header. The **decision column** uses a dropdown; other columns use text input.

| Filter | Matches |
|--------|---------|
| `abc` | Contains "abc" (case-insensitive) |
| `!abc` | NOT containing "abc" |
| `=blank` | Empty cells only |
| `!blank` | Non-empty cells only |
| `>10` / `<5` | Numeric comparisons |
| `foo\|bar` | "foo" OR "bar" |

Decision dropdown: `(all)` · `blank` · `filled` · `keep` · `remove` · `modify` · `substitute`

---

## Visual Cues

| Element | Meaning |
|---------|---------|
| Green / Red / Amber / Cyan badge | Decision: keep / remove / modify / substitute |
| Blue left border | `def-only` field profile |
| Orange left border | `desig-only` field profile |
| Green left border | `both` / `both-all` field profile |
| Purple left border | `mixed` field profile |
| Colored right border + badge | Merge group membership (G1, G2… 8 rotating colors) |

---

## Status Bar

```
needs_review.tsv -- 458 rows (3 selected) | ✓430  ✗24  ✎4  ⇄2  ?0    server
                                             keep  rem  mod sub  undecided
```

- **Counts update in real-time** as you assign decisions
- **`?0`** = all rows decided — you're done
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
- **Drag row numbers** to reorder by drag-and-drop.
- **Column sorting** — click any header to sort ascending/descending.
- **Column layout** — `decision` and `modification` are auto-moved to front. Save order unchanged.
