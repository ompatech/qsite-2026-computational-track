"""Connectivity-aware placement — center-seeded greedy weighted embedding.

Idea (a simplified TANGO dual-factor placement):
  1. Weight logical qubits by total incident interaction weight.
  2. Seed the heaviest logical qubit on a central, high-degree physical qubit
     (the hardware center {8,9,10,11}) so its many/early interactions start cheap.
  3. Grow the placement greedily: repeatedly take the unplaced logical qubit most
     strongly tied to the already-placed set, and drop it on the free physical
     qubit that minimizes the weighted sum of hardware distances to its already-
     placed logical neighbours.

Connectivity-blind ties fall back to "closest free qubit to the centroid of what's
already placed", which keeps everything compact on the sparse heavy-hex graph.
"""
from __future__ import annotations

import networkx as nx

from solver.interaction import qubit_weights, used_logical_qubits


class ConnectivityPlacement:
    name = "connectivity"

    def __init__(self, center_pool: tuple[int, ...] = (9, 10, 8, 11)):
        # Preference order for the seed's physical qubit (hardware center,
        # highest-degree first). Node 9/10 are degree-3 centers.
        self.center_pool = center_pool

    def place(
        self,
        program: list[tuple],
        hw: nx.Graph,
        interaction: nx.Graph,
    ) -> dict[int, int]:
        logical = used_logical_qubits(program)
        if not logical:
            return {}

        dist = dict(nx.all_pairs_shortest_path_length(hw))
        wq = qubit_weights(interaction)

        # Seed: heaviest logical qubit -> best central physical qubit.
        seed = max(logical, key=lambda q: (wq.get(q, 0.0), interaction.degree(q)))
        seed_phys = self._pick_center(hw)
        placement: dict[int, int] = {seed: seed_phys}
        occupied: set[int] = {seed_phys}

        unplaced = set(logical) - {seed}
        while unplaced:
            # Pick the unplaced qubit most tied to the placed set (tie-break by
            # its global weight so heavy hubs go down early).
            def tie_strength(q: int) -> float:
                return sum(
                    interaction[q][nb]["weight"]
                    for nb in interaction[q]
                    if nb in placement
                )

            q = max(unplaced, key=lambda q: (tie_strength(q), wq.get(q, 0.0)))
            placed_neighbors = [nb for nb in interaction[q] if nb in placement]

            free = [p for p in hw.nodes if p not in occupied]
            if placed_neighbors:
                def cost(p: int) -> float:
                    return sum(
                        interaction[q][nb]["weight"] * dist[p][placement[nb]]
                        for nb in placed_neighbors
                    )
                best_phys = min(free, key=cost)
            else:
                # No placed neighbour yet: sit near the centroid of placed qubits.
                def compactness(p: int) -> int:
                    return sum(dist[p][op] for op in occupied)
                best_phys = min(free, key=compactness)

            placement[q] = best_phys
            occupied.add(best_phys)
            unplaced.discard(q)

        return placement

    def _pick_center(self, hw: nx.Graph) -> int:
        for p in self.center_pool:
            if p in hw.nodes:
                return p
        # Fallback: true graph center, highest degree first.
        center = nx.center(hw)
        return max(center, key=lambda p: hw.degree(p))
