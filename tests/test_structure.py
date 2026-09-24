"""Structure detector tests: correct family on canonical shapes, and graceful
fallback (never crash, always a valid placement) on an unrecognised random graph.
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx

from starter_kit import build_hardware_graph
from starter_kit.scorer import validate_initial_placement
from solver.interaction import build_interaction_graph
from solver.placement.structure import StructurePlacement, detect_family


def _star(n):  # center 0 -> leaves 1..n-1, sequential
    return [("2Q", 0, i) for i in range(1, n)]


def _chain(n):
    return [("2Q", i, i + 1) for i in range(n - 1)]


def test_families_detected():
    assert detect_family(build_interaction_graph(_star(6))) == "star"
    assert detect_family(build_interaction_graph(_chain(8))) == "path"
    # A triangle-with-tail has a degree-3 node -> not star/path/grid -> generic.
    prog = [("2Q", 0, 1), ("2Q", 1, 2), ("2Q", 2, 0), ("2Q", 0, 3), ("2Q", 3, 4)]
    assert detect_family(build_interaction_graph(prog)) == "generic"


def test_fallback_valid_on_generic():
    hw = build_hardware_graph()
    place = StructurePlacement()
    prog = [("2Q", 0, 1), ("2Q", 1, 2), ("2Q", 2, 0), ("2Q", 0, 3), ("2Q", 3, 4)]
    ig = build_interaction_graph(prog)
    placement = place.place(prog, hw, ig)
    ok, msg = validate_initial_placement(prog, hw, placement)
    assert ok, f"structure fallback produced invalid placement: {msg}"


if __name__ == "__main__":
    test_families_detected()
    test_fallback_valid_on_generic()
    print("OK: structure tests passed")
