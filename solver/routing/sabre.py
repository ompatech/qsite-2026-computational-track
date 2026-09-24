"""SABRE-style router (decay heuristic), adapted to our ordered-emission constraint.

Because the scorer requires that stripping SWAPs reproduces the program in exact
order, we emit 2Q gates strictly in input order. The front layer is therefore the
single next 2Q gate; SABRE's power is retained through the *extended set* (the next
few gates) which biases SWAP choice toward the future, and through the *decay* term
which spreads SWAPs across qubits to hold depth down (our 0.5*depth term).

Per gate g=(l,r) not yet adjacent, repeatedly:
  - candidate SWAPs = hardware edges incident to phys(l) or phys(r);
  - score each with
        H = max(decay[a], decay[b]) * ( D[phys(l)][phys(r)]
                                        + W * (1/|E|) * sum_{g' in E} D[.][.] );
  - apply the min-H SWAP, bump decay[a],decay[b] by delta;
  - stop when phys(l),phys(r) are adjacent, then emit g and reset decay.

Multiple random seeds break ties differently; the caller keeps the best real
score. A shortest-path fallback guarantees termination if the heuristic stalls.
"""
from __future__ import annotations

import random

import networkx as nx

from solver.metrics import objective
from solver.routing.tracker import PlacementTracker


class SabreRouter:
    name = "sabre"

    def __init__(
        self,
        extended_size: int = 20,
        w_extended: float = 0.5,
        decay_delta: float = 0.001,
        trials: int = 8,
        max_swaps_per_gate: int = 200,
        seed: int = 0,
    ):
        self.extended_size = extended_size
        self.w_extended = w_extended
        self.decay_delta = decay_delta
        self.trials = trials
        self.max_swaps_per_gate = max_swaps_per_gate
        self.seed = seed

    def route(
        self,
        program: list[tuple],
        placement: dict[int, int],
        hw: nx.Graph,
    ) -> list[tuple]:
        dist = dict(nx.all_pairs_shortest_path_length(hw))
        # Index the 2Q gates so we can build the extended set cheaply.
        two_q_positions = [k for k, op in enumerate(program) if op[0] == "2Q"]

        best_routed: list[tuple] | None = None
        best_score = float("inf")
        for t in range(self.trials):
            rng = random.Random(self.seed + t)
            routed = self._route_once(program, placement, hw, dist, two_q_positions, rng)
            s = objective(routed)
            if s < best_score:
                best_score, best_routed = s, routed
        return best_routed

    def _route_once(self, program, placement, hw, dist, two_q_positions, rng) -> list[tuple]:
        t = PlacementTracker(placement)
        routed: list[tuple] = []
        decay: dict[int, float] = {p: 1.0 for p in hw.nodes}

        # Map from program index -> position within two_q_positions, to slice the
        # extended set (the next few upcoming 2Q gates) in O(1).
        next_2q_ptr = 0

        for k, op in enumerate(program):
            if op[0] == "1Q":
                routed.append(("1Q", t.phys_of(op[1])))
                continue

            # advance the 2Q pointer to this gate
            while next_2q_ptr < len(two_q_positions) and two_q_positions[next_2q_ptr] < k:
                next_2q_ptr += 1

            _, l, r = op
            extended = self._extended_gates(program, two_q_positions, next_2q_ptr + 1)

            steps = 0
            while not hw.has_edge(t.phys_of(l), t.phys_of(r)):
                if steps >= self.max_swaps_per_gate:
                    # Safety fallback: force progress with a shortest-path hop.
                    self._forced_hop(routed, t, hw, dist, l, r, decay)
                    steps += 1
                    continue
                swap = self._best_swap(t, hw, dist, l, r, extended, decay, rng)
                a, b = swap
                routed.append(("SWAP", a, b))
                t.apply_swap(a, b)
                decay[a] += self.decay_delta
                decay[b] += self.decay_delta
                steps += 1

            routed.append(("2Q", t.phys_of(l), t.phys_of(r)))
            # Executing a gate resets the depth-spreading decay.
            for p in decay:
                decay[p] = 1.0

        return routed

    def _extended_gates(self, program, two_q_positions, start_ptr) -> list[tuple[int, int]]:
        """The next `extended_size` upcoming 2Q gates as (logical_l, logical_r)."""
        out: list[tuple[int, int]] = []
        for ptr in range(start_ptr, min(start_ptr + self.extended_size, len(two_q_positions))):
            op = program[two_q_positions[ptr]]
            out.append((op[1], op[2]))
        return out

    def _candidate_swaps(self, t, hw, l, r) -> list[tuple[int, int]]:
        """Hardware edges incident to the front gate's current physical qubits."""
        pl, pr = t.phys_of(l), t.phys_of(r)
        seen = set()
        cands = []
        for hub in (pl, pr):
            for nb in hw[hub]:
                edge = (hub, nb) if hub < nb else (nb, hub)
                if edge not in seen:
                    seen.add(edge)
                    cands.append(edge)
        return cands

    def _best_swap(self, t, hw, dist, l, r, extended, decay, rng) -> tuple[int, int]:
        cands = self._candidate_swaps(t, hw, l, r)
        best = []
        best_h = float("inf")
        for (a, b) in cands:
            trial = t.clone()
            trial.apply_swap(a, b)
            h = self._heuristic(trial, dist, l, r, extended, decay, a, b)
            if h < best_h - 1e-12:
                best_h = h
                best = [(a, b)]
            elif abs(h - best_h) <= 1e-12:
                best.append((a, b))
        return rng.choice(best)

    def _heuristic(self, trial, dist, l, r, extended, decay, a, b) -> float:
        front = dist[trial.phys_of(l)][trial.phys_of(r)]
        ext = 0.0
        if extended:
            s = 0.0
            for (gl, gr) in extended:
                s += dist[trial.phys_of(gl)][trial.phys_of(gr)]
            ext = self.w_extended * (s / len(extended))
        return max(decay[a], decay[b]) * (front + ext)

    def _forced_hop(self, routed, t, hw, dist, l, r, decay) -> None:
        """Deterministic progress: swap along a shortest path from phys(l) to phys(r)."""
        path = nx.shortest_path(hw, t.phys_of(l), t.phys_of(r))
        a, b = path[0], path[1]
        routed.append(("SWAP", a, b))
        t.apply_swap(a, b)
        decay[a] += self.decay_delta
        decay[b] += self.decay_delta
