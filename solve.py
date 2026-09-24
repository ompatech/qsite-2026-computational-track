"""Submission entrypoint: solve(program, hardware_graph).

This is the single stable interface the grader calls. Internally it runs the
Layered Portfolio Compiler: several placement x router candidates are executed,
each scored with the real competition metric (swaps + 0.5*depth), and the best
valid result is returned. Improving the compiler only changes the candidate list
below — never this signature.
"""
from __future__ import annotations

import networkx as nx

from solver.pipeline import Candidate, portfolio_solve


def _candidates() -> list[Candidate]:
    from solver.routing.sabre import SabreRouter
    from solver.placement.connectivity import ConnectivityPlacement

    router = SabreRouter()
    cands: list[Candidate] = [Candidate(ConnectivityPlacement(), router)]

    # Structure-aware placement (Phase 2) — added when available.
    try:
        from solver.placement.structure import StructurePlacement

        cands.append(Candidate(StructurePlacement(), router))
    except Exception:
        pass

    # Placement search (Phase 3) — added when available. A strong config: with no
    # known grader time limit we spend ~20-35s/benchmark to minimize the real score.
    try:
        from solver.placement.annealing import AnnealingPlacement

        cands.append(
            Candidate(
                AnnealingPlacement(restarts=8, iters=1500, eval_trials=2), router
            )
        )
    except Exception:
        pass

    return cands


def solve(program: list[tuple], hardware_graph: nx.Graph) -> tuple[dict, list[tuple]]:
    """Return (initial_placement, routed_program) for the given program.

    Args:
        program: list of ("2Q", i, j) / ("1Q", i) tuples on logical qubits.
        hardware_graph: networkx.Graph of physical-qubit connectivity.

    Returns:
        (initial_placement: dict[int,int], routed_program: list[tuple])
    """
    return portfolio_solve(program, hardware_graph, _candidates())
