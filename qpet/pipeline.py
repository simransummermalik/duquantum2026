"""End-to-end orchestration for the Watchcat MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import SimulationRun, WatchcatReport
from .watchcat import analyze_convergence


DEFAULT_TRUNCATIONS: tuple[tuple[int, int], ...] = (
    (16, 4),
    (20, 6),
    (24, 8),
    (32, 10),
    (48, 12),
)
DEFAULT_OBSERVABLES: tuple[str, ...] = (
    "n_memory",
    "n_buffer",
    "memory_parity",
    "memory_amplitude_real",
)


def make_report_payload(
    report: WatchcatReport,
    runs: Iterable[SimulationRun],
    *,
    source: str,
    model: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the JSON contract consumed by the Watchcat dashboard."""

    payload: dict[str, Any] = {
        "product": "Watchcat",
        "source": source,
        "model": model,
        "report": report.to_dict(),
        "runs": [run.to_dict() for run in runs],
    }
    if extra:
        payload.update(extra)
    return payload


def write_report(payload: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_dynamiqs_introductory_sweep(
    *,
    truncations: Iterable[tuple[int, int]] = DEFAULT_TRUNCATIONS,
    duration_microseconds: float = 2.0,
    samples: int = 81,
    abs_tolerance: float = 1e-3,
    relative_tolerance: float = 1e-2,
) -> tuple[WatchcatReport, tuple[SimulationRun, ...]]:
    """Run the real Alice & Bob full two-mode sweep.

    Dynamiqs/JAX are imported only when this function is called so the
    dependency-free diagnostics and UI remain runnable on a clean machine.
    """

    import dynamiqs as dq
    import jax.numpy as jnp

    from .dynamiqs_adapter import run_truncation_sweep

    dq.set_precision("double")
    tsave = jnp.linspace(0.0, duration_microseconds, samples)
    runs, reference = run_truncation_sweep(
        dq,
        jnp,
        tsave,
        truncations,
    )
    report = analyze_convergence(
        runs,
        reference,
        observables=DEFAULT_OBSERVABLES,
        abs_tolerance=abs_tolerance,
        relative_tolerance=relative_tolerance,
    )
    return report, runs
