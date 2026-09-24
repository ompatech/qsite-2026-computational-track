"""Benchmark harness — run variants over all benchmarks, print a table, log a ledger.

Usage:
    python bench.py                # run the full portfolio + anchors
    python bench.py --anchors      # only the baseline anchors (identity+greedy)

Appends one row per (variant, benchmark) to results/scores.csv so we have an
ablation ledger across the whole project.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys

from starter_kit import BENCHMARKS, benchmark_stats, build_hardware_graph
from solver.pipeline import Candidate, run_candidate

RESULTS = os.path.join(os.path.dirname(__file__), "results", "scores.csv")


def anchor_candidates() -> list[Candidate]:
    from solver.placement.identity import IdentityPlacement
    from solver.routing.greedy import GreedyRouter

    return [Candidate(IdentityPlacement(), GreedyRouter())]


def poc_candidates() -> list[Candidate]:
    """Phase 1+ candidates, added as modules land (import-guarded)."""
    cands: list[Candidate] = []
    try:
        from solver.placement.connectivity import ConnectivityPlacement
        from solver.routing.sabre import SabreRouter

        cands.append(Candidate(ConnectivityPlacement(), SabreRouter()))
    except Exception:
        pass
    try:
        from solver.placement.structure import StructurePlacement
        from solver.routing.sabre import SabreRouter

        cands.append(Candidate(StructurePlacement(), SabreRouter()))
    except Exception:
        pass
    try:
        from solver.placement.annealing import AnnealingPlacement
        from solver.routing.sabre import SabreRouter

        if STRONG:
            cands.append(
                Candidate(
                    AnnealingPlacement(restarts=8, iters=1500, eval_trials=2),
                    SabreRouter(),
                )
            )
        else:
            cands.append(Candidate(AnnealingPlacement(), SabreRouter()))
    except Exception:
        pass
    return cands


STRONG = False


def log_rows(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["timestamp", "variant", "benchmark", "swaps", "depth", "score"]
        )
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchors", action="store_true", help="only baseline anchors")
    ap.add_argument("--strong", action="store_true", help="strong SA config (slow, best scores)")
    args = ap.parse_args()

    global STRONG
    STRONG = args.strong

    hw = build_hardware_graph()
    candidates = anchor_candidates()
    if not args.anchors:
        candidates += poc_candidates()

    ts = dt.datetime.now().isoformat(timespec="seconds")
    rows: list[dict] = []

    header = f"{'benchmark':16} {'Lq':>3} {'2Q':>3} | " + " | ".join(
        f"{c.name:>22}" for c in candidates
    )
    print(header)
    print("-" * len(header))

    totals = {c.name: 0.0 for c in candidates}
    best_total = 0.0
    for name, prog in BENCHMARKS.items():
        st = benchmark_stats(prog)
        cells = []
        best_here = float("inf")
        for c in candidates:
            r = run_candidate(c, prog, hw)
            totals[c.name] += r.score if r.valid else float("inf")
            best_here = min(best_here, r.score if r.valid else float("inf"))
            flag = "" if r.valid else "!"
            cells.append(f"{r.swaps:>3}/{r.depth:>3}/{r.score:>7.1f}{flag:>2}")
            rows.append(
                {
                    "timestamp": ts,
                    "variant": c.name,
                    "benchmark": name,
                    "swaps": r.swaps,
                    "depth": r.depth,
                    "score": r.score,
                }
            )
        best_total += best_here
        print(f"{name:16} {st['logical_qubits']:>3} {st['two_qubit_ops']:>3} | " + " | ".join(cells))

    print("-" * len(header))
    tcells = " | ".join(f"{totals[c.name]:>22.1f}" for c in candidates)
    print(f"{'TOTAL':16} {'':>3} {'':>3} | " + tcells)
    print(f"\nPortfolio best-of total: {best_total:.1f}")
    print("(cells are swaps/depth/score; ! = invalid)")

    log_rows(rows)


if __name__ == "__main__":
    main()
