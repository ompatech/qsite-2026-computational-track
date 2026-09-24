"""Build a weighted logical-qubit interaction graph from a program.

The interaction graph has one node per logical qubit used in the program and an
edge between two logical qubits for every two-qubit gate acting on them. Edge
weights encode how strongly (and how *early*) two qubits interact, so that
placement can put strongly/early-interacting qubits on nearby physical qubits.

Two weighting schemes:
  - "count": weight = number of 2Q gates on the pair (simple, order-agnostic).
  - "decay": weight = sum over gates on the pair of gamma**layer, where `layer`
    is the gate's index in a dependency-respecting layering of the program.
    Early gates (small layer) get more weight, matching TANGO's layer-decay
    idea (W_g(g_i) = gamma**layer_i). Front-loaded interactions dominate
    placement because they are the ones that must be satisfied first.

Both return an undirected ``networkx.Graph`` with a ``weight`` attribute on
every edge (accumulated across parallel/repeated gates).
"""
from __future__ import annotations

from collections.abc import Iterable

import networkx as nx


def used_logical_qubits(program: Iterable[tuple]) -> list[int]:
    """Sorted list of logical qubit indices that appear anywhere in `program`."""
    return sorted({q for op in program for q in op[1:]})


def program_layers(program: list[tuple]) -> list[int]:
    """Return, for each op in `program`, the dependency layer it lands in.

    Uses the same as-early-as-possible packing the scorer uses for depth: an op
    is placed one layer after the latest layer of any qubit it touches. 1Q gates
    are treated as occupying their single qubit. The returned list is parallel to
    `program` (same length, same order); the value at index k is the 1-based
    layer of program[k].
    """
    layer_of: list[int] = []
    qubit_last_layer: dict[int, int] = {}
    for op in program:
        wires = op[1:]
        layer = 1 + max((qubit_last_layer.get(q, 0) for q in wires), default=0)
        layer_of.append(layer)
        for q in wires:
            qubit_last_layer[q] = layer
    return layer_of


def build_interaction_graph(
    program: list[tuple],
    scheme: str = "decay",
    gamma: float = 0.9,
) -> nx.Graph:
    """Build the weighted logical interaction graph.

    Args:
        program: list of ("2Q", i, j) / ("1Q", i) tuples on logical qubits.
        scheme: "count" or "decay".
        gamma: decay base in (0, 1] for the "decay" scheme.

    Returns:
        networkx.Graph with all used logical qubits as nodes and weighted edges.
    """
    if scheme not in ("count", "decay"):
        raise ValueError(f"unknown scheme {scheme!r}")

    graph = nx.Graph()
    graph.add_nodes_from(used_logical_qubits(program))

    layers = program_layers(program) if scheme == "decay" else None

    for k, op in enumerate(program):
        if op[0] != "2Q":
            continue
        _, i, j = op
        w = 1.0 if scheme == "count" else gamma ** (layers[k] - 1)
        if graph.has_edge(i, j):
            graph[i][j]["weight"] += w
        else:
            graph.add_edge(i, j, weight=w)
    return graph


def qubit_weights(interaction: nx.Graph) -> dict[int, float]:
    """Total incident edge weight per logical qubit (placement priority)."""
    return {
        q: sum(interaction[q][nb]["weight"] for nb in interaction[q])
        for q in interaction.nodes
    }
