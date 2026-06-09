# Production Strip — Core-Scaling Benchmark

> **Version**: 1.5.1
> **Date**: 2026-06-08
> **Pipeline**: `workflows/production_strip.yaml` (Curator B reference patterns)
> **Corpus**: `cde_all_03_20260105_no-undrscr_nohtml.json` — 22,743 CDEs (allcde03)

## TL;DR — instance sizing

The production strip is **Amdahl-bound**: only `branching_strip` (and weakly the
substitution passes) parallelize; `quality_report` + `extract_embed` + JSON I/O form
a **~85 s serial floor** that no number of cores removes.

| If you care about… | Use | Why |
|---|---|---|
| **Cost efficiency** (best $/run) | **4 vCPU** | Captures 1.86× of the 2.30× max total speedup; 73% parallel efficiency on the strip |
| **Wall-clock, 2 variants** | **6–8 vCPU** | Knee of the total-time curve (~150 s); beyond this the serial floor dominates |
| **Wall-clock, all 7 variants** | **8–12 vCPU** | The strip cost scales ~linearly with variant count, so the parallel portion dominates and more cores keep paying off |

Past ~8 vCPU the **total** pipeline barely improves (148 s → 135 s from 8→12) because
the serial floor is already the majority of the run. AWS guidance: `c6i.xlarge`/`m6i.xlarge`
(4 vCPU) for cost, `c6i.2xlarge`/`m6i.2xlarge` (8 vCPU) for speed on the default 2-variant run.

## Results

### Total pipeline (default variants: MTSFPT, MTSTPT)

| vCPU (workers) | Total (s) | Speedup | Efficiency/core |
|---:|---:|---:|---:|
| 1  | 310.5 | 1.00× | 100% |
| 2  | 231.9 | 1.34× | 67% |
| 4  | 166.7 | 1.86× | 47% |
| 6  | 151.4 | 2.05× | 34% |
| 8  | 148.1 | 2.10× | 26% |
| 10 | 140.6 | 2.21× | 22% |
| 12 | 134.9 | 2.30× | 19% |

### `branching_strip` step only — the parallel hot path

| vCPU (workers) | Strip (s) | Speedup | Efficiency/core |
|---:|---:|---:|---:|
| 1  | 242.0 | 1.00× | 100% |
| 2  | 142.7 | 1.70× | 85% |
| 4  | 82.6  | 2.93× | 73% |
| 6  | 69.9  | 3.46× | 58% |
| 8  | 60.7  | 3.99× | 50% |
| 10 | 56.3  | 4.30× | 43% |
| 12 | 54.6  | 4.43× | 37% |

The strip keeps scaling usefully through ~8 workers (≈4× at 50% efficiency), then flattens.

### Full per-step breakdown (seconds)

| vCPU | phrase_sub | boilerplate_sub | temporal | **branching_strip** | quality_report | extract_embed | **total** |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1  | 12.3 | 14.0 | 0.1 | **242.0** | 30.1 | 24.0 | **310.5** |
| 2  | 18.9 | 15.7 | 0.0 | **142.7** | 32.9 | 24.5 | **231.9** |
| 4  | 16.2 | 16.5 | 0.0 | **82.6**  | 32.4 | 22.3 | **166.7** |
| 6  | 14.8 | 15.0 | 0.0 | **69.9**  | 31.8 | 24.2 | **151.4** |
| 8  | 18.4 | 14.3 | 0.1 | **60.7**  | 33.0 | 25.5 | **148.1** |
| 10 | 15.3 | 15.9 | 0.2 | **56.3**  | 30.5 | 24.6 | **140.6** |
| 12 | 15.8 | 15.3 | 0.2 | **54.6**  | 30.5 | 23.4 | **134.9** |

**Which steps scale:**

- **`branching_strip`** — true parallel scaling (chunks CDEs across workers via
  `ProcessPoolExecutor`). The only step where adding cores meaningfully helps.
- **`apply_phrase_substitutions` / `apply_boilerplate_substitutions`** — flat (~15 s).
  Although they accept `--workers`, the work (5 and 231 patterns) is dwarfed by the
  154 MB JSON load+write, so they are effectively I/O-bound and do not scale.
- **`expand_temporal`** — negligible (<0.3 s); pure config expansion.
- **`quality_report`, `extract_embed`** — serial (~31 s, ~24 s); independent of core count.

## Analysis

**Serial floor ≈ 85 s.** Substitutions (~30 s) + `quality_report` (~31 s) +
`extract_embed` (~24 s) are essentially fixed. With `branching_strip` driven toward its
~54 s asymptote, the practical pipeline floor is ~135 s on this hardware regardless of
how many cores are added.

**Amdahl in action.** Parallelizable fraction of the 1-core run is
≈ 242 / 310 ≈ 0.78. The theoretical max total speedup is therefore ≈ 1/(1−0.78) ≈ 4.5×,
but only at infinite cores; the observed 2.30× at 12 cores reflects that the strip itself
plateaus (heterogeneous cores, chunking overhead) before the serial floor would otherwise
allow.

**Variant-count caveat.** This run uses the **2 default variants** (MTSFPT, MTSTPT).
`branching_strip` cost scales roughly linearly with the number of variants, so the full
**7-variant** production run (≈3.5× the strip work) shifts the balance heavily toward the
parallel portion — there, 8–12 vCPU pay off far more than they do here, and the serial
floor becomes a smaller share of total time.

## Proportional use on other hardware

These absolute seconds are specific to the host below. **Use the *ratios*, not the
seconds**, as a portable guide: if 1 core takes time *x* on a different instance, expect
≈ *x*/1.86 at 4 cores and ≈ *x*/2.10 at 8 cores for the full 2-variant pipeline (and
≈ *x*/2.93 / *x*/3.99 for the strip step alone). Per-core wall-clock then scales inversely
with that instance's single-thread performance relative to this host.

### Benchmark host

| | |
|---|---|
| CPU | Intel Core i7-12700K (8 P-cores + 4 E-cores; 20 threads) |
| RAM | 39 GiB |
| OS | WSL2 Ubuntu-22.04 on Windows 11 |
| Python | 3.13 (`py313_base` venv) |

> **Hybrid-core note:** the i7-12700K mixes fast P-cores and slower E-cores. The slight
> 6→8 plateau and run-to-run jitter come from scheduling onto E-cores once the 8 P-core
> threads are saturated. A homogeneous cloud vCPU set should scale more smoothly.

## Reproduce

```bash
# from the cde_analyzer project root, inside the WSL py313 venv
python scripts/benchmark_strip_cores.py \
    --input  /path/to/allcde.json \
    --bench-dir /path/to/scratch/strip_bench \
    --workers 1,2,4,6,8,10,12 \
    --variants MTSFPT,MTSTPT
```

The harness runs `workflows/production_strip.yaml` once per worker count, captures total
wall-clock with `time.perf_counter`, and derives per-step durations from the engine's
`.workflow_state.json` (`started_at` + each step's `completed_at`). Outputs
`results.tsv` and per-run `state_w{N}.json` snapshots in `--bench-dir`.

To benchmark the full production config, add `--variants MTSFPF,MFSTPF,MTSTPF,MFSFPT,MTSFPT,MFSTPT,MTSTPT`.

> **Fix landed with this benchmark:** `extract_embed` (batch and single-file modes) now
> returns `0` explicitly. Previously it fell through to `None`, so the workflow engine
> (`status = success if result == 0`) flagged the final pipeline step as *failed* even
> though all embed files were written — a spurious failure on every `production_strip` run.
