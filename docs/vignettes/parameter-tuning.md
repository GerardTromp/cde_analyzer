# Vignette: Parameter Tuning by Dataset Size

A side-by-side comparison of parameter settings for small and large CDE
datasets, with guidance on diagnosing when defaults need adjustment.

## What This Vignette Covers

The CDE Analyzer's default parameters are tuned for mid-to-large corpora
(~10K-25K CDEs). Smaller datasets need lower thresholds to avoid aggressive
filtering, and larger datasets benefit from parallelism tuning. This vignette
covers:

- How to recognize when parameters need adjustment
- Phase-by-phase parameter tables with recommended ranges
- The most dataset-sensitive parameter (`min_parent_tinyids`)
- Three methods for setting parameters, with reproducibility guidance

**Prerequisites**: Familiarity with the [Quickstart](quickstart.md) walkthrough
and the [Pipeline Orchestration](pipeline-orchestration.md) variable system.

**Related documentation**:

- [phrase_miner reference](../help/phrase_miner.md) — mining parameters
- [pattern_util reference](../help/pattern_util.md) — coalescing and field analysis
- [workflow reference](../help/workflow.md) — `--set` and config files

---

## 1. Two Reference Datasets

All examples in this vignette use real metrics from two production runs:

| Property | scheuermann08 | allcde01 |
|----------|---------------|----------|
| CDE count | 1,148 | 22,743 |
| Domain | Neuro/rehabilitation (focused) | All NLM CDEs (broad) |
| Phase 1 patterns mined | 56 instruments | ~1,300 instruments |
| Phase 1 patterns curated | 136 (105 T1 + 31 T2) | 444 |
| Phase 2 patterns coalesced | 590 → 85 (after field analysis) | ~13,640 → ~600 |
| Phase 3 runtime | ~30 seconds | ~4.5 minutes |

---

## 2. Phase 1: Instrument Detection

Phase 1 parameters are generally robust across dataset sizes. The main
tuning knob is the iterative harvesting threshold.

| Parameter | Small (~1K) | Large (~22K) | Default | How to set |
|-----------|------------|-------------|---------|-----------|
| `workers` | 0 (auto) | 4-8 | 0 | `--set "workers=N"` |
| `min_count` (diagnose) | 5 | 11 | 2 | Scaffold uses dynamic formula |
| `min_prefix_tinyids` | 2 | 2 | 2 | Rarely needs changing |

### `workers`

Controls parallelism for `discover_verbatim` and `strip_instruments`.
Value `0` auto-detects CPU count with headroom. For datasets under 5K CDEs,
auto-detection is fine. For larger datasets, explicit values (4-8) can
improve throughput.

```bash
# Via --set
--set "workers=4"

# Via config file (phase1_output/instrument_stripping_config.yaml)
workers: 4
```

### `min_count` in iterative harvesting

The minimum number of CDEs a residual pattern must appear in to be considered
a real instrument. The scaffold script calculates this dynamically:

```
min_count = max(round(N * 0.0005), 5)
```

| Dataset size | Dynamic min_count |
|-------------|-------------------|
| 500 CDEs | 5 |
| 1,148 CDEs | 5 |
| 5,000 CDEs | 5 |
| 10,000 CDEs | 5 |
| 22,743 CDEs | 11 |
| 50,000 CDEs | 25 |

If you run iteration manually, pass `--min-count` to `diagnose_strip`:

```bash
cde-analyzer diagnose_strip \
    -i iter_stripped.json -m CDE -o sanity.tsv \
    --min-count 11 --suggest-patterns --emit-tinyids
```

---

## 3. Most Influential Parameters (Phase 2)

Phase 2 parameters drive the balance between false positives (noisy curation
queue) and false negatives (missed real phrases). Three runs on the same
22,743-CDE corpus illustrate the impact:

| Parameter | allcde01 (strict) | allcde03 (midway) | allcde02 (lax) |
|-----------|:-----------------:|:-----------------:|:--------------:|
| `min_parent_tinyids` | 20 | **5** | 5 |
| `min_field_count` | 6 | **4** | 3 |
| `min_tokens` | 3 | **2** | 2 |
| `k_max` | 25 | **90** | 90 |
| Coalesced patterns | 138 | 2,132 | 2,132 |
| **After field analysis** | **86** | **1,480** | **1,599** |

### Impact ranking

1. **`min_parent_tinyids`** — highest impact. Controls how many CDEs must
   share a parent phrase for sub-phrases to survive coalescing. Changing
   from 20→5 on the same corpus increased output by **18.6x** (86→1,599).
   This single parameter accounts for the largest share of the difference.

2. **`min_field_count`** — high impact. The field analysis filter removes
   patterns appearing in fewer than N fields. Tightening from 3→6 cuts an
   additional ~25% of patterns. Effective for trimming low-frequency noise
   without touching the coalescing stage.

3. **`k_max`** — moderate impact, mostly on mining phase. Mining is
   top-down (k_max→k_min). High-k passes with zero hits are essentially
   free; execution only slows around k≈30 where hits start appearing.
   Setting k_max=90 captures very long phrases intact with negligible
   cost. The coalescer and field filters determine what survives.

4. **`min_tokens`** — low-to-moderate impact. Lowering from 3→2 admits
   bigrams (two-word patterns), which include useful instrument
   abbreviations but also some noise. Impact is modest because most
   meaningful patterns are 3+ tokens.

5. **`k_min`** — negligible impact. The value 3 is standard and rarely
   needs changing.

### The false-positive / false-negative tradeoff

| Setting style | Curator queue | False positives | False negatives |
|---------------|:------------:|:---------------:|:---------------:|
| Strict (allcde01) | ~86 | Very few | Many real phrases missed |
| Lax + Zipf split (allcde03) | ~582 high + 898 low | Controlled | Very few |
| Lax (allcde02) | ~1,599 | Many | Very few |

The curator's time is the bottleneck. Rather than tightening mining
parameters (which risks false negatives), use permissive settings and
split the curation queue by word commonality:

```bash
cde-analyzer pattern_util --split-priority needs_review.tsv --split-auto-skip
```

This uses wordfreq Zipf scores to separate patterns into:

- **High-priority** (582 patterns): at least one domain-specific or
  uncommon word — assign to multiple reviewers
- **Low-priority** (898 patterns): all words are common English — one
  reviewer fast-triages, pre-filled as `skip`

The Zipf threshold (default 4.0 ≈ top ~6K English words) cleanly separates
domain terms ("Chiari malformation", "EEG ictal", "Polysomnography") from
generic phrases ("in the", "Have you had", "one of the").

Both files feed back into the same curation ledger, so future runs
auto-resolve all decisions.

---

## 4. Phase 2: Phrase Mining — Parameter Details

Phase 2 is where parameter sensitivity is highest. The `min_parent_tinyids`
threshold in particular can make the difference between a useful output and
an empty one.

| Parameter | Small (~1K) | Large (~22K) | Default | How to set |
|-----------|------------|-------------|---------|-----------|
| `min_parent_tinyids` | **2** | 10–20 | 20 | `--set "min_parent_tinyids=N"` |
| `k_max` | 25–90 | 90 | 25 | `--set "k_max=N"` |
| `k_min` | 3 | 3 | 3 | `--set "k_min=N"` |
| `min_field_count` | **3-4** | 4–6 | 6 | `--set "min_field_count=N"` |
| `min_tokens` | 2–3 | 2–3 | 3 | `--set "min_tokens=N"` |
| `workers` | 0 | 4-8 | 0 | `--set "workers=N"` |

### Deep dive: `min_parent_tinyids`

This is the most dataset-sensitive parameter in the entire pipeline. It
controls how many CDEs a parent phrase must appear in for its sub-phrases to
survive coalescing.

**What happened with scheuermann08 (1,148 CDEs):**

1. The phrase miner found 857 candidate phrases
2. Discovery expanded these to 1,235 verbatim patterns
3. Coalescing with default `min_parent_tinyids=20` retained only **4 patterns**
4. Field analysis reduced these to **2** — effectively useless

The default threshold of 20 was too aggressive for a 1,148-CDE corpus.
Most parent phrases in a focused domain appear in fewer than 20 CDEs.

**Fix**: Override to `min_parent_tinyids=2`:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "input_json=inst_stripped.json" \
    --set "output_dir=phase2_output" \
    --set "min_parent_tinyids=2"
```

Result: 590 coalesced patterns → 85 after field analysis. A usable output.

**With allcde01/02/03 (22,743 CDEs)**, the three runs show the sensitivity
at scale:

| `min_parent_tinyids` | `min_field_count` | Coalesced | After field analysis |
|:--------------------:|:-----------------:|:---------:|:--------------------:|
| 20 (allcde01) | 6 | 138 | 86 |
| 5 (allcde03) | 4 | 2,132 | 1,480 |
| 5 (allcde02) | 3 | 2,132 | 1,599 |

With allcde03, `--split-priority` further split the 1,480 into 582
high-priority + 898 low-priority patterns using Zipf frequency scoring.

### How to diagnose

After the `coalesce_patterns` step, check the pattern count in
`coalesced.tsv`:

- **< 10 patterns**: Your `min_parent_tinyids` is almost certainly too high.
  Lower it to 2-5.
- **10-100 patterns**: Reasonable for a small-to-medium dataset.
- **100-1000 patterns**: Typical for a large dataset. Field analysis will
  filter further.
- **> 1000 patterns**: Normal for very large corpora. The field analysis
  filters (`min_field_count`, `min_tokens`) will do heavy lifting.

### Recommended heuristic

A rough guideline for `min_parent_tinyids`:

```
min_parent_tinyids ≈ max(2, N / 1000)
```

| CDEs | Suggested threshold |
|------|-------------------|
| 500 | 2 |
| 1,000 | 2 |
| 5,000 | 5 |
| 10,000 | 10 |
| 20,000 | 10–20 |
| 50,000 | 50 |

This is a starting point — inspect the coalesced output and adjust.

### `min_field_count`

After coalescing, the field analysis step removes patterns appearing in
fewer than `min_field_count` CDEs in any single field. For small datasets,
lower this to 3 or 4:

```bash
--set "min_field_count=3"
```

For large datasets, 4–6 is the practical range. The allcde runs show:
`min_field_count=6` yields 86 patterns, `min_field_count=3` yields 1,599.
A value of 4 targets the middle ground.

### `k_max` and `k_min`

These control the k-mer mining window (maximum and minimum phrase length
in tokens).

**`k_max`**: The mining algorithm works top-down (k_max→k_min). Passes at
high k values with zero hits complete instantly, so `k_max=90` costs
virtually nothing extra over `k_max=25`. Execution only slows around k≈30
where hits start appearing. The benefit of a high `k_max` is capturing
very long repeated phrases (complete questionnaire prompts, definition
boilerplate) intact rather than relying on the dedup pre-pass.

**Recommendation**: Use `k_max=90` for all dataset sizes.

Lower `k_min` to 2 if you want to catch two-word patterns, but expect more
noise in the output.

---

## 5. Phase 3: Branching Strip

Phase 3 has no content-sensitive parameters — all pattern decisions were made
in Phase 1 and 2 curation. The only tuning is performance:

| Parameter | Small (~1K) | Large (~22K) | Default |
|-----------|------------|-------------|---------|
| `workers` | 0 | 4-8 | 0 |

Phase 3 runs 10 sequential strip steps. With allcde01 (22,743 CDEs), total
runtime is ~4.5 minutes. Workers primarily affect individual step speed.

!!! note "No content parameters"
    The patterns applied in Phase 3 come entirely from your Phase 1 curated
    patterns (via `--generate-strip-patterns`) and Phase 2 curated patterns.
    Temporal patterns are auto-expanded from seed configurations. There is
    nothing to tune for the strip itself — quality depends on curation.

---

## 6. Setting Parameters — Three Methods

### Config file (recommended for reproducibility)

Create `{output_dir}/{workflow_name}_config.yaml`:

```yaml
# phase2_output/phrase_stripping_config.yaml
min_parent_tinyids: 2
min_field_count: 3
workers: 4
```

This persists with your project output and documents exactly what settings
were used.

### `--set` overrides (quick experimentation)

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "output_dir=phase2_output" \
    --set "min_parent_tinyids=2" \
    --set "min_field_count=3"
```

Ephemeral — not saved anywhere. Good for testing, but remember to create a
config file once you find settings that work.

### Scaffold script (multi-phase consistency)

Edit the `PARAMETERS` section in the generated script:

```bash
# ── PARAMETERS ──
MIN_PARENT_TINYIDS=2
MIN_FIELD_COUNT=3
WORKERS=4
```

The scaffold passes these as `--set` overrides. The script itself serves as
documentation of your parameter choices.

---

## 7. Quick Reference Table

All tunable parameters across the pipeline, with defaults and recommended
ranges:

| Parameter | Phase | Default | Small (~1K) | Large (~22K) | Impact | Flag |
|-----------|-------|---------|------------|-------------|--------|------|
| `min_parent_tinyids` | 2 | 20 | **2** | 10–20 | Highest | `--set "min_parent_tinyids=N"` |
| `min_field_count` | 2 | 6 | **3-4** | 4–6 | High | `--set "min_field_count=N"` |
| `k_max` | 2 | 25 | 90 | 90 | Moderate | `--set "k_max=N"` |
| `min_tokens` | 2 | 3 | 2–3 | 2–3 | Low-Mod | `--set "min_tokens=N"` |
| `k_min` | 2 | 3 | 3 | 3 | Low | `--set "k_min=N"` |
| `workers` | All | 0 | 0 | 4-8 | Perf | `--set "workers=N"` |
| `min_prefix_tinyids` | 1, 2 | 2 | 2 | 2 | Low | `--set "min_prefix_tinyids=N"` |
| `min_count` (diagnose) | 1 iter | 2 | 5 | 11 | — | `--min-count N` (CLI arg) |

**Bold** values indicate parameters that differ significantly from defaults
for small datasets.

---

## 8. Troubleshooting

### "Phase 2 produced almost no patterns"

**Symptom**: `coalesced_fields.tsv` has fewer than 10 rows.

**Cause**: `min_parent_tinyids` is too high for your dataset.

**Fix**: Re-run with a lower threshold. Use `--from-step coalesce_patterns`
to skip mining and discovery:

```bash
cde-analyzer workflow run workflows/phrase_pipeline.yaml \
    --set "output_dir=phase2_output" \
    --set "min_parent_tinyids=2" \
    --from-step coalesce_patterns
```

### "Phase 2 has thousands of noisy patterns"

**Symptom**: `coalesced_fields.tsv` has 2,000+ rows, many are short or
low-frequency.

**Cause**: `min_field_count` and `min_tokens` are too permissive.

**Fix**: Raise the field analysis filters:

```bash
--set "min_field_count=8" --set "min_tokens=4"
```

### "Mining takes too long"

**Symptom**: `mine_phrases` step takes over 10 minutes.

**Cause**: Large corpus with `workers=0` defaulting to fewer cores than
available.

**Fix**: Set workers explicitly:

```bash
--set "workers=8"
```

Also check `workers` — explicit values (4-8) can help. Note that high
`k_max` values (e.g., 90) do **not** increase mining time significantly
because the algorithm works top-down and high-k passes with zero hits
complete instantly.
