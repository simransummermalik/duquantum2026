"""Small, serializable data contracts shared by the Watchcat and its UIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any, Mapping, Sequence


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


@dataclass(frozen=True)
class SimulationConfig:
    """Metadata needed to interpret one simulation run."""

    Na: int
    Nb: int
    precision: str = "double"
    time_unit: str = "microseconds"
    rate_unit: str = "rad_per_microsecond"
    solver: str = "unknown"
    atol: float | None = None
    rtol: float | None = None
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.Na < 2 or self.Nb < 2:
            raise ValueError("Na and Nb must each be at least 2")


@dataclass(frozen=True)
class SimulationRun:
    """An observable-only representation of a simulation result.

    Full density matrices stay outside this contract. The adapter that reads a
    Dynamiqs result computes the requested observables and passes their time
    series here, keeping the UI lightweight and reproducible.
    """

    config: SimulationConfig
    times: tuple[float, ...]
    observables: Mapping[str, tuple[float, ...]]
    runtime_seconds: float | None = None
    label: str = "run"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.times:
            raise ValueError("A simulation run needs at least one saved time")
        if any(not _finite(t) for t in self.times):
            raise ValueError("Simulation times must be finite")
        if any(right <= left for left, right in zip(self.times, self.times[1:])):
            raise ValueError("Simulation times must be strictly increasing")
        length = len(self.times)
        for name, values in self.observables.items():
            if len(values) != length:
                raise ValueError(f"Observable {name!r} has the wrong length")
            if any(not _finite(value) for value in values):
                raise ValueError(f"Observable {name!r} contains a non-finite value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "times": list(self.times),
            "observables": {name: list(values) for name, values in self.observables.items()},
            "runtime_seconds": self.runtime_seconds,
            "label": self.label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    recommendation: str | None = None


@dataclass(frozen=True)
class ConvergenceComparison:
    candidate_label: str
    reference_label: str
    passed: bool
    max_abs_error: float
    max_relative_error: float
    per_observable: Mapping[str, Mapping[str, float]]
    abs_tolerance: float
    relative_tolerance: float


@dataclass(frozen=True)
class WatchcatReport:
    run_label: str
    pet_state: str
    status: str
    diagnostics: tuple[Diagnostic, ...]
    metrics: Mapping[str, Any]
    comparisons: tuple[ConvergenceComparison, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_label": self.run_label,
            "pet_state": self.pet_state,
            "status": self.status,
            "diagnostics": [asdict(item) for item in self.diagnostics],
            "metrics": dict(self.metrics),
            "comparisons": [asdict(item) for item in self.comparisons],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)
