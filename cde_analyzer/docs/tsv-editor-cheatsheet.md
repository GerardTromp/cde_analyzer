# TSV Pattern Editor — Curation Cheat Sheet

> **Version**: v0.8.0 &nbsp;|&nbsp; **File**: `cde_editor.pyz` (standalone) or `cde-analyzer pattern_util --edit FILE`

---

## Quick Start

```bash
# Standalone zipapp (no dependencies beyond Python 3.10+)
python cde_editor.pyz needs_review.tsv

# Or from the full CDE Analyzer installation
cde-analyzer pattern_util --edit needs_review.tsv
```

Opens at `http://localhost:8777` in your browser. Edit, then **save** (Ctrl+S in server mode).

---

## Editor Layout

```
+==========================================================================================+
| TOOLBAR                                                                                  |
|  [Save] [Save As] [Open]  |  [+ Add] [x Del] [Up] [Down]  |  [Categorize] [Merge]      |
|  [Split]  |  [Keep] [Remove] [Modify]  |  [Group] [Propagate]  |  [Undo] [Redo]         |
|            ~~green~~ ~~red~~~~ ~~amber~~                                                  |
+==========================================================================================+
|  GRID HEADER ROW                                                                         |
| [ ] | #  | decision v | modification | group_key     | pattern         | ... | notes     |
|-----+----+------------+--------------+---------------+-----------------+-----+-----------|
|  FILTER ROW                                                                              |
|     |    | [(all)  v] | [Filter...  ]| [Filter...   ]| [Filter...     ]| ... |[Filter.. ]|
+==========================================================================================+
|  DATA ROWS                                                                               |
| [x] |  1 | keep       | (greyed)     | SF-12         | 12-item Short.. | ... |           |
| [ ] |  2 | keep       |              | SF-12         | 12-item Short.. | ... |           |
| [x] |  3 | remove     |              | Gas Exchange  | Gas Exchange    | ... |           |
| [x] |  4 | modify     | in past 7 d..| PROMIS        | I got enough s..| ... | G1        |
| [x] |  5 | modify     | in past 7 d..| PROMIS        | I had difficul..| ... | G1        |
|     |    |            |              |               |                 |     |           |
| ... |    |            |              |               |                 |     |           |
+==========================================================================================+
|  STATUS BAR                                                                              |
|  needs_review.tsv -- 458 rows (3 selected) | check 430  x 24  pencil 4  ?0    server    |
+==========================================================================================+
```

### Visual Cues

| Indicator | Meaning |
|-----------|---------|
| Green badge in decision column | `keep` — pattern will be stripped (deleted) |
| Red badge in decision column | `remove` — pattern will be excluded (false positive) |
| Amber badge in decision column | `modify` — pattern text changed to modification before stripping |
| Cyan badge in decision column | `substitute` — matched text replaced with modification text |
| Blue left border on row | `def-only` field profile (appears in definitions only) |
| Orange left border on row | `desig-only` field profile (designations only) |
| Green left border on row | `both` / `both-all` field profile (both fields) |
| Purple left border on row | `mixed` field profile |
| Colored right border on row | Merge group membership (G1, G2, ... — 8 rotating colors) |
| Group badge in notes column | Small colored chip showing `G1`, `G2`, etc. |

---

## The Curation Task

Each row is a candidate **instrument pattern** detected in CDE text fields.
Your job: decide what happens to each pattern.

| Decision | When to use | What happens |
|----------|-------------|--------------|
| **keep** | Pattern is a real instrument/scale name | Stripped (deleted) from CDE text |
| **remove** | False positive — generic phrase, not an instrument | Excluded from final pattern set |
| **modify** | Partially correct — needs edited text | `modification` text becomes the new pattern to strip |
| **substitute** | Pattern should be replaced, not deleted | `modification` text replaces the matched pattern in CDE text |

> **modify vs substitute**: Both use the `modification` column, but with different semantics.
> *Modify* changes **what gets stripped** (the pattern text is replaced before stripping).
> *Substitute* changes **what appears in the output** (matched text is replaced with the modification text instead of being deleted).

**Blank decision** = treated as `keep` by the pipeline (safe default).

---

## Keyboard Shortcuts

### Decision Assignment (fastest method)

| Key | Action | Requirement |
|-----|--------|-------------|
| **K** | Set selected rows to `keep` | Rows selected, not editing a cell |
| **R** | Set selected rows to `remove` | Rows selected, not editing a cell |
| **M** | Set selected rows to `modify` | Rows selected, not editing a cell |
| **S** | Set selected rows to `substitute` | Rows selected, not editing a cell |

### Navigation & Editing

| Shortcut | Action |
|----------|--------|
| **Ctrl+A** | Select all visible rows |
| **Ctrl+Z** | Undo |
| **Ctrl+Shift+Z** | Redo |
| **Ctrl+S** | Save (server mode) |
| **Ctrl+F** | Focus first filter input |
| **Delete** | Delete selected rows |
| **Double-click** cell | Edit cell inline |
| **Tab** / **Shift+Tab** | Move to next/previous column while editing |
| **Enter** | Commit cell edit |
| **Escape** | Cancel cell edit |
| **Shift+click** checkbox | Range-select rows |

---

## Recommended Curation Workflow

### Step 1: Triage — Remove False Positives

1. Scan through the patterns looking for obvious non-instruments
2. Select the offending rows (click checkboxes, or Shift+click for ranges)
3. Press **R** to mark them `remove`

Common false positives: generic phrases ("I felt", "Return to"), imaging
techniques (PET, MRI, DTI unless they are actual questionnaire names),
government agencies (OMB), overly short acronyms.

### Step 2: Modify — Fix Partial Matches

1. For patterns that are partially correct, select the row(s)
2. Press **M** to mark as `modify`
3. Double-click the **modification** column and type the corrected text
4. If multiple rows should share the same modification, use **Groups** (see below)

### Step 3: Mass Keep — Approve the Rest

1. Set the **decision filter** to `blank` (dropdown in the filter row)
2. Press **Ctrl+A** to select all visible (undecided) rows
3. Press **K** to set them all to `keep`
4. Reset the filter to `(all)` to confirm

```
 FILTER ROW — Decision Column
+-------------------+
| blank           v |   <-- shows only undecided rows
+-------------------+
    then Ctrl+A, K

 Result: all remaining rows marked "keep"
```

### Step 4: Save

- **Server mode** (launched via `cde-analyzer pattern_util --edit`): Ctrl+S saves in-place
- **Standalone mode** (launched via zipapp or drag-drop): Use **Save As** to download

---

## Merge Groups — Shared Modifications

When several patterns should all be modified to the **same replacement text**
(e.g., four PROMIS sleep items all mapping to "in past 7 days [PROMIS]"):

### Assigning a Group

```
 1. Select 2+ rows that share a modification
 2. Click [Group] in toolbar (or see it appear on the far right of the toolbar)
 3. All selected rows get tagged G1 in their notes column

 Row display after grouping:
 +----+--------+------------------+---------------------------------+----------+
 | #  | dec.   | modification     | pattern                         | notes    |
 +----+--------+------------------+---------------------------------+----------+
 | 47 | modify | in past 7 d...   | I got enough sleep in past 7 d..| G1       |
 | 48 | modify |                  | I had difficulty falling asle.. | G1       |
 | 49 | modify |                  | I was satisfied with my sleep.. | G1       |
 | 50 | modify |                  | My sleep quality was...in past..| G1       |
 +----+--------+------------------+---------------------------------+----------+
                ^                                                     ^
                |-- fill in ONE row's modification                    |-- colored
                                                                         right border
```

### Propagating the Modification

1. Set **one** group member's decision to `modify` and type the replacement text
2. Click **[Propagate]** in toolbar
3. Confirmation dialog: "Propagate modifications for 1 group(s) (3 target rows)?"
4. All other group members receive `decision=modify` + the same modification text

```
 After propagation:
 +----+--------+------------------+---------------------------------+----------+
 | #  | dec.   | modification     | pattern                         | notes    |
 +----+--------+------------------+---------------------------------+----------+
 | 47 | modify | in past 7 d...   | I got enough sleep in past 7 d..| G1       |
 | 48 | modify | in past 7 d...   | I had difficulty falling asle.. | G1       |
 | 49 | modify | in past 7 d...   | I was satisfied with my sleep.. | G1       |
 | 50 | modify | in past 7 d...   | My sleep quality was...in past..| G1       |
 +----+--------+------------------+---------------------------------+----------+
                ^^^^^^^^^^^^^^^^^^^^-- propagated to all group members
```

Multiple groups can exist (G1, G2, G3, ...). Each propagates independently.

---

## Column Filters

Each column has a filter input in the row below the headers.

| Filter syntax | Matches |
|---------------|---------|
| `abc` | Cells containing "abc" (case-insensitive) |
| `!abc` | Cells NOT containing "abc" |
| `=blank` | Empty cells only |
| `!blank` | Non-empty cells only |
| `>10` | Numeric cells greater than 10 |
| `<5` | Numeric cells less than 5 |
| `foo\|bar` | Cells containing "foo" OR "bar" |

The **decision column** has a dropdown filter instead of free-text:

```
+-------------------+
| (all)           v |   All rows
| blank             |   Undecided rows (decision is empty)
| filled            |   Any decision set
| keep              |   Only "keep" rows
| remove            |   Only "remove" rows
| modify            |   Only "modify" rows
| substitute        |   Only "substitute" rows
+-------------------+
```

---

## Column Layout

When the TSV contains curation columns (`decision`, `modification`), they are
automatically **moved to the front** of the display (right after the checkbox
and row number columns). This puts the most important columns closest to where
you click, while the underlying data order stays unchanged for saving.

```
 Typical needs_review.tsv column display order:
 +---+----+----------+--------------+----------+---------+----------+-----+
 | x | #  | decision | modification | group_key| pattern | tinyIds  | ... |
 +---+----+----------+--------------+----------+---------+----------+-----+
  ^    ^    ^-- moved      ^-- moved     ^-- original column order follows
  |    |        to front       to front
  |    row number
  checkbox
```

---

## Other Toolbar Features

| Button | What it does |
|--------|-------------|
| **Save** | Write changes back to file (server mode only) |
| **Save As** | Download current TSV as a file |
| **Open** | Load a different TSV file |
| **+ Add** | Insert a new empty row (after selection, or at end) |
| **x Del** | Delete selected rows (also: Delete key) |
| **Up / Down** | Move selected rows up or down |
| **Categorize** | Set a column value for all selected rows (modal dialog) |
| **Merge** | Combine selected rows into one (merges tinyIds, keeps longest pattern) |
| **Split** | Download separate TSV files grouped by `field_profile` column |

---

## Status Bar

The bottom bar shows:

```
needs_review.tsv -- 458 rows (3 selected) (24 hidden by filter) | ✓430  ✗24  ✎4  ⇄2  ?0    server
                                                                   ^^^^  ^^^  ^^  ^^^  ^^
                                                                   keep  rem  mod sub  undecided
```

- **Counts update in real-time** as you assign decisions
- **`?0`** means all rows have a decision — you're done!
- **`server`** / **`standalone`** indicates the mode

---

## Saving Your Work

### Server Mode (recommended)

When launched with `cde-analyzer pattern_util --edit FILE` or `python cde_editor.pyz FILE`:
- **Ctrl+S** saves directly to the original file
- The file is overwritten in place
- Unsaved changes trigger a browser warning if you try to close the tab

### Standalone / Drag-Drop Mode

When you open the editor without a file argument and drag-drop a TSV:
- Use **Save As** to download the edited file
- The original file is not modified
- Rename and return the downloaded file to the pipeline coordinator

---

## Tips

- **Undo is generous** — 50 levels. Don't worry about mistakes.
- **Shift+click** checkboxes for range selection — much faster than clicking each row.
- **Double-click** the decision badge to change it via dropdown (one row at a time).
- **The `K` shortcut is your friend** — after triaging removes and modifies, filter to blank, Ctrl+A, K. Done.
- **TinyId columns** collapse long ID lists to the first 3 with a count badge. Click to expand.
- **Drag row numbers** to reorder rows by drag-and-drop.
- **Column sorting** — click any column header to sort ascending/descending.

---

## After Curation

Return your curated TSV file to the pipeline coordinator. The pipeline will:

1. **Merge** your `needs_review.tsv` with auto-resolved patterns
2. **Apply decisions**: keep rows are included, modify rows use the modification text, remove rows are excluded
3. **Update the curation ledger** for future incremental runs
4. **Strip patterns** from CDE text fields using the final curated set

If multiple curators review the same file, the coordinator will run
`cde-analyzer pattern_util --merge-curation` to reconcile decisions
with inter-rater agreement statistics.
