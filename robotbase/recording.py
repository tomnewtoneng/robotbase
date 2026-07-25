"""MCAP episode recording — pure helpers (no docker/ROS side effects).

Phase 1 of the episode-record layer (see docs/design/mcap-recording.md): build the
`ros2 bag record` invocation and the self-describing `episode.json` sidecar. Kept free of
I/O so it is unit-testable with plain data; the Runtime and scenario runner call into it.
"""
from __future__ import annotations

import os
import time
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


def embed_attachment(mcap_path: str, name: str, data: bytes,
                     media_type: str = "application/json") -> bool:
    """Rewrite an MCAP file with an attachment added, so the single file is self-describing
    (carries its scenario + result, not just the topic trace). Runs host-side — the recorded
    file is host-owned — and faithfully copies every schema/channel/message. Returns True on
    success, False (leaving the original untouched) if mcap is unavailable or anything fails.
    """
    try:
        from mcap.reader import make_reader
        from mcap.writer import Writer
    except ImportError:
        return False
    tmp = mcap_path + ".tmp"
    try:
        with open(mcap_path, "rb") as inp, open(tmp, "wb") as out:
            reader = make_reader(inp)
            writer = Writer(out)
            writer.start()
            schemas: dict[int, int] = {}
            channels: dict[int, int] = {}
            for schema, channel, message in reader.iter_messages():
                if schema is not None and schema.id not in schemas:
                    schemas[schema.id] = writer.register_schema(
                        schema.name, schema.encoding, schema.data)
                if channel.id not in channels:
                    channels[channel.id] = writer.register_channel(
                        channel.topic, channel.message_encoding,
                        schemas.get(channel.schema_id, 0), channel.metadata)
                writer.add_message(channels[channel.id], message.log_time, message.data,
                                   message.publish_time, message.sequence)
            now = time.time_ns()
            writer.add_attachment(now, now, name, media_type, data)
            writer.finish()
        os.replace(tmp, mcap_path)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


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
