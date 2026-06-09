#!/usr/bin/env python3
"""Benchmark the production_strip pipeline across worker (core) counts.

Runs ``workflow run production_strip.yaml`` once per worker count, capturing
total wall-clock time and per-step durations (parsed from the engine's
``.workflow_state.json``).  The dominant parallel step is ``branching_strip``;
the substitution passes also parallelize, while temporal expansion, the
quality report, and embed extraction are effectively serial.

Results feed ``docs/benchmarks/strip-core-scaling.md`` as an approximate,
hardware-proportional sizing guide for cloud instances.

Usage (from the cde_analyzer project root, inside the WSL venv):

    python scripts/benchmark_strip_cores.py \
        --input /path/to/allcde.json \
        --bench-dir /path/to/scratch/strip_bench \
        --workers 1,2,4,6,8,10,12 \
        --variants MTSFPT,MTSTPT

Paths are parameters; nothing machine-specific is hardcoded.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Project root = parent of this scripts/ directory.
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "workflows" / "production_strip.yaml"
DEFAULT_PATTERNS = ROOT / "data" / "reference_ledger" / "production_patterns"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True,
                   help="CDE JSON to strip (e.g. allcde.json / cde_all_*.json).")
    p.add_argument("--bench-dir", required=True,
                   help="Scratch directory for per-run outputs and results.")
    p.add_argument("--workers", default="1,2,4,6,8,10,12",
                   help="Comma-separated worker counts to benchmark.")
    p.add_argument("--variants", default="MTSFPT,MTSTPT",
                   help="Branching-strip variant codes (default: production default).")
    p.add_argument("--patterns-dir", default=str(DEFAULT_PATTERNS),
                   help="Production pattern directory (default: reference ledger).")
    p.add_argument("--keep-outputs", action="store_true",
                   help="Keep each run's output dir (default: delete to save disk).")
    return p.parse_args()


def step_durations(state: dict) -> list[tuple[str, float]]:
    """Per-step seconds from started_at + each step's completed_at."""
    fmt = datetime.fromisoformat
    prev = fmt(state["started_at"])
    out = []
    for step in state.get("completed_steps", []):
        done = fmt(step["completed_at"])
        out.append((step["name"], (done - prev).total_seconds()))
        prev = done
    return out


def run_once(input_json: str, out_dir: Path, workers: int, variants: str,
             patterns_dir: str) -> dict:
    """Run the pipeline once; return {total, steps:[(name,sec)], rc}."""
    shutil.rmtree(out_dir, ignore_errors=True)  # fresh run, never a resume
    out_dir.mkdir(parents=True, exist_ok=True)
    # The engine writes state to <state-dir>/.workflow_state.json; pin it here.
    state_path = out_dir / ".workflow_state.json"

    cmd = [
        sys.executable, str(ROOT / "cde_analyzer.py"), "workflow", "run",
        str(WORKFLOW),
        "--set", f"input_json={input_json}",
        "--set", f"output_dir={out_dir}",
        "--set", f"workers={workers}",
        "--set", f"variants={variants}",
        "--set", f"patterns_dir={patterns_dir}",
        "--state-dir", str(out_dir),
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    total = time.perf_counter() - t0

    steps: list[tuple[str, float]] = []
    if state_path.exists():
        steps = step_durations(json.loads(state_path.read_text(encoding="utf-8")))
        shutil.copy(state_path, out_dir.parent / f"state_w{workers}.json")

    if proc.returncode != 0:
        sys.stderr.write(f"[w={workers}] non-zero rc={proc.returncode}\n")
        sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-2000:] + "\n")

    return {"total": total, "steps": steps, "rc": proc.returncode}


def main() -> int:
    args = parse_args()
    bench = Path(args.bench_dir)
    bench.mkdir(parents=True, exist_ok=True)
    worker_counts = [int(x) for x in args.workers.split(",") if x.strip()]

    results = []
    all_step_names: list[str] = []
    for w in worker_counts:
        out_dir = bench / f"out_w{w}"
        print(f"\n=== workers={w} ===", flush=True)
        r = run_once(args.input, out_dir, w, args.variants, args.patterns_dir)
        print(f"  total={r['total']:.1f}s  rc={r['rc']}", flush=True)
        for name, sec in r["steps"]:
            print(f"    {name:32s} {sec:8.1f}s", flush=True)
            if name not in all_step_names:
                all_step_names.append(name)
        results.append((w, r))
        # state_wN.json is already snapshotted in run_once; reclaim run output
        if not args.keep_outputs:
            shutil.rmtree(out_dir, ignore_errors=True)

    # ── Write results TSV ────────────────────────────────────────────
    res_tsv = bench / "results.tsv"
    with res_tsv.open("w", encoding="utf-8") as f:
        header = ["workers", "total_s"] + all_step_names
        f.write("\t".join(header) + "\n")
        for w, r in results:
            stepmap = dict(r["steps"])
            row = [str(w), f"{r['total']:.2f}"] + \
                  [f"{stepmap.get(n, ''):.2f}" if n in stepmap else ""
                   for n in all_step_names]
            f.write("\t".join(row) + "\n")

    # ── Console summary with speedup vs single worker ────────────────
    base = next((r["total"] for w, r in results if w == worker_counts[0]), None)
    print("\n=== SUMMARY ===")
    print(f"{'workers':>7}  {'total_s':>9}  {'speedup':>7}  {'eff/core':>8}")
    for w, r in results:
        sp = base / r["total"] if base else 0.0
        eff = sp / w if w else 0.0
        print(f"{w:>7}  {r['total']:>9.1f}  {sp:>6.2f}x  {eff:>7.0%}")
    print(f"\nresults: {res_tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
