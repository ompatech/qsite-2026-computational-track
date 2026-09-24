"""Reverse-traversal placement refinement (SABRE, §III).

Wraps any base placement. It routes the program forward, takes the layout the
circuit *ends* in, routes the reversed program from there, and uses that ending
layout as the new initial map — iterating a few times. The intuition: a layout
that a circuit naturally settles into is a cheaper place to start it from, so this
reduces total SWAPs without any change to the router.

RefinedPlacement is a decorator: `RefinedPlacement(ConnectivityPlacement())` is a
Placement whose `.place()` returns the refined initial map.
"""
from __future__ import annotations

import networkx as nx

from solver.routing.sabre import SabreRouter
from solver.routing.tracker import final_layout


class RefinedPlacement:
    def __init__(self, base, iters: int = 3, eval_trials: int = 1):
        self.base = base
        self.iters = iters
        self._router = SabreRouter(trials=eval_trials)
        self.name = f"rev({base.name})"

    def place(self, program, hw, interaction) -> dict[int, int]:
        placement = self.base.place(program, hw, interaction)
        reversed_program = list(reversed(program))
        for _ in range(self.iters):
            fwd = self._router.route(program, placement, hw)
            mid = final_layout(placement, fwd)
            bwd = self._router.route(reversed_program, mid, hw)
            placement = final_layout(mid, bwd)
        return placement
