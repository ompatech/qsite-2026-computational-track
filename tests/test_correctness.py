"""Correctness tests — every candidate must be valid on every benchmark, and the
identity+greedy anchor must reproduce the published baseline total (283.5).

Run: python -m pytest tests/ -q   (or: python tests/test_correctness.py)
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx

from starter_kit import BENCHMARKS, build_hardware_graph
from starter_kit.scorer import validate_routed_program
from solver.pipeline import Candidate, run_candidate
from solver.placement.identity import IdentityPlacement
from solver.routing.greedy import GreedyRouter

BASELINE_TOTAL = 283.5
BASELINE_PER = {
    "ghz_star": 14.0,
    "chain_trotter": 15.0,
    "ladder_trotter": 35.5,
    "qaoa_random": 39.0,
    "dense_random": 122.0,
    "vqe_layers": 58.0,
}


def _all_candidates() -> list[Candidate]:
    from bench import anchor_candidates, poc_candidates

    return anchor_candidates() + poc_candidates()


def test_anchor_reproduces_baseline():
    hw = build_hardware_graph()
    cand = Candidate(IdentityPlacement(), GreedyRouter())
    total = 0.0
    for name, prog in BENCHMARKS.items():
        r = run_candidate(cand, prog, hw)
        assert r.valid, f"{name}: anchor invalid: {r.message}"
        assert abs(r.score - BASELINE_PER[name]) < 1e-9, (
            f"{name}: anchor score {r.score} != baseline {BASELINE_PER[name]}"
        )
        total += r.score
    assert abs(total - BASELINE_TOTAL) < 1e-9, f"anchor total {total} != {BASELINE_TOTAL}"


def test_all_candidates_valid():
    hw = build_hardware_graph()
    for cand in _all_candidates():
        for name, prog in BENCHMARKS.items():
            r = run_candidate(cand, prog, hw)
            assert r.valid, f"{cand.name} invalid on {name}: {r.message}"
            # Double-check with the official validator directly.
            ok, msg = validate_routed_program(prog, hw, r.placement, r.routed)
            assert ok, f"{cand.name} fails official validator on {name}: {msg}"


if __name__ == "__main__":
    test_anchor_reproduces_baseline()
    test_all_candidates_valid()
    print("OK: all correctness tests passed")
