"""PlacementTracker — the single source of truth for logical<->physical state.

Every router mutates the qubit mapping as it inserts SWAPs. Getting this
bookkeeping wrong is the most common way to produce an invalid routed program
(score = inf), so it lives in one small, well-tested place.

Conventions:
  - `pos[logical]  = physical`   (where each logical qubit currently sits)
  - `occ[physical] = logical`    (who currently occupies each physical qubit,
                                  or None if the physical qubit is empty)
Empty physical qubits (the spare hardware qubits) are tracked as None so that a
SWAP with an empty qubit — legal and sometimes useful for routing through spare
space — updates the maps correctly.
"""
from __future__ import annotations


class PlacementTracker:
    def __init__(self, placement: dict[int, int]):
        self.pos: dict[int, int] = dict(placement)
        self.occ: dict[int, int | None] = {p: l for l, p in placement.items()}

    def phys_of(self, logical: int) -> int:
        return self.pos[logical]

    def logical_of(self, physical: int) -> int | None:
        return self.occ.get(physical)

    def is_occupied(self, physical: int) -> bool:
        return self.occ.get(physical) is not None

    def apply_swap(self, a: int, b: int) -> None:
        """Exchange the occupants of physical qubits a and b (either may be empty)."""
        la = self.occ.get(a)
        lb = self.occ.get(b)
        self.occ[a], self.occ[b] = lb, la
        if la is not None:
            self.pos[la] = b
        if lb is not None:
            self.pos[lb] = a

    def snapshot(self) -> dict[int, int]:
        """Current logical->physical mapping (a copy)."""
        return dict(self.pos)

    def clone(self) -> "PlacementTracker":
        new = PlacementTracker.__new__(PlacementTracker)
        new.pos = dict(self.pos)
        new.occ = dict(self.occ)
        return new


def final_layout(placement: dict[int, int], routed: list[tuple]) -> dict[int, int]:
    """Replay a routed program's SWAPs from `placement` to get the final map.

    Returns logical->physical after all SWAPs in `routed` are applied. Used by
    reverse-traversal placement refinement (SABRE): the layout a circuit ends in
    is a good layout to start the reversed circuit from.
    """
    t = PlacementTracker(placement)
    for op in routed:
        if op[0] == "SWAP":
            t.apply_swap(op[1], op[2])
    return t.snapshot()
