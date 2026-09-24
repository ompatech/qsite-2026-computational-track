"""Reusable, graph-agnostic analysis of a hardware graph.

Everything here is computed from the graph itself (no hard-coded node numbers), so
it generalises to any coupling map, not just the QSITE teaching graph. Results are
cached per graph object.
"""
from __future__ import annotations

import networkx as nx

_CACHE: dict[int, "HardwareInfo"] = {}


class HardwareInfo:
    def __init__(self, hw: nx.Graph):
        self.hw = hw
        self.dist = dict(nx.all_pairs_shortest_path_length(hw))
        self.degree = dict(hw.degree())
        self.center = list(nx.center(hw))
        # Hubs: highest-degree nodes (for star centers etc.), high degree first.
        self.hubs = sorted(hw.nodes, key=lambda n: self.degree[n], reverse=True)
        self.longest_path = _longest_simple_path(hw)

    def central_hub(self) -> int:
        """A central, high-degree physical qubit (good default seed)."""
        return max(self.center, key=lambda n: self.degree[n])


def hardware_info(hw: nx.Graph) -> HardwareInfo:
    key = id(hw)
    info = _CACHE.get(key)
    if info is None:
        info = HardwareInfo(hw)
        _CACHE[key] = info
    return info


def _longest_simple_path(hw: nx.Graph, expansion_cap: int = 300_000) -> list[int]:
    """Heuristic longest simple path via DFS from peripheral nodes.

    Returns the longest simple path found (a Hamiltonian path when one exists and
    the search reaches it within the expansion cap). For the sparse teaching graph
    this finds a full 20-node path immediately. Deterministic: nodes are explored
    in a fixed order.
    """
    best: list[int] = []
    expansions = 0

    # Start from low-degree nodes first (dead-ends / periphery make good endpoints).
    starts = sorted(hw.nodes, key=lambda n: hw.degree(n))
    n = hw.number_of_nodes()

    for s in starts:
        stack = [(s, [s], {s})]
        while stack:
            node, path, visited = stack.pop()
            if len(path) > len(best):
                best = path
                if len(best) == n:
                    return best  # Hamiltonian path found
            expansions += 1
            if expansions > expansion_cap:
                return best
            # Explore neighbours in a fixed order for determinism.
            for nb in sorted(hw[node]):
                if nb not in visited:
                    stack.append((nb, path + [nb], visited | {nb}))
        if len(best) == n:
            break
    return best
