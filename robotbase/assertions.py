from __future__ import annotations
from robotbase.schema import AssertionSpec
from robotbase.results import Metrics, AssertionResult

# The assertion vocabulary — the single source of truth for the authoring reference. Each entry is a
# one-line description naming the AssertionSpec field(s) it reads. A guard test asserts every type
# here is actually handled by evaluate(), so the docs can never drift from the checker.
ASSERTION_DOCS: dict[str, str] = {
    "no_collision": "no collision occurred (LiDAR-proximity heuristic)",
    "no_contact": "no contact occurred (ground-truth contact/bumper sensor) — prefer over no_collision",
    "minimum_obstacle_distance": "closest approach to any obstacle >= minimum_metres",
    "robot_stopped": "came to rest: |velocity| <= linear_velocity_tolerance / angular_velocity_tolerance",
    "required_topic_messages": "topic published >= minimum_count messages (needs topic + minimum_count)",
    "robot_moved_minimum_distance": "displacement from start >= minimum_distance_metres",
    "minimum_path_length": "total path length (integrated odometry) >= minimum_metres — proves a detour",
    "robot_reached_pose": "final pose within position_tolerance_metres of (target_x, target_y[, target_z])",
    "joint_positions_reached": "each joint within joint_tolerance of joint_targets {joint: radians}",
}


def evaluate(spec: AssertionSpec, metrics: Metrics) -> AssertionResult:
    t = spec.type
    if t == "no_collision":
        ok = metrics.collision_count == 0
        return AssertionResult(type=t, passed=ok, expected=0, actual=metrics.collision_count)

    if t == "no_contact":
        # Ground-truth collision check from the contact/bumper sensor (physics), as
        # opposed to no_collision's LiDAR-proximity heuristic.
        ok = metrics.contact_count == 0
        return AssertionResult(type=t, passed=ok, expected=0, actual=metrics.contact_count)

    if t == "minimum_obstacle_distance":
        actual = metrics.minimum_obstacle_distance_metres
        ok = actual is not None and actual >= (spec.minimum_metres or 0.0)
        return AssertionResult(type=t, passed=ok, expected=spec.minimum_metres, actual=actual)

    if t == "robot_stopped":
        lin_ok = abs(metrics.final_linear_velocity) <= (spec.linear_velocity_tolerance or 0.0)
        ang_ok = abs(metrics.final_angular_velocity) <= (spec.angular_velocity_tolerance or 0.0)
        return AssertionResult(type=t, passed=lin_ok and ang_ok,
                               expected=spec.linear_velocity_tolerance,
                               actual=metrics.final_linear_velocity)

    if t == "required_topic_messages":
        count = metrics.topic_message_counts.get(spec.topic or "", 0)
        ok = count >= (spec.minimum_count or 0)
        return AssertionResult(type=t, passed=ok, expected=spec.minimum_count, actual=count)

    if t == "robot_moved_minimum_distance":
        target = spec.minimum_distance_metres or 0.0
        ok = metrics.distance_travelled_metres >= target
        return AssertionResult(type=t, passed=ok, expected=target,
                               actual=metrics.distance_travelled_metres)

    if t == "minimum_path_length":
        # Total path travelled (integrated odometry) ≥ value — e.g. to prove the robot
        # took a detour around an obstacle rather than a straight shot.
        target = spec.minimum_metres or 0.0
        ok = metrics.path_length_metres >= target
        return AssertionResult(type=t, passed=ok, expected=target,
                               actual=round(metrics.path_length_metres, 3))

    if t == "robot_reached_pose":
        import math
        dx = metrics.final_x - (spec.target_x or 0.0)
        dy = metrics.final_y - (spec.target_y or 0.0)
        # target_z is optional — include it (3D distance) only for robots that fly.
        dz = (metrics.final_z - spec.target_z) if spec.target_z is not None else 0.0
        dist = math.hypot(math.hypot(dx, dy), dz)
        tol = spec.position_tolerance_metres or 0.0
        goal = (spec.target_x, spec.target_y) + ((spec.target_z,) if spec.target_z is not None else ())
        return AssertionResult(type=t, passed=dist <= tol, expected=tol, actual=round(dist, 3),
                               detail=f"distance to goal {goal}")

    if t == "joint_positions_reached":
        # Every named joint must be within tolerance of its target angle (radians).
        targets = spec.joint_targets or {}
        tol = spec.joint_tolerance or 0.0
        errors = {j: round(abs(metrics.joint_positions.get(j, 1e9) - tgt), 3)
                  for j, tgt in targets.items()}
        worst = max(errors.values(), default=0.0)
        detail = "per-joint error: " + ", ".join(f"{j}={e}" for j, e in errors.items())
        return AssertionResult(type=t, passed=worst <= tol, expected=tol, actual=round(worst, 3),
                               detail=detail)

    return AssertionResult(type=t, passed=False, detail=f"Unknown assertion type: {t}")
