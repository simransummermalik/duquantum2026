"""Q-Pet's deterministic Numerical Watchcat core.

The core intentionally has no cloud, UI, or LLM dependencies. It turns
simulation outputs into evidence-backed diagnostics that other interfaces can
consume later.
"""

from .models import (
    ConvergenceComparison,
    Diagnostic,
    SimulationConfig,
    SimulationRun,
    WatchcatReport,
)
from .watchcat import analyze_run, compare_runs, recommend_run
from .dynamiqs_adapter import CatParameters

__all__ = [
    "ConvergenceComparison",
    "Diagnostic",
    "SimulationConfig",
    "SimulationRun",
    "WatchcatReport",
    "analyze_run",
    "compare_runs",
    "recommend_run",
    "CatParameters",
]
