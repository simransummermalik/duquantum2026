"""Deterministic diagnostics for Q-Pet's first vertical slice."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, Sequence

from .models import (
    ConvergenceComparison,
    Diagnostic,
    SimulationRun,
    WatchcatReport,
)


def _max(values: Sequence[float]) -> float:
    return max((float(value) for value in values), default=0.0)


def _last(values: Sequence[float]) -> float | None:
    return float(values[-1]) if values else None


def analyze_run(
    run: SimulationRun,
    *,
    edge_tolerance: float = 1e-3,
    trace_tolerance: float = 1e-8,
) -> WatchcatReport:
    """Analyze one run without guessing beyond the supplied evidence.

    The result is intentionally scoped: a clean report means the supplied
    checks passed, not that every possible observable is converged.
    """

    diagnostics: list[Diagnostic] = []
    metrics: dict[str, object] = {
        "Na": run.config.Na,
        "Nb": run.config.Nb,
        "precision": run.config.precision,
        "duration": run.times[-1] - run.times[0],
        "runtime_seconds": run.runtime_seconds,
    }

    if "memory_edge_population" in run.observables:
        peak = _max(run.observables["memory_edge_population"])
        metrics["peak_memory_edge_population"] = peak
        if peak > edge_tolerance:
            diagnostics.append(
                Diagnostic(
                    code="MEMORY_EDGE_POPULATION",
                    severity="warning",
                    message="Memory population reaches the truncation boundary.",
                    evidence={"peak": peak, "threshold": edge_tolerance, "Na": run.config.Na},
                    recommendation="Increase Na and compare the transient observables.",
                )
            )

    if "buffer_edge_population" in run.observables:
        peak = _max(run.observables["buffer_edge_population"])
        metrics["peak_buffer_edge_population"] = peak
        if peak > edge_tolerance:
            diagnostics.append(
                Diagnostic(
                    code="BUFFER_EDGE_POPULATION",
                    severity="warning",
                    message="Buffer population reaches the truncation boundary.",
                    evidence={"peak": peak, "threshold": edge_tolerance, "Nb": run.config.Nb},
                    recommendation="Increase Nb; the buffer transient can be larger than its steady state.",
                )
            )

    if "trace" in run.observables:
        drift = max(abs(float(value) - 1.0) for value in run.observables["trace"])
        metrics["max_trace_drift"] = drift
        if drift > trace_tolerance:
            diagnostics.append(
                Diagnostic(
                    code="TRACE_DRIFT",
                    severity="error",
                    message="The density-matrix trace drifts beyond the configured tolerance.",
                    evidence={"max_drift": drift, "threshold": trace_tolerance},
                    recommendation="Check solver tolerances, precision, and the model adapter.",
                )
            )

    if run.config.precision.lower() not in {"double", "float64", "complex128"}:
        diagnostics.append(
            Diagnostic(
                code="LOW_PRECISION",
                severity="warning",
                message="The run is not marked as double precision.",
                evidence={"precision": run.config.precision},
                recommendation="Use double precision for slow decays and convergence checks.",
            )
        )

    if "n_memory" in run.observables:
        values = run.observables["n_memory"]
        metrics["memory_photon_peak"] = _max(values)
        metrics["memory_photon_final"] = _last(values)
        if len(values) > 1 and values[-1] > values[0] * 1.25:
            pet_state = "watching"
        else:
            pet_state = "idle"
    else:
        pet_state = "watching"

    if diagnostics:
        pet_state = "worried"
        status = "needs_review" if not any(item.severity == "error" for item in diagnostics) else "invalid"
    else:
        pet_state = pet_state
        status = "observed"

    return WatchcatReport(
        run_label=run.label,
        pet_state=pet_state,
        status=status,
        diagnostics=tuple(diagnostics),
        metrics=metrics,
    )


def analyze_convergence(
    candidates: Sequence[SimulationRun],
    reference: SimulationRun,
    *,
    observables: Iterable[str],
    abs_tolerance: float = 1e-3,
    relative_tolerance: float = 1e-2,
    edge_tolerance: float = 1e-3,
    trace_tolerance: float = 1e-8,
) -> WatchcatReport:
    """Build the evidence-backed report that drives the Watchcat UI.

    A candidate must pass both the convergence comparison and the standalone
    numerical diagnostics. This prevents a cheaper run from being recommended
    merely because its selected observables look close while its population is
    reaching the Fock-space boundary.
    """

    comparisons: list[ConvergenceComparison] = []
    clean_labels: set[str] = set()
    for run in candidates:
        comparison = compare_runs(
            run,
            reference,
            observables=observables,
            abs_tolerance=abs_tolerance,
            relative_tolerance=relative_tolerance,
        )
        comparisons.append(comparison)
        run_report = analyze_run(
            run,
            edge_tolerance=edge_tolerance,
            trace_tolerance=trace_tolerance,
        )
        if not any(item.severity in {"warning", "error"} for item in run_report.diagnostics):
            clean_labels.add(run.label)

    passing = [
        run
        for run, comparison in zip(candidates, comparisons)
        if comparison.passed and run.label in clean_labels
    ]

    def cost(run: SimulationRun) -> tuple[float, float]:
        measured = run.runtime_seconds if run.runtime_seconds is not None else math.inf
        proxy = float((run.config.Na * run.config.Nb) ** 2)
        return (measured if math.isfinite(measured) else proxy, proxy)

    selected = min(passing, key=cost) if passing else None
    base = analyze_run(
        selected or reference,
        edge_tolerance=edge_tolerance,
        trace_tolerance=trace_tolerance,
    )
    metrics = dict(base.metrics)
    metrics.update(
        {
            "reference_label": reference.label,
            "reference_Na": reference.config.Na,
            "reference_Nb": reference.config.Nb,
            "candidate_count": len(candidates),
            "passing_count": len(passing),
            "selected_label": selected.label if selected else None,
            "selected_Na": selected.config.Na if selected else None,
            "selected_Nb": selected.config.Nb if selected else None,
            "abs_tolerance": abs_tolerance,
            "relative_tolerance": relative_tolerance,
        }
    )

    diagnostics = list(base.diagnostics)
    if selected is None:
        diagnostics.append(
            Diagnostic(
                code="NO_VALIDATED_CONFIGURATION",
                severity="error",
                message="No candidate truncation passed both convergence and boundary checks.",
                evidence={
                    "candidate_count": len(candidates),
                    "passing_convergence_count": sum(item.passed for item in comparisons),
                },
                recommendation="Increase Na or Nb and rerun the convergence study.",
            )
        )
        pet_state = "worried"
        status = "needs_review"
    elif diagnostics:
        pet_state = "worried"
        status = "needs_review"
    elif selected.config.Na < reference.config.Na or selected.config.Nb < reference.config.Nb:
        pet_state = "celebrating"
        status = "validated_optimization"
    else:
        pet_state = "happy"
        status = "validated"

    return replace(
        base,
        run_label=selected.label if selected else reference.label,
        pet_state=pet_state,
        status=status,
        diagnostics=tuple(diagnostics),
        metrics=metrics,
        comparisons=tuple(comparisons),
    )


def compare_runs(
    candidate: SimulationRun,
    reference: SimulationRun,
    *,
    observables: Iterable[str] | None = None,
    abs_tolerance: float = 1e-3,
    relative_tolerance: float = 1e-2,
) -> ConvergenceComparison:
    """Compare time-aligned observables and return an auditable result."""

    if candidate.times != reference.times:
        raise ValueError("Candidate and reference runs must use the same saved times")

    names = list(observables or sorted(set(candidate.observables) & set(reference.observables)))
    if not names:
        raise ValueError("No shared observables were supplied")

    per_observable: dict[str, dict[str, float]] = {}
    max_abs = 0.0
    max_relative = 0.0
    passed = True

    for name in names:
        if name not in candidate.observables or name not in reference.observables:
            raise ValueError(f"Observable {name!r} is missing from one run")
        candidate_values = candidate.observables[name]
        reference_values = reference.observables[name]
        abs_error = max(abs(float(left) - float(right)) for left, right in zip(candidate_values, reference_values))
        scale = max(max(abs(float(value)) for value in reference_values), abs_tolerance)
        relative_error = abs_error / scale
        allowed = abs_tolerance + relative_tolerance * scale
        observable_passed = abs_error <= allowed
        per_observable[name] = {
            "max_abs_error": abs_error,
            "max_relative_error": relative_error,
            "allowed_error": allowed,
            "passed": observable_passed,
        }
        max_abs = max(max_abs, abs_error)
        max_relative = max(max_relative, relative_error)
        passed = passed and observable_passed

    return ConvergenceComparison(
        candidate_label=candidate.label,
        reference_label=reference.label,
        passed=passed,
        max_abs_error=max_abs,
        max_relative_error=max_relative,
        per_observable=per_observable,
        abs_tolerance=abs_tolerance,
        relative_tolerance=relative_tolerance,
    )


def recommend_run(
    runs: Sequence[SimulationRun],
    reference: SimulationRun,
    *,
    observables: Iterable[str] | None = None,
    abs_tolerance: float = 1e-3,
    relative_tolerance: float = 1e-2,
) -> tuple[SimulationRun | None, tuple[ConvergenceComparison, ...]]:
    """Pick the cheapest passing run using measured runtime when available."""

    comparisons: list[ConvergenceComparison] = []
    passing: list[SimulationRun] = []
    for run in runs:
        comparison = compare_runs(
            run,
            reference,
            observables=observables,
            abs_tolerance=abs_tolerance,
            relative_tolerance=relative_tolerance,
        )
        comparisons.append(comparison)
        if comparison.passed:
            passing.append(run)

    def cost(run: SimulationRun) -> tuple[float, int]:
        measured = run.runtime_seconds if run.runtime_seconds is not None else math.inf
        # This is only a fallback proxy; reports should show measured runtime.
        proxy = (run.config.Na * run.config.Nb) ** 2
        return (measured if math.isfinite(measured) else float(proxy), proxy)

    selected = min(passing, key=cost) if passing else None
    return selected, tuple(comparisons)
