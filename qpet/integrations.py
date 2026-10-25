"""Optional MLH-track integrations for Watchcat.

The numerical report remains the source of truth. Sponsor services explain,
remember, store, or speak that report; none of them are allowed to decide
whether a quantum simulation is numerically converged.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _load_local_env() -> None:
    """Load simple KEY=value entries without requiring python-dotenv."""

    env_file = Path(".env")
    if not env_file.exists():
        return
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    local_voice_settings = {"ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL_ID"}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # VS Code may inherit stale voice settings from the shell that launched
        # it. The project's .env is the source of truth for these two choices.
        if key and (key in local_voice_settings or not os.environ.get(key)):
            os.environ[key] = value


def _report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("report", {})
    metrics = report.get("metrics", {})
    return {
        "run_label": report.get("run_label"),
        "pet_state": report.get("pet_state"),
        "status": report.get("status"),
        "Na": metrics.get("Na"),
        "Nb": metrics.get("Nb"),
        "reference_Na": metrics.get("reference_Na"),
        "reference_Nb": metrics.get("reference_Nb"),
        "selected_Na": metrics.get("selected_Na"),
        "selected_Nb": metrics.get("selected_Nb"),
        "memory_photon_final": metrics.get("memory_photon_final"),
        "memory_photon_peak": metrics.get("memory_photon_peak"),
        "target_memory_photons": metrics.get("target_memory_photons"),
        "peak_memory_edge_population": metrics.get("peak_memory_edge_population"),
        "max_trace_drift": metrics.get("max_trace_drift"),
        "runtime_seconds": metrics.get("runtime_seconds"),
        "diagnostics": [item.get("code") for item in report.get("diagnostics", [])],
    }


def _local_explanation(payload: dict[str, Any]) -> str:
    report = payload.get("report", {})
    metrics = report.get("metrics", {})
    diagnostics = report.get("diagnostics", [])
    state = report.get("pet_state", "idle")
    final = metrics.get("memory_photon_final")
    target = metrics.get("target_memory_photons")
    final_line = ""
    if isinstance(final, (int, float)) and isinstance(target, (int, float)):
        final_line = f" The memory ends at {final:.3f} photons versus the semiclassical target α²={target:.3f}."
    if diagnostics:
        first = diagnostics[0]
        reason = str(first.get("message", "a diagnostic needs review")).rstrip(".")
        return (
            f"Watchcat is {state} because {reason}."
            f"{final_line} The result is not certified; increase the relevant Hilbert-space truncation "
            "and rerun the time-aligned convergence comparison."
        )
    return f"Watchcat is {state}.{final_line} The supplied observables passed the configured checks."


def _explanation_prompt(payload: dict[str, Any]) -> str:
    return (
        "You are explaining a numerical quantum-simulation report to a hackathon judge. "
        "Use only the JSON evidence below. Do not claim convergence if status is not validated. "
        "Mention the key diagnostic, the target alpha-squared comparison, and the next action "
        "in at most four concise sentences.\n\n"
        + json.dumps(_report_summary(payload), indent=2, sort_keys=True)
    )


def _openai_explanation(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Use the OpenAI Responses API without putting provider details in the UI."""

    model = os.getenv("WATCHCAT_AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    endpoint = os.getenv("WATCHCAT_AI_BASE_URL", "https://api.openai.com/v1/responses")
    result = _post_json(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        body={"model": model, "input": _explanation_prompt(payload)},
    )
    text = result.get("output_text")
    if not text:
        for item in result.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    text = content["text"]
                    break
            if text:
                break
    return {"provider": "ai", "text": text or _local_explanation(payload), "configured": True}


def explain_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Explain a report with a configured AI backend, otherwise use local evidence."""

    _load_local_env()
    fallback = _local_explanation(payload)
    provider = os.getenv("WATCHCAT_AI_PROVIDER", "").strip().lower()
    generic_key = os.getenv("WATCHCAT_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if provider == "openai" and generic_key:
        try:
            return _openai_explanation(payload, generic_key)
        except Exception as exc:  # optional network path must never break Watchcat
            return {"provider": "local-fallback", "configured": True, "error": str(exc), "text": fallback}

    api_key = os.getenv("GEMINI_API_KEY") or (generic_key if provider == "gemini" else None)
    if not api_key:
        return {"provider": "local-fallback", "text": fallback, "configured": False}

    try:
        from google import genai

        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        client = genai.Client(api_key=api_key)
        prompt = (
            "You are explaining a numerical quantum-simulation report to a hackathon judge. "
            "Use only the JSON evidence below. Do not claim convergence if status is not validated. "
            "Mention the key diagnostic, the target alpha-squared comparison, and the next action "
            "in at most four concise sentences.\n\n"
            + json.dumps(_report_summary(payload), indent=2, sort_keys=True)
        )
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None) or fallback
        return {"provider": "gemini", "model": model, "text": text, "configured": True}
    except Exception as exc:  # optional network/dependency path must never break Watchcat
        return {
            "provider": "local-fallback",
            "configured": True,
            "error": str(exc),
            "text": fallback,
        }


def _post_json(url: str, *, headers: dict[str, str], body: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def remember_backboard(payload: dict[str, Any]) -> dict[str, Any]:
    _load_local_env()
    api_key = os.getenv("BACKBOARD_API_KEY")
    assistant_id = os.getenv("BACKBOARD_ASSISTANT_ID")
    if not api_key or not assistant_id:
        return {"provider": "backboard", "configured": False, "stored": False}
    summary = _report_summary(payload)
    try:
        result = _post_json(
            f"https://app.backboard.io/api/assistants/{assistant_id}/memories",
            headers={"X-API-Key": api_key},
            body={
                "content": "Watchcat experiment result: " + json.dumps(summary, sort_keys=True),
                "metadata": {"product": "Watchcat", "source": payload.get("source", "unknown")},
            },
        )
        return {"provider": "backboard", "configured": True, "stored": True, "response": result}
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {"provider": "backboard", "configured": True, "stored": False, "error": str(exc)}


def remember_tiger_data(payload: dict[str, Any]) -> dict[str, Any]:
    _load_local_env()
    database_url = os.getenv("WATCHCAT_TIGER_DATABASE_URL") or os.getenv("TIGER_DATA_DATABASE_URL")
    if not database_url:
        return {"provider": "tiger-data", "configured": False, "stored": False}
    try:
        import psycopg

        summary = _report_summary(payload)
        with psycopg.connect(database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS watchcat_runs (
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    run_label TEXT,
                    status TEXT,
                    na INTEGER,
                    nb INTEGER,
                    runtime_seconds DOUBLE PRECISION,
                    memory_photon_peak DOUBLE PRECISION,
                    peak_memory_edge_population DOUBLE PRECISION,
                    report JSONB NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO watchcat_runs
                (run_label, status, na, nb, runtime_seconds, memory_photon_peak,
                 peak_memory_edge_population, report)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    summary["run_label"],
                    summary["status"],
                    summary["Na"],
                    summary["Nb"],
                    summary["runtime_seconds"],
                    summary["memory_photon_peak"],
                    summary["peak_memory_edge_population"],
                    json.dumps(summary),
                ),
            )
        return {"provider": "tiger-data", "configured": True, "stored": True}
    except Exception as exc:  # optional database path must never break Watchcat
        return {"provider": "tiger-data", "configured": True, "stored": False, "error": str(exc)}


def record_experiment(payload: dict[str, Any], path: str | Path = "watchcat_history.json") -> dict[str, Any]:
    """Always keep a local history, then mirror it to configured sponsor services."""

    destination = Path(path)
    try:
        history = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {"runs": []}
        if not isinstance(history, dict) or not isinstance(history.get("runs"), list):
            history = {"runs": []}
        history["runs"].append(_report_summary(payload))
        destination.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        local = {"provider": "local", "configured": True, "stored": True, "path": str(destination)}
    except (OSError, ValueError) as exc:
        local = {"provider": "local", "configured": True, "stored": False, "error": str(exc)}
    return {
        "local": local,
        "backboard": remember_backboard(payload),
        "tiger_data": remember_tiger_data(payload),
    }


def speak_report(payload: dict[str, Any], output: str | Path = "watchcat_alert.mp3", *, play: bool = False) -> dict[str, Any]:
    """Generate an optional ElevenLabs voice alert; return a local message without a key."""

    _load_local_env()
    text = _local_explanation(payload)
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return {"provider": "local-fallback", "configured": False, "spoken": False, "text": text}
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not voice_id:
        return {
            "provider": "elevenlabs",
            "configured": True,
            "spoken": False,
            "error": "Set ELEVENLABS_VOICE_ID in .env to a voice your API plan can use.",
            "text": text,
        }
    model_id = os.getenv("ELEVENLABS_MODEL_ID") or "eleven_v4"
    if model_id in {"eleven_v4", "eleven_v4_turbo", "eleven_v3"}:
        pet_state = payload.get("report", {}).get("pet_state", "idle")
        delivery = {
            "worried": "[concerned, bright cartoon cat voice]",
            "happy": "[happy, bright cartoon cat voice]",
            "celebrating": "[excited, bright cartoon cat voice]",
            "sleeping": "[sleepy, soft cartoon cat voice]",
            "watching": "[curious, bright cartoon cat voice]",
        }.get(pet_state, "[playful, bright cartoon cat voice]")
        text = f"{delivery} Meow! {text}"
    try:
        request = Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
            data=json.dumps({"text": text, "model_id": model_id}).encode("utf-8"),
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            Path(output).write_bytes(response.read())
        played = False
        if play and sys.platform == "darwin":
            try:
                subprocess.run(
                    ["afplay", str(output)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                played = True
            except (subprocess.SubprocessError, OSError) as exc:
                playback_error = getattr(exc, "stderr", None) or str(exc)
                return {
                    "provider": "elevenlabs",
                    "configured": True,
                    "spoken": False,
                    "generated": True,
                    "played": False,
                    "path": str(output),
                    "error": playback_error.strip(),
                    "text": text,
                }
        return {
            "provider": "elevenlabs",
            "configured": True,
            "spoken": True,
            "generated": True,
            "played": played,
            "path": str(output),
            "text": text,
        }
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            detail = ""
        try:
            error_body = json.loads(detail)
        except (TypeError, ValueError):
            error_body = {}
        api_detail = error_body.get("detail") if isinstance(error_body, dict) else None
        if isinstance(api_detail, dict):
            message = api_detail.get("message")
            code = api_detail.get("code")
            if message:
                detail = f"{message} ({code})" if code else str(message)
        elif isinstance(api_detail, str):
            detail = api_detail
        return {
            "provider": "elevenlabs",
            "configured": True,
            "spoken": False,
            "error": detail or f"HTTP {exc.code}: {exc.reason}",
            "text": text,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {"provider": "elevenlabs", "configured": True, "spoken": False, "error": str(exc), "text": text}


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional Watchcat sponsor integrations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("explain", "remember", "speak"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--report", type=Path, default=Path("watchcat_report.json"))
        if command == "explain":
            subparser.add_argument("--out", type=Path)
        if command == "speak":
            subparser.add_argument("--out", type=Path, default=Path("watchcat_alert.mp3"))
            subparser.add_argument("--play", action="store_true")

    args = parser.parse_args()
    payload = _load(args.report)
    if args.command == "explain":
        result = explain_report(payload)
        if args.out:
            args.out.write_text(result["text"] + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "remember":
        print(json.dumps(record_experiment(payload), indent=2, sort_keys=True))
    else:
        print(json.dumps(speak_report(payload, args.out, play=args.play), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
