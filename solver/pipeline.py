"""Portfolio pipeline — compose placement x router, score the real metric, win.

`portfolio_solve` runs every (Placement, Router) candidate, validates each
result, scores it with the true competition metric, and returns the best valid
(placement, routed_program). Invalid candidates are dropped, never returned.
Because the challenge has no known grader time limit, running a handful of cheap
candidates and keeping the winner is both safe (no single strategy can misfire on
a shape) and near-optimal.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from solver.interaction import build_interaction_graph
from solver.metrics import evaluate


@dataclass
class Candidate:
    placement: object  # Placement
    router: object     # Router
    interaction_scheme: str = "decay"
    gamma: float = 0.9

    @property
    def name(self) -> str:
        return f"{self.placement.name}+{self.router.name}"


@dataclass
class Result:
    name: str
    placement: dict
    routed: list
    swaps: int
    depth: int
    score: float
    valid: bool
    message: str


def run_candidate(candidate: Candidate, program: list[tuple], hw: nx.Graph) -> Result:
    interaction = build_interaction_graph(
        program, scheme=candidate.interaction_scheme, gamma=candidate.gamma
    )
    placement = candidate.placement.place(program, hw, interaction)
    routed = candidate.router.route(program, placement, hw)
    ev = evaluate(program, hw, placement, routed)
    return Result(
        name=candidate.name,
        placement=placement,
        routed=routed,
        swaps=ev["swaps"],
        depth=ev["depth"],
        score=ev["score"],
        valid=ev["valid"],
        message=ev["message"],
    )


def portfolio_solve(
    program: list[tuple],
    hw: nx.Graph,
    candidates: list[Candidate],
    return_details: bool = False,
):
    """Return (placement, routed) of the best valid candidate.

    If return_details=True, also return the list of all per-candidate Results
    (for benchmarking/ablation).
    """
    results = [run_candidate(c, program, hw) for c in candidates]
    valid = [r for r in results if r.valid]
    if not valid:
        # Should never happen — greedy anchors always produce valid output — but
        # fail loudly rather than returning garbage.
        raise RuntimeError(
            "no valid candidate produced; messages: "
            + "; ".join(f"{r.name}: {r.message}" for r in results)
        )
    best = min(valid, key=lambda r: r.score)
    if return_details:
        return best.placement, best.routed, results
    return best.placement, best.routed
