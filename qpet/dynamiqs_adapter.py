"""Dynamiqs adapter for the Alice & Bob cat-qubit challenge.

Dynamiqs and JAX are optional at import time. This keeps the Watchcat core
testable on a clean machine while making the real challenge model a first-class
integration once those packages are installed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Iterable, Sequence

from .models import SimulationConfig, SimulationRun


@dataclass(frozen=True)
class CatParameters:
    """Challenge parameters in rad / microsecond units."""

    g2: float = 2 * math.pi * 0.763
    kappa_b: float = 2 * math.pi * 2.6
    kappa_a: float = 2 * math.pi * 9.3e-3
    alpha: float = 2.1

    @property
    def eps_d(self) -> float:
        return self.alpha**2 * self.g2

    @property
    def kappa_2(self) -> float:
        return 4 * self.g2**2 / self.kappa_b

    def ratios(self) -> dict[str, float]:
        return {
            "g2_over_kappa_b": self.g2 / self.kappa_b,
            "eps_d_over_kappa_b": self.eps_d / self.kappa_b,
        }


@dataclass(frozen=True)
class DynamiqsModel:
    H: Any
    jump_ops: Sequence[Any]
    psi0: Any
    exp_ops: Sequence[Any]
    observable_names: tuple[str, ...]
    config: SimulationConfig
    metadata: dict[str, Any]


def build_full_two_mode_model(
    dq: Any,
    jnp: Any,
    *,
    Na: int = 24,
    Nb: int = 6,
    params: CatParameters | None = None,
) -> DynamiqsModel:
    """Build the full memory-buffer model from the challenge prompt."""

    params = params or CatParameters()
    a, b = dq.destroy(Na, Nb)
    H = (
        params.g2 * (a @ a @ b.dag())
        + params.g2 * (a.dag() @ a.dag() @ b)
        - params.eps_d * (b + b.dag())
    )
    jump_ops = [jnp.sqrt(params.kappa_b) * b, jnp.sqrt(params.kappa_a) * a]
    psi0 = dq.tensor(dq.fock(Na, 0), dq.fock(Nb, 0))

    identity_a = dq.eye(Na)
    identity_b = dq.eye(Nb)
    n_memory = a.dag() @ a
    n_buffer = b.dag() @ b
    memory_parity = dq.tensor(dq.parity(Na), identity_b)
    # ``dq.destroy(Na, Nb)`` already returns operators embedded in the full
    # two-mode Hilbert space.  Tensoring ``a`` again would accidentally create
    # an extra buffer mode (and a 3-mode observable), which Dynamiqs cannot
    # evaluate against the two-mode state.
    memory_amplitude_real = (a + a.dag()) / 2
    edge_memory = dq.tensor(
        dq.fock_dm(Na, Na - 1) + dq.fock_dm(Na, Na - 2),
        identity_b,
    )
    edge_buffer = dq.tensor(identity_a, dq.fock_dm(Nb, Nb - 1))
    trace = dq.tensor(identity_a, identity_b)
    exp_ops = [n_memory, n_buffer, edge_memory, edge_buffer, trace, memory_parity, memory_amplitude_real]
    names = (
        "n_memory",
        "n_buffer",
        "memory_edge_population",
        "buffer_edge_population",
        "trace",
        "memory_parity",
        "memory_amplitude_real",
    )
    config = SimulationConfig(
        Na=Na,
        Nb=Nb,
        precision="double",
        solver="dynamiqs.mesolve",
        source="alice_bob.full_two_mode",
    )
    return DynamiqsModel(
        H=H,
        jump_ops=jump_ops,
        psi0=psi0,
        exp_ops=exp_ops,
        observable_names=names,
        config=config,
        metadata={
            "model": "full_two_mode",
            "parameters": params.__dict__,
            "ratios": params.ratios(),
        },
    )


def build_effective_single_mode_model(
    dq: Any,
    jnp: Any,
    *,
    Na: int = 30,
    params: CatParameters | None = None,
) -> DynamiqsModel:
    """Build the effective single-mode stabilization model from Task 1.0(c)."""

    params = params or CatParameters()
    a = dq.destroy(Na)
    identity = dq.eye(Na)
    H = 0 * identity
    jump_ops = [
        jnp.sqrt(params.kappa_2) * (a @ a - params.alpha**2 * identity),
        jnp.sqrt(params.kappa_a) * a,
    ]
    psi0 = dq.fock(Na, 0)
    exp_ops = [a.dag() @ a, dq.parity(Na)]
    config = SimulationConfig(
        Na=Na,
        Nb=2,
        precision="double",
        solver="dynamiqs.mesolve",
        source="alice_bob.effective_single_mode",
    )
    return DynamiqsModel(
        H=H,
        jump_ops=jump_ops,
        psi0=psi0,
        exp_ops=exp_ops,
        observable_names=("n_memory", "parity"),
        config=config,
        metadata={
            "model": "effective_single_mode",
            "parameters": params.__dict__,
            "ratios": params.ratios(),
        },
    )


def run_model(dq: Any, model: DynamiqsModel, tsave: Any, *, method: Any = None) -> Any:
    """Run a prepared model using the current Dynamiqs API."""

    dq.set_precision("double")
    kwargs = {"exp_ops": list(model.exp_ops)}
    if method is not None:
        kwargs["method"] = method
    return dq.mesolve(model.H, list(model.jump_ops), model.psi0, tsave, **kwargs)


def run_model_to_run(
    dq: Any,
    model: DynamiqsModel,
    tsave: Any,
    *,
    method: Any = None,
    label: str | None = None,
) -> SimulationRun:
    """Run one model and convert it into the serializable Watchcat contract."""

    started = time.perf_counter()
    result = run_model(dq, model, tsave, method=method)
    runtime = time.perf_counter() - started
    return result_to_run(
        result,
        model,
        label=label or f"Na{model.config.Na}-Nb{model.config.Nb}",
        runtime_seconds=runtime,
    )


def run_truncation_sweep(
    dq: Any,
    jnp: Any,
    tsave: Any,
    truncations: Iterable[tuple[int, int]],
    *,
    params: CatParameters | None = None,
    method: Any = None,
) -> tuple[tuple[SimulationRun, ...], SimulationRun]:
    """Run a convergence sweep and return all runs plus the reference run.

    The reference is the largest requested memory-buffer space. Its result is
    deliberately still passed through Watchcat rather than treated as exact.
    """

    requested = sorted(set((int(Na), int(Nb)) for Na, Nb in truncations))
    if not requested:
        raise ValueError("At least one truncation pair is required")
    runs: list[SimulationRun] = []
    for Na, Nb in requested:
        model = build_full_two_mode_model(dq, jnp, Na=Na, Nb=Nb, params=params)
        runs.append(run_model_to_run(dq, model, tsave, method=method))
    reference = max(runs, key=lambda run: (run.config.Na * run.config.Nb, run.config.Na, run.config.Nb))
    return tuple(runs), reference


def result_to_run(
    result: Any,
    model: DynamiqsModel,
    *,
    label: str = "dynamiqs-run",
    runtime_seconds: float | None = None,
) -> SimulationRun:
    """Convert a Dynamiqs result's saved expectation values into Watchcat data."""

    times = tuple(float(value) for value in result.tsave.tolist())
    expects = result.expects
    observables: dict[str, tuple[float, ...]] = {}
    for index, name in enumerate(model.observable_names):
        values = expects[index]
        if hasattr(values, "real"):
            values = values.real
        observables[name] = tuple(float(value) for value in values.tolist())
    return SimulationRun(
        config=model.config,
        times=times,
        observables=observables,
        runtime_seconds=runtime_seconds,
        label=label,
        metadata=model.metadata,
    )
