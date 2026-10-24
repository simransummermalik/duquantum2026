"""Dependency-free demo of the Watchcat report and dashboard contract.

This is a UI/integration smoke test, not a substitute for Dynamiqs. The next
adapter will turn real Dynamiqs states into the same SimulationRun object.
"""

from __future__ import annotations

import math
from pathlib import Path

from .models import SimulationConfig, SimulationRun
from .pipeline import make_report_payload, write_report
from .watchcat import analyze_convergence


def fake_run(label: str, Na: int, Nb: int, *, error: float, runtime: float) -> SimulationRun:
    times = tuple(index / 20 for index in range(41))
    memory = tuple(4.41 * (1 - math.exp(-3.0 * t)) + error * math.sin(8 * t) for t in times)
    buffer = tuple(2.1 * math.exp(-4.0 * t) + 0.05 * error * math.sin(12 * t) for t in times)
    edge_memory = tuple(max(0.0, error * (0.25 + 0.75 * math.sin(math.pi * t) ** 2)) for t in times)
    edge_buffer = tuple(max(0.0, error * (0.10 + 0.90 * math.exp(-3.0 * t))) for t in times)
    return SimulationRun(
        config=SimulationConfig(Na=Na, Nb=Nb, precision="double", solver="demo", source="qpet.demo"),
        times=times,
        observables={
            "n_memory": memory,
            "n_buffer": buffer,
            "memory_edge_population": edge_memory,
            "buffer_edge_population": edge_buffer,
            "trace": tuple(1.0 for _ in times),
        },
        runtime_seconds=runtime,
        label=label,
    )


def main() -> None:
    reference = fake_run("reference-48x12", 48, 12, error=0.00001, runtime=4.0)
    candidates = [
        fake_run("candidate-16x4", 16, 4, error=0.2, runtime=0.3),
        fake_run("candidate-24x8", 24, 8, error=0.0002, runtime=0.8),
    ]
    report = analyze_convergence(
        candidates,
        reference,
        observables=["n_memory", "n_buffer"],
        abs_tolerance=0.001,
        relative_tolerance=0.01,
    )
    payload = make_report_payload(
        report,
        [reference, *candidates],
        source="synthetic_demo",
        model="synthetic_cat_qubit_trajectory",
        extra={"warning": "Synthetic trajectories only; not a physics result."},
    )
    output = write_report(payload, Path("watchcat_report.json"))
    print(report.to_json())
    print(f"Selected configuration: {report.metrics.get('selected_label') or 'none'}")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
