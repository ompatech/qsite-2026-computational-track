"""Identity placement — the baseline anchor.

Maps the sorted logical qubits onto the sorted physical qubits (L0->P0, L1->P1,
...). Intentionally connectivity-blind. Kept forever as a regression anchor: with
the greedy router it must reproduce the published baseline total (283.5).
"""
from __future__ import annotations

import networkx as nx

from solver.interaction import used_logical_qubits


class IdentityPlacement:
    name = "identity"

    def place(
        self,
        program: list[tuple],
        hw: nx.Graph,
        interaction: nx.Graph,
    ) -> dict[int, int]:
        logical = used_logical_qubits(program)
        physical = sorted(hw.nodes)
        return {lq: physical[i] for i, lq in enumerate(logical)}
