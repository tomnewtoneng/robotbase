"""Auto-diagnosis — turn a failed run into a plain-language, evidence-linked *why*.

Deterministic and rule-based (no LLM/API): it correlates each failed assertion with the
relevant episode event and the control/sensor behaviour at the failure, and states it in
words. An agent can read the structured findings and elaborate; a human can read them
directly. The logic is pure and unit-tested; the CLI/MCP gather the inputs (the stored
result, the derived events, a `/cmd_vel` sample at the failure) and call `diagnose`.
"""
from __future__ import annotations

from typing import Any


def _r(v):
    return round(v, 3) if isinstance(v, float) else v


def _finding(assertion: dict, metrics: dict, events: list[dict]) -> str:
    t = assertion["type"]
    exp, act = assertion.get("expected"), _r(assertion.get("actual"))
    collision = next((e for e in events if e["type"] == "collision"), None)
    closest = next((e for e in events if e["type"] == "closest_approach"), None)

    if t in ("no_contact", "no_collision"):
        if collision:
            return f"Collided at t={collision['timestamp']}s ({collision['detail']})."
        return "A collision was registered during the run."
    if t == "minimum_obstacle_distance":
        where = f" near {closest['position']}" if closest and closest.get("position") else ""
        return f"Came within {act} m of an obstacle{where} (needed ≥ {exp} m)."
    if t == "robot_reached_pose":
        pos = (round(metrics.get("final_x", 0.0), 2), round(metrics.get("final_y", 0.0), 2))
        return f"Stopped {act} m from the goal at {pos} (needed ≤ {exp} m)."
    if t == "robot_stopped":
        return f"Was still moving at the end (final speed {_r(metrics.get('final_linear_velocity'))} m/s)."
    if t == "robot_moved_minimum_distance":
        return f"Only travelled {act} m (needed ≥ {exp} m)."
    if t == "minimum_path_length":
        return f"Path length {act} m (needed ≥ {exp} m) — likely went straight instead of detouring."
    if t == "joint_positions_reached":
        return f"Joints did not reach the target ({assertion.get('detail')}; tolerance {exp} rad)."
    if t == "required_topic_messages":
        return f"Too few sensor messages ({act}, needed ≥ {exp}) — a topic may not be publishing."
    return f"Assertion {t!r} failed (actual {act}, expected {exp})."


def diagnose(result: dict, events: list[dict], control_at_failure: dict | None = None) -> dict:
    """Explain why a run failed. `control_at_failure` is the `/cmd_vel` sample nearest the
    collision (`{vx, wz}`), used to say whether the controller was still driving into it."""
    if result.get("passed"):
        return {"scenario": result.get("scenario"), "passed": True,
                "summary": "The run passed — nothing to diagnose."}

    metrics = result.get("metrics", {})
    failed = [a for a in result.get("assertions", []) if not a["passed"]]
    findings = list(dict.fromkeys(_finding(a, metrics, events) for a in failed))  # dedupe, keep order

    collision = next((e for e in events if e["type"] == "collision"), None)
    if collision and control_at_failure and abs(control_at_failure.get("vx", 0.0)) > 0.05:
        findings.append(
            f"At the moment of collision the controller was still commanding forward velocity "
            f"(vx={control_at_failure['vx']} m/s) — it did not slow down or turn away."
        )

    scenario = result.get("scenario")
    summary = (f"{scenario} failed: " + findings[0]) if findings else f"{scenario} failed."
    return {
        "scenario": scenario,
        "passed": False,
        "failed_assertions": [a["type"] for a in failed],
        "findings": findings,
        "summary": summary,
    }


def collision_time(events: list[dict]) -> float | None:
    e = next((e for e in events if e["type"] == "collision"), None)
    return e["timestamp"] if e else None
