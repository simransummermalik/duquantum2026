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

## Where Watchcat's results come from

The popup reads the workspace file `watchcat_report.json`. It does not invent
simulation values or ask an AI model to decide whether a run is accurate.

There are two ways that file can be produced:

- `python3 -m qpet.demo` writes a **synthetic demo report** for trying the UI.
  Its values are made-up examples and must not be presented as physics results.
- `python3 -m qpet.run_sweep` runs the **Alice & Bob model in Dynamiqs**, then
  writes measured observables and Watchcat's diagnostics to the report. The
  VS Code **Run sweep** button runs this command for you.

The real sweep is assembled in `qpet/dynamiqs_adapter.py` and
`qpet/pipeline.py`. It uses the challenge's two-mode memory and buffer model,
starts both modes in vacuum, and evolves the state with Dynamiqs' Lindblad
master-equation solver. The default parameters are `g₂ = 2π·0.763`,
`κᵦ = 2π·2.6`, `κₐ = 2π·0.0093`, and `α = 2.1`, in the challenge's
rad/µs convention. The default run samples 81 points from 0 to 2 µs at five
memory × buffer Hilbert-space sizes: `16×4`, `20×6`, `24×8`, `32×10`, and
`48×12`.

For each run, Dynamiqs supplies time series for memory and buffer photon
number, memory parity and amplitude, trace, and population near the top of
each truncated Fock space. Watchcat compares the declared observables at
every saved time against the largest requested space, checks trace drift and
boundary population, and writes the evidence, settings, and runtimes into the
JSON report. The largest space is a reference for comparison, not a proven
exact answer.

The popup's numbers mean:

- **target α²**: the target memory photon number from the model parameters.
- **final / peak nₐ**: the memory photon number at the end / its largest value
  during the run.
- **edge population**: population near the highest memory Fock levels; a high
  value warns that the memory space may be too small.
- **parity, purity, even-cat F**: measured logical-state diagnostics at the end
  of the run. These describe the simulation output; they are not accuracy
  guarantees on their own.
- **reference**: the largest requested `Nₐ×Nᵦ` run. **Selected** is filled
  only if a smaller run passes both the configured convergence tolerance and
  the boundary checks. A blank selection means Watchcat found no validated
  cheaper setting.

For example, the included `watchcat_report.json` can say `needs_review` when
memory edge population exceeds the `0.001` threshold. That status comes from
the stored diagnostics, not from the cat animation. See `qpet/watchcat.py` for
the thresholds and decision rules.

## What the voice says

The **Speak** button reads a short explanation composed locally from the
report's status, first diagnostic, and measured final/target photon numbers.
ElevenLabs converts that text to audio; it does not calculate or validate the
quantum result. Watchcat uses `ELEVENLABS_VOICE_ID` and `ELEVENLABS_MODEL_ID`
from `.env`. Eleven v4 adds state-matched delivery cues such as playful,
curious, or sleepy, and the spoken line starts with “Meow!”. The API key stays
in `.env` and is never written to the report or sent to Git.

Voice identity comes from the ElevenLabs voice ID. Delivery tags such as
`[playful]` can guide expression, but they do not turn an arbitrary voice into
a literal cat voice. To use a custom cat character voice, create one with
[ElevenLabs Voice Design](https://elevenlabs.io/docs/overview/capabilities/voices)
and replace `ELEVENLABS_VOICE_ID` in `.env` with that voice's ID. ElevenLabs
explains how to [copy a voice ID from My Voices](https://elevenlabs.io/docs/help-center/technical/how-do-i-find-the-voice-id-of-my-voices-via-the-website-and-api).
Free accounts may be blocked from using shared Voice Library presets through
the API even when those voices appear in the website's preview. Use a voice
your API plan can access; the API's error message explains whether the account
needs credits or a plan change.

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
python3 -m pip install -e ".[physics,visualization]"
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

Each real sweep also writes `watchcat_wigner.png` and a JSON summary for three
reduced-memory snapshots. In the VS Code popup, **Wigner** opens that measured
artifact. Use `--no-wigner` when you only need the scalar diagnostics.

Watchcat is deliberately conservative: if the reference itself reaches the
top Fock levels, it reports **worried** and recommends increasing the Hilbert
space instead of claiming a false compute saving.

For a fast, explicitly scoped preparation-window demonstration, compare the
same model over `0 <= t <= 0.2` microseconds:

```bash
python3 -m qpet.run_sweep \
  --duration 0.2 --samples 9 \
  --truncations 32x10,48x12,64x16 \
  --no-wigner --out watchcat_early_validation.json
```

That measured window validates `48x12` against `64x16`; it is a separate
early-time result, not a replacement for the default 2 microsecond report.

## Next research extensions

1. Full Task 1.3 logical-state fidelity analysis beyond the current purity,
   parity, amplitude, and Wigner evidence.
2. Remote Vultr sweeps after the local convergence workflow is stable.

The sponsor-track mapping and setup commands are in
[`docs/mlh-track-plan.md`](docs/mlh-track-plan.md). Gemini, Backboard, Tiger
Data, and ElevenLabs are optional adapters around the evidence-backed report;
they never replace the numerical checks.

Use [`docs/judge-demo.md`](docs/judge-demo.md) for the short presentation flow.

Copy [`.env.example`](.env.example) into your local environment when testing
the optional integrations. Keep real API keys out of Git.
