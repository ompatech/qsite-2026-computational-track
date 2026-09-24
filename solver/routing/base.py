"""Routing interface.

A Router takes a program (on logical qubits), an initial placement, and the
hardware graph, and returns a routed program on *physical* qubits with
("SWAP", p, q) operations inserted so that every ("2Q", p, q) lands on a hardware
edge.

Hard invariant enforced by the scorer and therefore by every router here:
stripping the SWAPs from the routed program must reproduce the original program
*in exact order*. So 2Q gates are emitted strictly in input order — routers may
choose which SWAPs to insert and when, but never reorder, drop, or add program
gates.
"""
from __future__ import annotations

from typing import Protocol

import networkx as nx


class Router(Protocol):
    name: str

    def route(
        self,
        program: list[tuple],
        placement: dict[int, int],
        hw: nx.Graph,
    ) -> list[tuple]:
        """Return a routed program on physical qubits (SWAPs inserted)."""
        ...
