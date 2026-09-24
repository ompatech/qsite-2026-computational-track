"""Placement search — simulated annealing scored by the *real* route metric.

Where structure/connectivity give a good starting map, SA squeezes the rest by
directly minimizing swaps + 0.5*depth: each candidate placement is evaluated by
actually routing it (a fast single-trial SABRE) and scoring it. Moves either swap
two logical qubits' physical slots or relocate a logical qubit onto a currently
*empty* physical qubit — exploiting the spare hardware qubits (only 8-16 of 20 are
occupied). Seeded from StructurePlacement, so SA can only improve on it; the outer
portfolio keeps the overall best regardless.

No grader time limit is assumed, but the search is bounded (restarts x iters) for
predictable runtime; raise `restarts`/`iters` for a stronger final pass.
"""
from __future__ import annotations

import math
import random

import networkx as nx

from solver.hardware_analysis import hardware_info
from solver.interaction import used_logical_qubits
from solver.metrics import objective
from solver.placement.structure import StructurePlacement
from solver.routing.sabre import SabreRouter


class AnnealingPlacement:
    name = "annealing"

    def __init__(
        self,
        restarts: int = 4,
        iters: int = 500,
        t0: float = 2.0,
        cooling: float = 0.995,
        seed: int = 0,
        eval_trials: int = 1,
    ):
        self.restarts = restarts
        self.iters = iters
        self.t0 = t0
        self.cooling = cooling
        self.seed = seed
        # Cheap inner router for the search loop; the portfolio re-routes the
        # winner at full quality afterwards.
        self._router = SabreRouter(trials=eval_trials)
        self._seeder = StructurePlacement()

    def place(self, program, hw, interaction) -> dict[int, int]:
        logical = used_logical_qubits(program)
        if len(logical) <= 1:
            return self._seeder.place(program, hw, interaction)

        all_phys = list(hw.nodes)
        rng = random.Random(self.seed)

        def score(placement: dict[int, int]) -> float:
            routed = self._router.route(program, placement, hw)
            return objective(routed)

        seed_placement = self._seeder.place(program, hw, interaction)
        best = dict(seed_placement)
        best_score = score(best)

        for r in range(self.restarts):
            state = dict(seed_placement if r == 0 else best)
            cur_score = score(state)
            T = self.t0
            for _ in range(self.iters):
                cand = self._neighbor(state, logical, all_phys, rng)
                cand_score = score(cand)
                delta = cand_score - cur_score
                if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-9)):
                    state, cur_score = cand, cand_score
                    if cur_score < best_score:
                        best, best_score = dict(state), cur_score
                T *= self.cooling
        return best

    def _neighbor(self, placement, logical, all_phys, rng) -> dict[int, int]:
        """One random move: swap two logical slots, or relocate onto an empty qubit."""
        new = dict(placement)
        occupied = set(new.values())
        empties = [p for p in all_phys if p not in occupied]

        if empties and rng.random() < 0.5:
            # Relocate a random logical qubit onto a random empty physical qubit.
            q = rng.choice(logical)
            new[q] = rng.choice(empties)
        else:
            # Swap the physical slots of two logical qubits.
            a, b = rng.sample(logical, 2)
            new[a], new[b] = new[b], new[a]
        return new
