# Challenge 1: Compiling for Quantum Computers

# Overview

> **You are given a set of quantum programs and a hardware connectivity graph. Your core job: find a qubit placement and SWAP routing strategy that executes all required interactions using the fewest SWAP operations and parallel time steps.**
>
> **For extra points**, optimize the gate decomposition and single-qubit gate layers - we provide intentionally bad baselines for both that are easy to beat.

The problem can be broken roughly into three sub-problems:

### 1. Placement

**Question**: which logical qubit goes on which physical qubit?

**Why it matters**: a good placement puts frequently-interacting logical qubits on nearby physical qubits, reducing the number of SWAPs needed. A bad placement puts them far apart.

**CS framing**: this is a **graph assignment** problem. You're mapping the nodes of one graph (your program's interaction pattern) onto the nodes of another graph (the hardware), trying to minimize some distance metric.

**Possible approaches**: random assignment, degree-matching heuristics, simulated annealing, exhaustive search on small instances.

### 2. Routing

**Question**: when two qubits need to interact but aren't adjacent, which SWAPs do you insert?

**Why it matters**: every SWAP adds cost. Greedy routing (always SWAP along the shortest path to the current gate) ignores the rest of the program - a SWAP that helps gate #5 might make gate #6 much harder.

**CS framing**: this is a **path planning** problem with a twist - every SWAP changes the state of the graph (qubit positions move), so future routing depends on past decisions.

**Possible approaches**: greedy shortest-path, look-ahead heuristics that consider upcoming gates, SABRE-style bidirectional search. See the [IBM SABRE tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) for a detailed walkthrough of the best known heuristic.

### 3. Scheduling

**Question**: which two-qubit operations can run at the same time?

**Why it matters**: running gates in parallel reduces the total circuit depth (execution time). Two 2-qubit gates can run simultaneously if they act on disjoint sets of qubits.

**CS framing**: this is a **DAG scheduling** / **bin packing** problem. Build a dependency graph of operations that respects both the original gate order and qubit conflicts, then assign operations to time slots such that no two operations in the same slot share a qubit.

**Possible approaches**: sequential execution (no parallelization), greedy layer packing, DAG-based topological scheduling.

---



## The Compilation Pipeline

```
Abstract Circuit
      ↓
  [Placement]        assign logical qubits to physical qubits       ⬅ CORE CHALLENGE
      ↓
  [Routing]          insert SWAPs so all 2Q gates are on neighbors   ⬅ CORE CHALLENGE
      ↓
  [Scheduling]       pack gates into parallel time steps              ⬅ CORE CHALLENGE
      ↓
  [Decomposition]    rewrite gates into hardware-native gate set     ⬅ STRETCH GOAL A
      ↓
  [1Q Optimization]  fuse/cancel redundant single-qubit gates        ⬅ STRETCH GOAL B
      ↓
Executable Circuit
```

## Essential Resources

- [PostQuantum: Routing Quantum Information](https://postquantum.com/quantum-computing/routing-quantum-information/) - visual intro to SWAP routing
- [IBM SABRE Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) - the industry-standard routing algorithm explained
- [Python `networkx` docs](https://networkx.org/documentation/stable/) - graph algorithms you'll use heavily
- [PennyLane: Compilation of Quantum Circuits](https://pennylane.ai/qml/demos/tutorial_circuit_compilation) - useful for stretch goals

# Strategy Guide & Resources

### For the Core Challenge
- 📖 [PostQuantum: Routing Quantum Information](https://postquantum.com/quantum-computing/routing-quantum-information/) - start here for the big picture
- 📖 [IBM SABRE Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) - detailed walkthrough of the best known routing heuristic
- 🔧 [networkx: Shortest Paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html) - `nx.shortest_path()` is your best friend
- 🔧 [networkx: Graph Generators](https://networkx.org/documentation/stable/reference/generators.html) - if you want to test on other topologies

### For Stretch Goals
- 📖 [PennyLane: Compilation of Quantum Circuits](https://pennylane.ai/qml/demos/tutorial_circuit_compilation) - full walkthrough of gate cancellation, rotation merging, and decomposition
- 🔧 [PennyLane `qml.compile` docs](https://docs.pennylane.ai/en/stable/code/api/pennylane.compile.html) - one-liner compilation with configurable pipeline
- 🔧 [PennyLane `qml.transforms` reference](https://docs.pennylane.ai/en/stable/code/qml_transforms.html) - `cancel_inverses`, `merge_rotations`, `single_qubit_fusion`, `decompose`

### Extra
- 📄 Li et al., "Tackling the Qubit Mapping Problem for NISQ-Era Quantum Devices" (ASPLOS 2019) - the original SABRE paper
- 📄 [RL-based transpilation (arXiv:2405.13196)](https://arxiv.org/abs/2405.13196) - reinforcement learning for SWAP selection
- 📄 [NASSC: Not All SWAPs Have the Same Cost (HPCA 2022)](https://hzhou.wordpress.ncsu.edu/files/2022/12/HPCA22_NASSC.pdf) - choosing SWAPs that enable downstream gate cancellation
