"""Structure-aware placement — detect the interaction graph's family, embed exactly.

The detector keys off graph *properties* (degree sequence, isomorphism to a grid),
never the benchmark names, so it generalises: any path-like program embeds along
the hardware's longest path (0 SWAPs when the program is a pure chain), any star
embeds around a high-degree hub, any 2xk ladder embeds onto a 2xk grid subgraph
when one exists. Anything unrecognised falls back to ConnectivityPlacement, so this
candidate is never worse than connectivity and often much better.
"""
from __future__ import annotations

import networkx as nx
from networkx.algorithms.isomorphism import GraphMatcher

from solver.hardware_analysis import hardware_info
from solver.interaction import used_logical_qubits
from solver.placement.connectivity import ConnectivityPlacement


def detect_family(interaction: nx.Graph) -> str:
    """Classify the interaction graph: 'path', 'star', 'grid', or 'generic'."""
    n = interaction.number_of_nodes()
    if n <= 1 or not nx.is_connected(interaction):
        return "generic"
    degs = sorted(dict(interaction.degree()).values())
    max_deg = degs[-1]

    # Star: one center connected to all others, everyone else a leaf.
    if max_deg == n - 1 and degs[:-1] == [1] * (n - 1):
        return "star"

    # Path: every node degree <= 2, exactly two endpoints of degree 1 (a simple
    # path, not a cycle).
    if max_deg <= 2 and degs.count(1) == 2 and interaction.number_of_edges() == n - 1:
        return "path"

    # Grid/ladder: isomorphic to a 2xk grid (k = n/2).
    if n % 2 == 0:
        k = n // 2
        if k >= 2 and nx.is_isomorphic(interaction, nx.grid_2d_graph(2, k)):
            return "grid"

    return "generic"


class StructurePlacement:
    name = "structure"

    def __init__(self):
        self._fallback = ConnectivityPlacement()

    def place(self, program, hw, interaction) -> dict[int, int]:
        family = detect_family(interaction)
        placement = None
        if family == "path":
            placement = self._embed_path(interaction, hw)
        elif family == "star":
            placement = self._embed_star(interaction, hw)
        elif family == "grid":
            placement = self._embed_grid(interaction, hw)

        if placement is None:
            placement = self._fallback.place(program, hw, interaction)
        return placement

    # ---- family embeddings -------------------------------------------------

    def _embed_path(self, interaction, hw) -> dict[int, int] | None:
        """Order logical qubits along the interaction path, map onto the hardware
        longest path so consecutive interacting qubits are hardware-adjacent."""
        order = _path_node_order(interaction)
        if order is None:
            return None
        info = hardware_info(hw)
        hw_path = info.longest_path
        if len(hw_path) < len(order):
            return None
        return {log: hw_path[i] for i, log in enumerate(order)}

    def _embed_star(self, interaction, hw) -> dict[int, int] | None:
        """Center on a central high-degree hub; leaves on nearest nodes by BFS."""
        n = interaction.number_of_nodes()
        center = max(interaction.nodes, key=lambda q: interaction.degree(q))
        leaves = [q for q in interaction.nodes if q != center]

        info = hardware_info(hw)
        hub = info.central_hub()
        # Physical qubits ordered by distance from the hub (closest first).
        ranked = sorted(hw.nodes, key=lambda p: (info.dist[hub][p], -info.degree[p]))
        placement = {center: hub}
        used = {hub}
        idx = 0
        for leaf in leaves:
            while ranked[idx] in used:
                idx += 1
            placement[leaf] = ranked[idx]
            used.add(ranked[idx])
        return placement

    def _embed_grid(self, interaction, hw) -> dict[int, int] | None:
        """Find a 2xk grid subgraph in hardware (VF2) and map the ladder onto it."""
        k = interaction.number_of_nodes() // 2
        grid = nx.grid_2d_graph(2, k)
        gm = GraphMatcher(hw, grid)
        if not gm.subgraph_is_isomorphic():
            return None  # heavy-hex may not contain an exact 2xk grid -> fallback
        # gm.mapping: hw_node -> grid_node ; invert to grid_node -> hw_node.
        grid_to_hw = {gnode: hwnode for hwnode, gnode in gm.mapping.items()}
        # Map interaction (isomorphic to grid) onto grid coordinates, then to hw.
        iso = GraphMatcher(interaction, grid)
        assert iso.is_isomorphic()
        # iso.mapping: interaction_node -> grid_node
        return {inode: grid_to_hw[gnode] for inode, gnode in iso.mapping.items()}


def _path_node_order(interaction: nx.Graph) -> list[int] | None:
    """Return the logical qubits in path order (endpoint to endpoint)."""
    endpoints = [q for q in interaction.nodes if interaction.degree(q) == 1]
    if len(endpoints) != 2:
        return None
    start = min(endpoints)
    order = [start]
    prev, cur = None, start
    while len(order) < interaction.number_of_nodes():
        nxts = [nb for nb in interaction[cur] if nb != prev]
        if not nxts:
            break
        prev, cur = cur, nxts[0]
        order.append(cur)
    return order if len(order) == interaction.number_of_nodes() else None
