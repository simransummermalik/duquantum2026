"""Wigner snapshots for the Alice & Bob logical-state evidence.

The numerical verdict still comes from the scalar diagnostics in ``watchcat``.
This module produces a compact visual artifact for the judge/demo workflow:
three reduced-memory-state Wigner snapshots at preparation, inflation, and the
final saved time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _snapshot_indices(count: int) -> tuple[int, ...]:
    if count <= 0:
        return ()
    return tuple(dict.fromkeys((0, count // 2, count - 1)))


def write_wigner_snapshots(
    dq: Any,
    result: Any,
    model: Any,
    output_path: str | Path,
    *,
    xmax: float = 5.0,
    ymax: float = 5.0,
    npixels: int = 81,
) -> dict[str, Any]:
    """Write reduced-memory Wigner snapshots and a machine-readable summary.

    The JSON summary is always written.  The PNG is written when matplotlib is
    available; this keeps the core sweep usable on headless/minimal installs.
    """

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    states = getattr(result, "states", None)
    if states is None:
        raise ValueError("Dynamiqs result does not contain saved states")

    import numpy as np

    indices = _snapshot_indices(len(result.tsave))
    snapshots: list[dict[str, Any]] = []
    grids: list[tuple[Any, Any, Any]] = []
    for index in indices:
        rho_memory = dq.ptrace(states[index], keep=0)
        xvec, yvec, values = dq.wigner(
            rho_memory,
            xmax=xmax,
            ymax=ymax,
            npixels=npixels,
        )
        values_np = np.asarray(values)
        x_np = np.asarray(xvec)
        y_np = np.asarray(yvec)
        dx = float(abs(x_np[1] - x_np[0])) if len(x_np) > 1 else 0.0
        dy = float(abs(y_np[1] - y_np[0])) if len(y_np) > 1 else 0.0
        negative_volume = float(np.sum(np.maximum(-values_np, 0.0)) * dx * dy)
        snapshots.append(
            {
                "time": float(result.tsave[index]),
                "minimum": float(values_np.min()),
                "maximum": float(values_np.max()),
                "negative_volume": negative_volume,
            }
        )
        grids.append((x_np, y_np, values_np))

    summary: dict[str, Any] = {
        "path": str(destination),
        "mode": "memory_reduced_wigner",
        "grid": {"xmax": xmax, "ymax": ymax, "pixels": npixels},
        "snapshots": snapshots,
        "interpretation": (
            "Wigner snapshots are visual logical-state evidence. They complement, "
            "but do not replace, parity, purity, trace, and truncation checks."
        ),
    }

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(1, len(grids), figsize=(11, 3.7), squeeze=False)
        axes_row = axes[0]
        for axis, snapshot, (xvec, yvec, values) in zip(axes_row, snapshots, grids):
            image = axis.contourf(xvec, yvec, values, levels=25, cmap="RdBu_r")
            axis.set_title(f"t = {snapshot['time']:.2f} μs")
            axis.set_xlabel("Re(α)")
            axis.set_ylabel("Im(α)")
            axis.set_aspect("equal")
            figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        figure.suptitle("Watchcat · reduced-memory Wigner snapshots")
        figure.tight_layout()
        figure.savefig(destination, dpi=150, bbox_inches="tight")
        plt.close(figure)
        summary["png_written"] = True
    except ImportError:
        summary["png_written"] = False
        summary["png_note"] = "Install matplotlib to render the PNG; JSON evidence is still available."

    summary_path = destination.with_suffix(".json")
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
