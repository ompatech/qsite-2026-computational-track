"""Greedy shortest-path router — the baseline anchor.

For each 2Q gate whose qubits are not adjacent, walk one qubit toward the other
along a shortest path in the hardware graph, inserting a SWAP per hop until the
two are neighbors, then emit the gate. No look-ahead: a SWAP that helps this gate
may hurt the next. With IdentityPlacement this reproduces the published baseline.

Generalized over the baseline in one way only: it accepts an arbitrary initial
placement (the baseline hard-codes identity), so it can serve as a fast inner
router and as an honest regression anchor.
"""
from __future__ import annotations

import networkx as nx

from solver.routing.tracker import PlacementTracker


class GreedyRouter:
    name = "greedy"

    def route(
        self,
        program: list[tuple],
        placement: dict[int, int],
        hw: nx.Graph,
    ) -> list[tuple]:
        t = PlacementTracker(placement)
        routed: list[tuple] = []

        for op in program:
            if op[0] == "1Q":
                routed.append(("1Q", t.phys_of(op[1])))
                continue

            _, l_left, l_right = op
            p_left, p_right = t.phys_of(l_left), t.phys_of(l_right)

            if not hw.has_edge(p_left, p_right):
                path = nx.shortest_path(hw, p_left, p_right)
                # SWAP l_left one hop at a time toward l_right along the path,
                # stopping when it is adjacent to l_right (path[:-2]).
                for a, b in zip(path[:-2], path[1:-1]):
                    routed.append(("SWAP", a, b))
                    t.apply_swap(a, b)

            routed.append(("2Q", t.phys_of(l_left), t.phys_of(l_right)))

        return routed
