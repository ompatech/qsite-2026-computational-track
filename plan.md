# Research Plan — QSITE 2026 Computational Track (Quantum Circuit Compilation)

> **Living document.** This plan governs the research phase (before we write a single line of solver code). We fill in evidence links under each section as we collect them. When each block has enough evidence, we lock the section and move to the paper-design phase.

---

## 0. TL;DR — What we're actually solving

Given (a) a **20-node heavy-hex hardware graph** with diameter ~7 and (b) a stream of **ordered 2Q operations** (the "program"), produce:

1. **`initial_placement`** — an injective map `logical → physical`.
2. **`routed_program`** — the same 2Q ops (in the same order), but on **physical** qubits, with `("SWAP", p, q)` operations inserted so that every 2Q gate lands on an edge.

Judged by (lower is better):

```
score  = Σ_benchmarks  [ swap_count + 0.5 × depth ]
```

The three "sub-problems" (Placement, Routing, Scheduling) are **not independent** — the scorer's `depth` term rewards SWAP choices that don't cluster on the same qubits, so routing implicitly shapes scheduling; placement implicitly shapes routing distances. **One joint optimizer, three simultaneous objectives.** That's our thesis.

**Benchmarks we must beat** (from `starter_kit/benchmarks.py`):
| name | logical qubits | 2Q ops | shape/hint |
|---|---:|---:|---|
| `ghz_star` | 8 | 7 | star — one hot qubit, punishing for scheduling |
| `chain_trotter` | 10 | 9 | linear chain — near-perfect for a chain embedding |
| `ladder_trotter` | 12 | 17 | 2×6 ladder — matches heavy-hex locally |
| `qaoa_random` | 12 | 18 | random pairs — placement is everything |
| `dense_random` | 14 | 40 | pathological — SWAP-heavy no matter what |
| `vqe_layers` | 16 | brick-wall × 3 | high depth, needs parallelism |

**Baseline to beat:** identity placement (L0→P0, L1→P1, …) + greedy shortest-path SWAPs, no scheduling awareness. Documented weak.

**Stretch goals** (not the priority, but plan for time budget):
- **A. Decomposition** — rewrite 2Q gates in a hardware-native basis with cancellations. Bonus: `N × 0.1` per saved gate.
- **B. 1Q optimization** — fuse/cancel single-qubit rotations. Same bonus rate.

---

## 1. Working thesis for the algorithm (revise after research)

Our first hypothesis, before any paper is read:

> A **co-designed compiler pass** built around a **SABRE-style bidirectional routing loop** with (i) a **connectivity-aware initial placement** derived from the program's interaction graph, (ii) a **look-ahead SWAP cost function** that folds in future depth (not just swap count), and (iii) a **DAG-aware layer packer** that runs *inline* with SWAP insertion (not as a post-pass), will beat the baseline on all six benchmarks. Optional: a **local search / simulated-annealing wrapper** around the placement to squeeze the last few percent on `qaoa_random` and `dense_random`.

Concretely, the object being optimized is **the sequence of placements over time** (the "trajectory"), not just the initial map. Placement and routing are two ends of the same object.

Every research item below is chosen to either **support**, **sharpen**, or **falsify** this thesis. If a paper suggests a materially better framing (e.g. RL, ILP, MCTS, or a GNN policy), we log it and reconsider.

---

## 2. Research map (what we need to learn, and why)

Each block has a **question**, **why it matters for our score**, **what evidence looks like**, and a **to-fill checklist**. As we drop links, we mark boxes.

### 2.1 Placement (initial map)

**Central question:** what is the cheapest initial `logical → physical` map for a given program's interaction pattern on this specific 20-node graph?

**Why it matters for score:** a good placement can eliminate 30–70% of SWAPs on structured programs (chain, ladder, star). Placement is the highest-leverage single decision.

**Sub-questions:**
- How is the program's **interaction graph** (nodes = logical qubits, edge weights = # of 2Q gates between them, or their frequency + recency) usually built?
- What **graph embedding** algorithms exist for placing one graph inside another to minimize weighted distance? (Subgraph isomorphism? Graph edit distance? Quadratic assignment?)
- What do SABRE, BIP, and TB-OLSQ do for the initial map?
- Is **reverse-traversal placement** (run router backwards from an identity map, use the final placement as the forward initial map) worth implementing?
- For our specific graph, are there **canonical embeddings** for a chain/ladder/star that give provably-optimal placements?

**Evidence to gather:**
- [ ] SABRE paper §III (reverse traversal for initial map) — Li et al., ASPLOS 2019.
- [ ] BIP / integer-programming placement papers (Nannicini et al., "Optimal qubit assignment and routing…").
- [ ] Simulated annealing for qubit placement (see Qiskit `SabreLayout` code + docs).
- [ ] Any paper on **subgraph isomorphism** for compilation (e.g. VF2 / VF3 usage in Qiskit).
- [ ] Toy: hand-compute optimal placements for `chain_trotter` and `ladder_trotter` on our 20-node graph. If our algorithm doesn't find these, it's broken.

### 2.2 Routing (SWAP insertion)

**Central question:** given the current placement and the remaining program, which SWAPs do we insert next?

**Why it matters:** every SWAP is +1 to the score. Every SWAP that doesn't help downstream is pure waste. Routing is where SABRE gets most of its win.

**Sub-questions:**
- What is the SABRE **heuristic cost function** exactly? (Front layer distance + look-ahead extended-set decay, tuned weight `W`.)
- What is **bidirectional / iterative SABRE** — run forward, use ending placement as new initial, run backward, iterate?
- What alternatives exist? Token swapping (approximation algorithms), A*, beam search, RL policies (arXiv:2405.13196), MCTS, GNN-guided routing.
- What does **NASSC (HPCA 2022)** say about picking SWAPs that enable later gate *cancellations*? Applicable to us via Stretch Goal A?
- How does routing choice affect **depth** (our 0.5× cost)? Do we prefer SWAPs on qubits that are otherwise idle in the next layer?

**Evidence to gather:**
- [ ] SABRE paper — Li, Ding, Xie, ASPLOS 2019 (the whole thing, esp. Alg. 1 + heuristic).
- [ ] IBM SABRE tutorial (link already in the handout) — read for the operational recipe.
- [ ] Qiskit source: `qiskit/transpiler/passes/routing/sabre_swap.py` (implementation reference).
- [ ] "Not All SWAPs Have the Same Cost" — Zhou et al., HPCA 2022 (for Stretch A crossover).
- [ ] RL for transpilation — arXiv:2405.13196.
- [ ] Token-swapping approximation bounds (Miltzow et al.) — sanity floor for how good any router can be on a fixed placement.
- [ ] Any recent 2023–2025 survey on qubit routing (arXiv search: "qubit routing survey").

### 2.3 Scheduling (layer packing)

**Central question:** given a valid routed program, what's the minimum-depth layering?

**Why it matters:** depth is 0.5× per layer. On `vqe_layers` (brick-wall) and `dense_random`, better scheduling can win us multiple points essentially for free.

**Observation from `scorer.py`:** the given scorer uses `schedule_layers_ordered` — **it respects the routed program's order**. That means:
- Once we've fixed the routed program, the layering is *deterministic under this policy*.
- The only way to improve depth is to change **what SWAPs we insert** and **where**, i.e. routing is scheduling.
- **We do not need to invent a fancy scheduler post-hoc** — we need a *scheduling-aware router*.

**Sub-questions:**
- Is the ordered-layer scheduler optimal for the given routed sequence? (Yes, greedy earliest-fit under ordering is optimal for this cost.)
- Can we consider **reordering commuting 2Q gates** in the original program to break dependency chains? *Check rules*: the scorer requires "the remaining operations match the original program in order" after stripping SWAPs — so reordering the program itself would be invalid. We can only reorder SWAPs relative to each other, not program ops. Confirm this reading in `starter.ipynb`.
- Are there **canonical scheduling heuristics** (list scheduling, DAG-based topological) that beat greedy-earliest-fit? Under our fixed constraint the answer is *no for depth alone*, but they matter for the routing cost function.

**Evidence to gather:**
- [ ] Confirm scorer semantics from `starter.ipynb` (esp. whether commuting program-op reorder is allowed).
- [ ] DAG scheduling under precedence constraints (Graham 1966 list scheduling, textbook).
- [ ] Any Qiskit / Cirq scheduling pass code for reference (`ALAPScheduleAnalysis`, `ASAPScheduleAnalysis`).

### 2.4 Joint optimization (the actual thesis)

**Central question:** how do we combine placement + routing + scheduling into one objective?

**Why it matters:** this is the differentiator vs. anyone who just re-implements SABRE.

**Sub-questions:**
- Is the score `swaps + 0.5×depth` linear enough to plug into ILP? (Yes-ish, but ILP is slow at 40 gates × 20 qubits.)
- What's the right **cost function** for a SABRE-like heuristic that folds `depth` in? E.g., `H = Σ_frontlayer dist(gate, current_placement) + α × look_ahead - β × parallel_potential`.
- Can we run the whole solver as a **metaheuristic** (SA / genetic / MCTS) over initial placements, scoring each with a cheap deterministic router?
- Would an **RL policy** trained on random circuits generalize to our 6 benchmarks in the time we have?

**Evidence to gather:**
- [ ] Papers combining placement + routing (BIP, TB-OLSQ, OLSQ2, Molavi et al.).
- [ ] Any paper explicitly using `swaps + λ × depth` as objective.
- [ ] Zulehner–Wille "Efficient mapping of quantum circuits to the IBM QX architectures" (A*-style).
- [ ] Look at Cirq's `RouteCQC` and Qiskit's `SabreSwap` + `SabreLayout` for two well-tuned baselines.

### 2.5 Stretch Goal A — decomposition

**Central question:** can we rewrite gates in a hardware-native basis so that SWAP + neighbor-CX combinations cancel?

- [ ] Read PennyLane compilation tutorial (linked in handout).
- [ ] Read NASSC (already in 2.2) with a decomposition lens.
- [ ] Look at PennyLane `qml.compile`, `qml.transforms.decompose`.
- [ ] Skim: how many gates a SWAP costs when decomposed into 3× CX and what basis change unlocks cancellation?

### 2.6 Stretch Goal B — 1Q fusion / cancellation

- [ ] PennyLane `cancel_inverses`, `merge_rotations`, `single_qubit_fusion` docs.
- [ ] Skim: is any benchmark program 1Q-heavy? (Looking at `benchmarks.py`, they're 2Q-only — Stretch B may score 0 unless we augment. Confirm from `starter.ipynb` whether the grader runs 1Q-heavy hidden benchmarks.)

---

## 3. Evidence collection — the master reading list

We fill this table as we gather. Priority column drives order.

| # | Item | Type | Priority | Section | Status | Notes / key takeaway |
|---:|---|---|---|---|---|---|
| 1 | Li, Ding, Xie — "Tackling the Qubit Mapping Problem for NISQ-Era Quantum Devices" (ASPLOS 2019, SABRE) | paper | P0 | 2.1, 2.2, 2.4 | ☐ | The single most important paper — read *first*, take notes on Alg. 1. |
| 2 | IBM SABRE tutorial (link in handout) | tutorial | P0 | 2.1, 2.2 | ☐ | Operational recipe with code. |
| 3 | Qiskit `SabreSwap` + `SabreLayout` source | code | P0 | 2.1, 2.2 | ☐ | Reference implementation. Read pass code + docstrings. |
| 4 | PostQuantum "Routing Quantum Information" (link in handout) | article | P1 | 2.2 | ☐ | Big-picture / warm-up. |
| 5 | Zulehner, Paler, Wille — A* mapper (IEEE TCAD 2018) | paper | P1 | 2.2, 2.4 | ☐ | Non-SABRE alternative worth understanding. |
| 6 | Nannicini et al. — Optimal qubit assignment & routing (BIP / ILP) | paper | P2 | 2.1, 2.4 | ☐ | Exact-optimal small instances → gold-standard reference for tiny benchmarks. |
| 7 | Molavi et al. — OLSQ / TB-OLSQ / OLSQ2 | paper | P2 | 2.4 | ☐ | SAT/SMT-based joint optimizer. |
| 8 | Zhou et al. — "Not All SWAPs Have the Same Cost" (HPCA 2022) | paper | P2 | 2.2, 2.5 | ☐ | Bridges routing and decomposition. |
| 9 | RL transpilation — arXiv:2405.13196 | paper | P3 | 2.2, 2.4 | ☐ | Only worth trying if we have GPU time and a training set. Likely NOT in scope for the hackathon budget. |
| 10 | Token-swapping approximation bounds (Miltzow, Narayanan, Okamoto) | paper | P3 | 2.2 | ☐ | Theoretical lower-bound lens. |
| 11 | PennyLane compilation tutorial (link in handout) | tutorial | P1 | 2.5, 2.6 | ☐ | Stretch goals. |
| 12 | PennyLane `qml.compile` / `qml.transforms` docs | docs | P1 | 2.5, 2.6 | ☐ | Stretch goals reference. |
| 13 | NetworkX shortest-paths, VF2, algorithms docs | docs | P0 | all | ☐ | We'll be calling these constantly. |
| 14 | Recent survey (2023–2025) on quantum circuit routing | paper | P2 | all | ☐ | To find, arXiv-search "qubit routing survey". |
| 15 | Cirq `RouteCQC` source | code | P2 | 2.2, 2.4 | ☐ | Second reference implementation. |
| 16 | `starter.ipynb` (this repo) — full read | notebook | P0 | all | ☐ | Confirms scorer semantics, benchmark shapes, allowed operations. |
| 17 | User-supplied resources — [drop links here as OM shares them] | ? | P0 | ? | ☐ | Reserved. |

**Legend:** P0 = mandatory before design; P1 = strongly recommended; P2 = pick two based on best fit; P3 = optional / stretch-of-the-stretch.

---

## 4. How we read each source (extraction protocol)

To avoid burning time on skims we can't reuse, every source read produces a **one-page note** in `research/notes/<key>.md` with:

1. **One-sentence summary** of the technique.
2. **Objective function** the paper optimizes.
3. **The algorithm in ≤10 lines of pseudocode.**
4. **Complexity** (in n qubits, m gates, d diameter).
5. **What it beats** and by how much (benchmark, metric).
6. **What plugs into our score** — mark: helps `swaps`, helps `depth`, both, neither.
7. **Open questions / gotchas.**
8. **Snippet of the actual formula or key equation** (verbatim).

We're aiming for ~15 pages of notes total, not a lit review novella.

---

## 5. From evidence to design (post-research phase)

After Section 3 is at ≥80% checked, we run a **design sprint** producing:

1. **`design.md`** — the chosen algorithm(s), objective function, pseudocode, chosen data structures. On paper, no coding yet.
2. **Complexity budget** — expected runtime per benchmark (must complete in seconds, not minutes, given hackathon rerun cycles).
3. **Ablation plan** — what we'll turn on/off to prove each component earns its keep (identity vs. connectivity placement; greedy vs. look-ahead; single-pass vs. iterated).
4. **Risk register** — what breaks (`dense_random` scoring plateau, correctness bugs in SWAP tracking, depth blow-up on `vqe_layers`).

**Gate before implementation:** we can predict, in one paragraph per benchmark, roughly what score we'll get and why. If we can't, we're not ready to code.

---

## 6. Implementation phase (after design)

The plan for `solve()` we'll build:

```
solve(program, hw_graph):
    interaction_graph = build_interaction_graph(program, decay=τ)
    initial = connectivity_aware_placement(interaction_graph, hw_graph)
    # optional: reverse-traversal refinement (SABRE-style)
    initial = reverse_traversal_refine(initial, program, hw_graph, iters=k)
    routed = sabre_route_with_depth_cost(program, initial, hw_graph,
                                         extended_set=E, decay=δ,
                                         depth_weight=0.5)
    # optional: local-search refinement over `initial` if time remains
    return initial, routed
```

Each named function above becomes a small module with unit tests against `scorer.validate_routed_program` and a smoke-test that beats the baseline on `chain_trotter` (which is the easiest sanity check — a straight embedding along the graph's longest path should get 0 SWAPs).

**Milestones:**
1. Reproduce baseline score locally.
2. Beat baseline on `chain_trotter` and `ladder_trotter` with placement-only improvement.
3. Beat baseline on all six with base SABRE.
4. Add depth-aware cost — measure `depth` improvement per benchmark.
5. Add reverse-traversal / SA refinement — measure marginal SWAP gain.
6. Freeze `solve()`, run full scorer, record final numbers.
7. (Optional) Stretch A and B.

---

## 7. Deliverables

- **Draft submission:** GitHub link with working `solve()` + reproducible notebook cell that runs the scorer and prints per-benchmark scores + total.
- **Final submission:** short (3–5 min) video walkthrough — hardware graph, one worked example (probably `ladder_trotter`), a per-benchmark chart of *baseline vs. ours*, and a 60-second "why our joint framing wins" pitch.

---

## 8. Working conventions

- Every source we read → a note file in `research/notes/`.
- Every algorithm we try → a subclassed `solve_<name>()` behind a common interface so we can benchmark them apples-to-apples.
- Every score run → append to `results/scores.csv` (columns: `timestamp, variant, benchmark, swaps, depth, score, notes`). This is our ablation ledger.
- Correctness is non-negotiable: the scorer's `validate_routed_program` must pass on **every** run of every variant. An invalid routed program is worse than a slow one.

---

## 9. Next action

**Now:** OM drops the resources (papers, tutorials, workshop notes, docs) into this plan's Section 3 table (or a `research/inbox/` folder), we sort them by priority, and we start reading in P0 → P3 order producing the note files described in Section 4.

**Trigger to move to Section 5 (design):** Section 3 is ≥80% checked AND the SABRE paper + `starter.ipynb` + the Qiskit `SabreSwap` source have been read and noted.
