# QSITE 2026 — Quantum Coalition Open Challenge · Computational Track

**A qubit-mapping compiler for 20-qubit heavy-hex hardware.**
Given a quantum program (an ordered list of 2-qubit operations) and a hardware
connectivity graph, we produce an initial qubit **placement** and a SWAP-inserted
**routing** that keeps every 2-qubit gate on physically adjacent qubits — while
minimizing the competition objective:

```
score = swap_count + 0.5 × depth
```

> **Draft submission (Sept 23).** This README summarizes our approach and current
> results. The implementation is complete and reproducible; wording, ablations,
> and the final write-up will be tightened for the final submission.

---

## Results

Portfolio best-of vs. the provided baseline, across the six reference program
families:

| benchmark | baseline | **ours** | reduction |
|---|--:|--:|--:|
| ghz_star | 14.0 | **6.5** | −54% |
| chain_trotter | 15.0 | **4.5** | −70% |
| ladder_trotter | 35.5 | **6.5** | −82% |
| qaoa_random | 39.0 | **12.5** | −68% |
| dense_random | 122.0 | **40.5** | −67% |
| vqe_layers | 58.0 | **3.0** | −95% |
| **total** | **283.5** | **73.5** | **−74%** |

An `identity + greedy` anchor reproduces the baseline **283.5** exactly — an
honesty check that our harness scores with the *real* competition metric and
nothing is being flattered.

---

## The strategy in one picture

We do **not** bet on a single clever algorithm. Different program shapes have
different optimal mappings, so we run a small **portfolio** of placement × router
candidates, score each one with the *true* objective, and return the best valid
result.

```
program ──► [ candidate 1 ]  placement × router ──► score
        ├─► [ candidate 2 ]  placement × router ──► score  ──►  argmin  ──► best valid mapping
        └─► [ candidate 3 ]  placement × router ──► score
```

Three ideas make this work:

1. **Structure-aware placement.** Before searching, we detect the *family* of the
   interaction graph from its properties (not its name): path-like, star-like,
   grid-like, or generic. The hardware graph contains a **Hamiltonian path**, so
   chain- and path-shaped programs embed with **zero SWAPs**. Stars snap onto a
   high-degree hub; grids onto a matching sub-lattice; everything else falls back
   to a connectivity-driven greedy embedding.

2. **Search that optimizes the real score.** For the hard, irregular programs
   (QAOA, dense random), a simulated-annealing search explores placements and is
   scored end-to-end by actually routing and measuring `swaps + 0.5·depth` — never
   a proxy. Spare physical qubits (only 8–16 of 20 are used) are available as
   routing scratch.

3. **A look-ahead router with valid-by-construction output.** Routing uses a
   SABRE-style heuristic with decay (to spread depth) and an extended look-ahead
   set. Crucially, gates are **emitted in the program's exact order**, so the
   routed program — with SWAPs stripped — always equals the input. This satisfies
   the grader's ordering constraint by construction; every candidate we return is
   valid.

The portfolio guarantees no single strategy can misfire on an unfamiliar shape:
the generic fallback is always present, and we keep whichever candidate the real
metric says is best.

---

## Repository layout

```
Computational Track/
  solve.py                 required entrypoint: solve(program, hardware_graph)
  solver/
    interaction.py         weighted logical interaction graph
    hardware_analysis.py   graph-agnostic facts: distances, hubs, longest path
    metrics.py             wrapper over the official scorer (the true objective)
    pipeline.py            portfolio: run candidates, score, pick best valid
    placement/             identity · connectivity · structure · annealing · refine
    routing/               tracker · greedy (baseline) · sabre (look-ahead)
  bench.py                 benchmark harness → results table + CSV ledger
  tests/                   validity, baseline reproduction, family detection, score regression
```

## Run it

```bash
python bench.py            # portfolio over all six benchmarks (~9s) — prints table
python bench.py --strong   # stronger search (~80s) — best scores (73.5 total)
python bench.py --anchors  # baseline anchors only (must total 283.5)
python -m pytest tests/    # validity + baseline reproduction + score regression
```

## Design principles

- **Select on the true metric, never a proxy.** Every decision terminates in the
  competition score.
- **Generalize by property, not by name.** Family detection reads graph structure,
  so it works on programs we've never seen.
- **Valid by construction.** Ordered emission means the router cannot produce an
  out-of-order (invalid) program.
- **Portfolio over silver bullet.** With no known grader time limit, running a
  handful of candidates and keeping the best is both safe and near-optimal.

---

*QSITE 2026 Quantum Coalition Open Challenge — Computational Track.*
