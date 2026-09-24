"""Score regression — the portfolio must stay well under the baseline on every
benchmark, and the total must not regress past a safe ceiling.

Uses the *light* portfolio (fast SA) so this runs in seconds for CI-style checks;
the strong config (used by solve.py) only does better. If a change pushes any
number above these ceilings, something regressed.
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starter_kit import BENCHMARKS, build_hardware_graph
from solver.pipeline import run_candidate

BASELINE_PER = {
    "ghz_star": 14.0, "chain_trotter": 15.0, "ladder_trotter": 35.5,
    "qaoa_random": 39.0, "dense_random": 122.0, "vqe_layers": 58.0,
}
# Safe ceilings for the light portfolio (well above observed ~81.5 best-of, far
# below the 283.5 baseline). Deterministic seeds mean observed values are stable.
CEILING_TOTAL = 95.0


def _portfolio_best_per_benchmark():
    from bench import anchor_candidates, poc_candidates

    hw = build_hardware_graph()
    cands = anchor_candidates() + poc_candidates()
    out = {}
    for name, prog in BENCHMARKS.items():
        best = min(
            (run_candidate(c, prog, hw) for c in cands),
            key=lambda r: r.score if r.valid else float("inf"),
        )
        assert best.valid, f"{name}: no valid candidate"
        out[name] = best.score
    return out


def test_beats_baseline_everywhere():
    best = _portfolio_best_per_benchmark()
    for name, score in best.items():
        assert score < BASELINE_PER[name], (
            f"{name}: {score} did not beat baseline {BASELINE_PER[name]}"
        )


def test_total_under_ceiling():
    best = _portfolio_best_per_benchmark()
    total = sum(best.values())
    assert total <= CEILING_TOTAL, f"portfolio total {total} exceeded ceiling {CEILING_TOTAL}"


if __name__ == "__main__":
    best = _portfolio_best_per_benchmark()
    for k, v in best.items():
        print(f"{k:16} {v:6.1f}   (baseline {BASELINE_PER[k]})")
    print("TOTAL", sum(best.values()))
    test_beats_baseline_everywhere()
    test_total_under_ceiling()
    print("OK: score regression passed")
