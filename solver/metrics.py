"""Scoring/validation helpers — a thin, honest wrapper over the starter scorer.

Everything terminates here. The competition objective is::

    score = swap_count + 0.5 * depth

which is exactly ``starter_kit.scorer.core_score`` on a valid routed program, and
``inf`` on an invalid one. We never invent our own proxy; candidate selection and
search both call these functions so we optimize precisely what is graded.
"""
from __future__ import annotations

import networkx as nx

from starter_kit.scorer import (
    core_score,
    schedule_layers_ordered,
    validate_routed_program,
)

OBJECTIVE_DEPTH_WEIGHT = 0.5


def evaluate(
    program: list[tuple],
    hw: nx.Graph,
    placement: dict[int, int],
    routed: list[tuple],
) -> dict:
    """Validate and score one (placement, routed_program) result.

    Returns a dict with keys: valid, message, swaps, depth, score.
    `score` is inf when invalid, so an invalid result always loses a min().
    """
    valid, message = validate_routed_program(program, hw, placement, routed)
    swaps = sum(1 for op in routed if op[0] == "SWAP")
    depth = len(schedule_layers_ordered(routed))
    return {
        "valid": valid,
        "message": message,
        "swaps": swaps,
        "depth": depth,
        "score": core_score(routed) if valid else float("inf"),
    }


def objective(routed: list[tuple]) -> float:
    """The raw competition score of an *assumed-valid* routed program.

    Cheap (no validation) — use inside inner search loops where validity is
    guaranteed by construction; use `evaluate` at boundaries where it is not.
    """
    return core_score(routed)
