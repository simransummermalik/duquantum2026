# Watchcat — Quantum Simulation Companion

Watchcat is a research companion for dissipative bosonic quantum simulations. Its
deterministic core checks whether a simulation is numerically trustworthy for
declared observables, compares Fock-space truncations, and recommends a
validated configuration. The pet UI is represented by a custom pixel-art
detective cat: Watchcat investigates suspicious simulation results and reacts
to the evidence.

## Meet Watchcat

<p align="center">
  <img src="assets/watchcat.svg" alt="Watchcat, the pixel-art detective cat" width="320" />
</p>

Watchcat combines a friendly virtual pet with a serious numerical trust layer:

- the detective cat watches Alice & Bob cat-qubit simulations;
- worried expressions flag possible truncation or accuracy problems;
- happy and celebrating expressions appear after validated convergence checks;
- the scientific result always comes from measured diagnostics, never from the
  cat's mood.

The current mascot is a hand-built pixel-art cat rendered on a canvas. It will
become the visual layer for Watchcat's states: sleeping, watching, worried,
happy, and celebrating.

## Current status

The first vertical slice is dependency-free and includes:

- a serializable simulation-run contract;
- edge-population, trace, precision, and photon-number diagnostics;
- observable-aware convergence comparisons;
- measured-runtime-aware configuration recommendations;
- an evidence-backed convergence report;
- a Watchcat dashboard that maps report states to the six cat animations;
- a VS Code extension with a bottom-corner status item and tiny animated popup;
- a synthetic demo report and unit tests.

The demo uses synthetic trajectories only to test the Watchcat contract. It is
not a physics result. A Dynamiqs adapter for the Alice & Bob cat-qubit model is
included, but executing it requires Dynamiqs/JAX to be installed.

## Run the smoke test

```bash
python3 -m unittest discover -s tests -v
python3 -m qpet.demo
python3 -m qpet.server
```

Then open `http://127.0.0.1:8000/`. The generated `watchcat_report.json` is a
local artifact and is ignored by Git. The demo is synthetic and is not a
physics result.

## Use Watchcat inside VS Code

Open this repository in VS Code, press `F5`, and choose **Extension Development
Host**. In the new window, run the sweep and click **Watchcat** in the
bottom-right status bar. The extension lives in
[`vscode-extension`](vscode-extension/README.md), reads the same
`watchcat_report.json`, and refreshes the cat state while you code.

## Run the real Alice & Bob sweep

Install the optional physics dependencies once:

```bash
python3 -m pip install -e ".[physics]"
```

Then run:

```bash
python3 -m qpet.run_sweep
python3 -m qpet.server
```

This runs the full two-mode memory-buffer model over several `(Na, Nb)`
truncations, compares memory and buffer observables, checks boundary
populations, and writes the report consumed by the dashboard.

The default sweep uses the challenge's provided parameters, double precision,
`0 <= t <= 2` microseconds, and the truncations
`16x4, 20x6, 24x8, 32x10, 48x12`. Override them for a faster smoke test, for
example:

```bash
python3 -m qpet.run_sweep --duration 0.2 --samples 5 --truncations 8x3,10x4
```

Watchcat is deliberately conservative: if the reference itself reaches the
top Fock levels, it reports **worried** and recommends increasing the Hilbert
space instead of claiming a false compute saving.

## Next research extensions

1. Wigner snapshots and full Task 1.3 logical-state fidelity/purity analysis.
2. VS Code pet panel consuming the same Watchcat JSON contract.
3. Optional sponsor integrations: Gemini explanations, Backboard memory,
   Tiger Data experiment history, remote Vultr sweeps, and ElevenLabs voice.
