# Layered Portfolio Compiler — `solver/`

A qubit-mapping compiler for the QSITE 2026 Computational Track. One `solve()`
(in `../solve.py`) runs several placement×router candidates, scores each with the
**real** competition metric (`swaps + 0.5·depth`), and returns the best valid one.

## Results (portfolio best-of vs. baseline)

| benchmark | baseline | ours (strong) | winning strategy |
|---|--:|--:|---|
| ghz_star | 14.0 | **6.5** | annealing |
| chain_trotter | 15.0 | **4.5** | structure (path, 0 swaps) |
| ladder_trotter | 35.5 | **6.5** | annealing |
| qaoa_random | 39.0 | **12.5** | annealing |
| dense_random | 122.0 | **40.5** | annealing |
| vqe_layers | 58.0 | **3.0** | structure (path, 0 swaps) |
| **total** | **283.5** | **73.5** | **−74%** |

The `identity + greedy` anchor reproduces the baseline 283.5 exactly (an honesty
check on the harness). Strong config ≈ 80 s for all six; the light default
(`bench.py`) is ≈ 9 s and reaches 81.5.

## Architecture

```
solve.py                     required entrypoint: solve(program, hardware_graph)
solver/
  interaction.py             weighted logical interaction graph (layer-decay weights)
  hardware_analysis.py       graph-agnostic facts: distances, hubs, longest path
  metrics.py                 thin wrapper over starter_kit.scorer (the real objective)
  pipeline.py                Portfolio: run candidates, score real metric, pick best
  placement/
    identity.py              baseline anchor
    connectivity.py          center-seeded greedy weighted embedding
    structure.py             family detector (path/star/grid) + exact embeddings
    annealing.py             SA search over placements, scored by real route
    refine.py                reverse-traversal wrapper (available, not in default portfolio)
  routing/
    tracker.py               logical<->physical bookkeeping (+ final_layout replay)
    greedy.py                baseline shortest-path anchor
    sabre.py                 SABRE decay router, ordered emission, multi-seed
```

## Key design decisions

- **Ordered emission.** The scorer requires the routed program, with SWAPs
  stripped, to equal the input *in exact order*. So the router emits 2Q gates in
  input order (front layer = next gate); look-ahead lives in the extended set.
  This makes every output valid by construction.
- **Select on the true metric, never a proxy.** Everything terminates in
  `core_score`. Candidate selection and SA both minimize `swaps + 0.5·depth`.
- **Property-based family detection.** `detect_family` classifies by graph
  properties (degree sequence, grid isomorphism), not benchmark names, so it
  generalizes; anything unrecognized falls back to connectivity placement.
- **Portfolio.** With no known grader time limit, running a handful of candidates
  and keeping the best is safe (no single strategy can misfire on a shape) and
  near-optimal. The generic fallback is always present.
- **Spare qubits as scratch.** Only 8–16 of 20 physical qubits are used; SA may
  relocate logical qubits onto empty physical qubits, and the tracker handles
  SWAPs with empty qubits correctly.

## Run

```bash
python bench.py            # light portfolio, ~9s, prints table + logs results/scores.csv
python bench.py --strong   # strong SA, ~80s, best scores
python bench.py --anchors  # baseline anchors only (must total 283.5)
python tests/test_correctness.py   # validity + baseline reproduction
python tests/test_structure.py     # family detection + fallback
python tests/test_scores.py        # score regression vs ceilings
```
