"""Command-line entry point for a real Dynamiqs convergence sweep."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import (
    DEFAULT_TRUNCATIONS,
    make_report_payload,
    run_dynamiqs_introductory_sweep,
    write_report,
)
from .dynamiqs_adapter import CatParameters


def _parse_truncations(value: str) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for item in value.split(","):
        try:
            Na, Nb = item.strip().lower().split("x", 1)
            pairs.append((int(Na), int(Nb)))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid truncation {item!r}; use Na×Nb, e.g. 24x6") from exc
    return tuple(pairs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Alice & Bob cat-qubit Watchcat sweep")
    parser.add_argument("--duration", type=float, default=2.0, help="Simulation duration in microseconds")
    parser.add_argument("--samples", type=int, default=81)
    parser.add_argument("--truncations", type=_parse_truncations, default=DEFAULT_TRUNCATIONS)
    parser.add_argument("--out", type=Path, default=Path("watchcat_report.json"))
    args = parser.parse_args()

    report, runs = run_dynamiqs_introductory_sweep(
        truncations=args.truncations,
        duration_microseconds=args.duration,
        samples=args.samples,
    )
    payload = make_report_payload(
        report,
        runs,
        source="dynamiqs",
        model="alice_bob.full_two_mode",
        extra={
            "challenge_track": "Alice & Bob Introductory Track",
            "units": {"time": "microseconds", "rates": "rad_per_microsecond"},
            "math": {
                "alpha": CatParameters().alpha,
                "alpha_squared": CatParameters().alpha**2,
                "g2": CatParameters().g2,
                "kappa_b": CatParameters().kappa_b,
                "kappa_a": CatParameters().kappa_a,
                "eps_d": CatParameters().eps_d,
                "kappa_2_effective": CatParameters().kappa_2,
                "convergence_rule": "max_t |candidate - reference| <= abs_tol + rel_tol * max_t |reference|",
            },
        },
    )
    destination = write_report(payload, args.out)
    print(report.to_json())
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
