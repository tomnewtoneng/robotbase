from __future__ import annotations
from robotbase.schema import AssertionSpec
from robotbase.results import Metrics, AssertionResult

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

    return AssertionResult(type=t, passed=False, detail=f"Unknown assertion type: {t}")
