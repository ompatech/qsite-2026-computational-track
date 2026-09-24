"""Placement interface.

A Placement maps every logical qubit used in the program to a distinct physical
qubit of the hardware graph. It must be *injective* and cover exactly the logical
qubits that appear in the program (the scorer enforces both).
"""
from __future__ import annotations

from typing import Protocol

import networkx as nx


class Placement(Protocol):
    """Anything that can produce an initial logical->physical mapping."""

    name: str

    def place(
        self,
        program: list[tuple],
        hw: nx.Graph,
        interaction: nx.Graph,
    ) -> dict[int, int]:
        """Return an injective dict logical_qubit -> physical_qubit."""
        ...


def validate_placement(
    placement: dict[int, int],
    program: list[tuple],
    hw: nx.Graph,
) -> None:
    """Raise AssertionError if the placement is structurally invalid.

    A cheap internal guard so bugs surface at the source rather than as an
    opaque ``inf`` from the scorer later.
    """
    from solver.interaction import used_logical_qubits

    logical = set(used_logical_qubits(program))
    assert set(placement) == logical, "placement must cover exactly the used logical qubits"
    phys = list(placement.values())
    assert len(phys) == len(set(phys)), "placement must be injective"
    assert set(phys).issubset(set(hw.nodes)), "placement uses physical qubits outside the graph"
