# Implementation Plan — QSITE 2026 Computational Track

> Companion to `plan.md` (research) and the eventual `strategies.md`. This is the build spec: architecture, phases, tests, and milestones. We implement **bit by bit, testing each piece against the real scorer before moving on.**

---

## 0. Finalized strategy — "Layered Portfolio Compiler"

One `solve()` that is a **portfolio**: it runs a few placement×router combinations, scores each with the **real competition metric** (`swaps + 0.5·depth`) via the starter scorer, and returns the best valid result. Because the challenge has **no known grader time limit**, running several cheap candidates and keeping the winner is both safe (no single strategy can misfire on a shape) and near-optimal.

The candidates are three **layers**, built in order, each reusing the last:

- **Layer 1 — Retuned SABRE core (POC).** Connectivity-aware placement (center-seeded greedy on the weighted interaction graph) → **SABRE `decay` router** (basic + lookahead·W + decay·δ), with multi-seed trials selected by our real metric. Beats the baseline on all six on its own.
- **Layer 2 — Structure-aware placement.** A **family detector** on the interaction graph (path / star / grid-ladder / generic, by graph properties — *not* benchmark names) that produces an exact/near-exact embedding using this graph's Hamiltonian path and degree-3 hubs. Feeds Layer 1's router. This is where the big structured-benchmark wins come from.
- **Layer 3 — Placement search (SA).** Simulated annealing / multi-restart over the initial placement, each candidate scored by a full real-metric route. Seeded from Layer 2. Wins the unstructured benchmarks (`qaoa_random`, `dense_random`) where placement dominates. Uses the spare physical qubits (only 8–16 of 20 are occupied) as legal reassignment targets.

**Design principles (hold from day one):**
1. **Correctness is non-negotiable** — every candidate must pass `validate_routed_program`; an invalid result is dropped from the portfolio, never returned.
2. **Select on the true metric**, never a proxy. Everything terminates in `core_score`.
3. **Pluggable interfaces** — placement and routing are swappable objects, so the POC is literally the first entry of the final portfolio, not a throwaway.
4. **No overfitting** — family detection is property-based; we validate it degrades gracefully to the generic path on shapes it doesn't recognize.

---

## 1. Hardware facts we exploit (verified in code)

- Graph: 20 nodes, 23 edges, **diameter 9**, radius 5, **center = {8,9,10,11}**.
- Degree-3 hubs: {2,5,6,9,10,13,14,17}. Dead-ends (deg 1): {3,16}.
- **A Hamiltonian path exists:** `3-2-1-0-4-5-6-7-11-10-9-8-12-13-14-15-19-18-17-16`. → any chain/linear program embeds with **0 SWAPs**; brick-wall (VQE) embeds along it nearly perfectly.
- Only 8–16 logical qubits are used → **spare physical qubits are routing scratch / reassignment space.**
- Benchmarks are **pure 2Q** → Stretch Goal B (1Q fusion) is out of scope for the core score.
- In this scorer **a SWAP = 1 gate and 1 layer** (not 3 CNOTs) → depth is a light tiebreaker the decay term handles; cancellation-aware decomposition (NASSC/TANGO `Reward`) only matters for Stretch A.

**Baseline to beat (total 283.5):** ghz_star 14.0 · chain 15.0 · ladder 35.5 · qaoa 39.0 · dense 122.0 · vqe 58.0.

---

## 2. Target architecture

```
Computational Track/
  solve.py                     # REQUIRED submission entrypoint: solve(program, hardware_graph)
  solver/
    __init__.py
    interaction.py             # build weighted interaction graph (TANGO layer-decay weights)
    metrics.py                 # thin wrapper over starter_kit.scorer; our objective helpers
    pipeline.py                # Portfolio: compose placement×router, score real metric, pick best
    placement/
      base.py                  # Placement protocol: place(program, hw, interaction) -> dict
      identity.py              # baseline (sanity / regression anchor)
      connectivity.py          # Layer 1: center-seeded greedy on interaction graph
      structure.py             # Layer 2: family detector + exact embeddings
      annealing.py             # Layer 3: SA / multi-restart search over placements
    routing/
      base.py                  # Router protocol: route(program, placement, hw) -> routed_program
      greedy.py                # baseline shortest-path (regression anchor)
      sabre.py                 # Layer 1: SABRE basic/lookahead/decay, multi-seed
  tests/
    test_correctness.py        # every variant valid on all benchmarks
    test_scores.py             # regression: score <= recorded best (per benchmark)
    test_structure.py          # family detector: correct family + graceful fallback
  results/
    scores.csv                 # ledger: timestamp,variant,benchmark,swaps,depth,score
  bench.py                     # runs all variants over all benchmarks, prints table, appends ledger
```

**Core data structures (match the scorer exactly):**
- `program`: `list[tuple]` — `("2Q", i, j)` / `("1Q", i)` on **logical** qubits.
- `placement`: `dict[int,int]` — logical → physical, injective.
- `routed_program`: `list[tuple]` — same ops on **physical** qubits with `("SWAP", p, q)` inserted; every `("2Q", p, q)` on a hardware edge.
- `interaction`: `nx.Graph` — nodes = logical qubits, edge weight = Σ layer-decay weight of gates on that pair.

**Interfaces (stable from the start):**
```python
# placement/base.py
class Placement(Protocol):
    def place(self, program, hw, interaction) -> dict[int,int]: ...
# routing/base.py
class Router(Protocol):
    def route(self, program, placement, hw) -> list[tuple]: ...
# pipeline.py
def portfolio_solve(program, hw, candidates) -> tuple[dict, list[tuple]]:
    # run each (Placement, Router), validate, score real metric, return best valid
```

`solve.py` is a one-liner over `portfolio_solve` with the finalized candidate list — so improving the compiler never changes the submission entrypoint.

---

## 3. Phased build plan (with independent tests + expected results)

Each phase ends only when its test passes and the ledger shows the expected improvement.

### Phase 0 — Harness (foundation)
- Build `interaction.py`, `metrics.py`, `bench.py`, the two protocols, and `identity`/`greedy` anchors (wrapping the baseline).
- **Test:** `bench.py` reproduces the baseline total **283.5** exactly; `test_correctness` passes for the baseline.
- **Why first:** everything downstream is measured by this harness. No solver logic yet.

### Phase 1 — POC core (this is the Sept 23 deliverable)
- `connectivity.py`: weighted interaction graph → seed highest-weight logical qubit at a center node {9,10} → greedily place remaining logical qubits at the free physical node minimizing weighted distance to already-placed neighbors (TANGO dual-factor, simplified).
- `sabre.py`: SABRE `decay` heuristic (`H = max(decay(q1),decay(q2)) · [ (1/|F|)ΣD_F + W·(1/|E|)ΣD_E ]`), front-layer loop, neighbor-restricted SWAP candidates, multi-seed trials, **select trial by real `swaps + 0.5·depth`.**
- `pipeline.py`: portfolio with the single `(connectivity, sabre-decay)` candidate.
- **Test:** valid on all six; **total strictly < 283.5**, with `chain_trotter` swaps in low single digits and every benchmark ≤ baseline. Target: comfortably under ~200.
- **Milestone: commit + push → GitHub link is the draft submission.**

### Phase 2 — Structure-aware placement
- `structure.py`: detect family by interaction-graph properties —
  - **path/chain:** max degree ≤ 2 and connected → embed along the Hamiltonian path (expect chain → **0 swaps**).
  - **star:** one node of degree n−1 → center on a degree-3 hub, order leaves by adjacency.
  - **grid/ladder:** 2×k grid signature → embed in a heavy-hex 2×k block.
  - **generic:** fall back to `connectivity`.
- Add `(structure, sabre-decay)` to the portfolio.
- **Test:** `test_structure` confirms correct family + fallback on a random graph; scores on chain/ladder/star/vqe drop materially vs Phase 1 (chain reaches ~0 swaps).

### Phase 3 — Placement search (SA)
- `annealing.py`: SA over placement; moves = reassign a logical qubit (incl. onto an empty physical node) or swap two assignments; objective = real route score; seed from `structure`; restarts; wall-clock cap (configurable, generous since no grader limit).
- Add `(annealing, sabre-decay)` to the portfolio.
- **Test:** `qaoa_random` and `dense_random` improve vs Phase 2; no regression elsewhere (portfolio keeps the best).

### Phase 4 — Polish / stretch (post-draft, before final)
- Optional: SABRE **reverse-traversal** initial-map refinement; TANGO **executable-gate-first** router as an extra candidate; token-swapping for provably-good fixed-permutation segments; Stretch A decomposition only if it's free points.
- **Test:** each addition must lower total or it's cut.

---

## 4. Test & tracking discipline
- **Every** solver run goes through `validate_routed_program` — invalid = dropped, logged, never returned.
- `results/scores.csv` is the ablation ledger; `bench.py` appends a row per (variant, benchmark) run.
- `test_scores.py` pins the best-known score per benchmark; a change that regresses any benchmark fails CI-style before commit.
- Regression anchors kept forever: `identity`+`greedy` must always reproduce 283.5 (proves the harness is honest).

---

## 5. Open research items (pull the trigger only if a phase needs it)
- **Reverse-traversal tuning** (SABRE §III) — if Phase 1 placement underperforms on random benchmarks before Phase 3 lands.
- **Token swapping** (Miltzow 1602.05150) — optimal routing for a *fixed* target permutation; useful if we want a provable-quality inner router for structured segments.
- **Exact A*/ILP** (Zulehner 2018 / Nannicini 2106.06446) — only as a **gold-standard check** on the two smallest benchmarks (ghz_star=8, chain=10); too slow as the engine.
- **Stretch A decomposition** (NASSC 2205.10596, TANGO `Reward`) — revisit only if core score plateaus and we want the `N×0.1` bonus.

---

## 6. Risk register
| Risk | Mitigation |
|---|---|
| SWAP bookkeeping bug → invalid output | Portfolio validates every candidate; regression tests on all six every commit. |
| Structure detector overfits the six | Property-based families + `test_structure` fallback case on a random graph. |
| SA burns time for marginal gain | Wall-clock cap + seeded from structure; portfolio keeps best regardless. |
| Depth balloons on vqe/dense | Decay term spreads SWAPs; depth is in the selection metric, not an afterthought. |
| Hidden benchmarks (non-six) | Generic path + connectivity fallback always present in the portfolio. |

---

## 7. Immediate next action
Build **Phase 0 + Phase 1** → that's the POC for the Sept 23 draft (GitHub link). Then Phase 2, Phase 3 before final. Start coding Phase 0 (`interaction.py`, `metrics.py`, protocols, `bench.py`, baseline anchors) and confirm it reproduces 283.5.
