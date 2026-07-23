"""MCAP episode recording — pure helpers (no docker/ROS side effects).

Phase 1 of the episode-record layer (see docs/design/mcap-recording.md): build the
`ros2 bag record` invocation and the self-describing `episode.json` sidecar. Kept free of
I/O so it is unit-testable with plain data; the Runtime and scenario runner call into it.
"""
from __future__ import annotations

from typing import Any


def record_selection(topics: list[str], exclude: list[str], available: list[str]) -> list[str]:
    """Return the topic-selection args for `ros2 bag record`.

    An explicit allow-list wins; otherwise record every currently-available topic. In
    both cases the exclude deny-list is removed. Passing an explicit list (rather than
    `-a`) keeps the recorded set deterministic and inspectable. Falls back to ``["-a"]``
    only when nothing is known to record.
    """
    denied = set(exclude or [])
    if topics:
        selected = [t for t in topics if t not in denied]
        if selected:
            return selected
    selected = [t for t in (available or []) if t not in denied]
    return selected or ["-a"]


def record_command(dest: str, selection: list[str]) -> str:
    """Build the shell command that records an episode to *dest* as MCAP.

    Clears any prior staging dir first (``ros2 bag record`` refuses to overwrite) and
    records with sim time so message log-times align with the simulation clock.
    """
    sel = " ".join(selection)
    return (
        f'rm -rf {dest} && mkdir -p "$(dirname {dest})" && '
        f"ros2 bag record --storage mcap --use-sim-time -o {dest} {sel}"
    )


def episode_events(result: Any) -> list[dict]:
    """Derive the (Phase 1, coarse) event list from a scenario result.

    Phase 1 reports *whether* notable things happened; precise per-event timestamps
    arrive with the Phase 2 query verbs that read back the MCAP.
    """
    events: list[dict] = []
    if getattr(result.metrics, "collision_count", 0):
        events.append(
            {
                "type": "collision",
                "timestamp": None,
                "detail": "collision detected during the episode "
                "(precise timing lands with the Phase 2 query verbs)",
            }
        )
    return events


def episode_sidecar(scenario: Any, result: Any, recording: dict | None) -> dict:
    """Build the self-describing `episode.json` written next to `episode.mcap`.

    Bundles the scenario spec, the full result, the recording metadata, and the derived
    events so the episode directory is interpretable on its own — the seed of the open
    episode artifact format (versioned).
    """
    info = recording or {}
    return {
        "version": 1,
        "run_id": result.run_id,
        "scenario": result.scenario,
        "passed": result.passed,
        "recording": {
            "mcap": info.get("mcap"),
            "storage": "mcap",
            "topics": info.get("topics", []),
        },
        "scenario_spec": scenario.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "events": episode_events(result),
    }
