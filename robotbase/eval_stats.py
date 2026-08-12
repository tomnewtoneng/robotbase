"""Pure statistics + report assembly for `robotbase eval` (no I/O — unit-tested).

Turns per-trial pass/fail + metrics into a statistically honest report: a binomial success-rate
with a Wilson 95% confidence interval, per-metric distributions, and a shareable markdown card.
The honesty guard: a CI is only emitted when the scenario is actually randomized."""
from __future__ import annotations


def wilson_ci(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion (correct for small n). Clamped [0,1]."""
    if n == 0:
        return (0.0, 0.0)
    p = passed / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, round(center - half, 4)), min(1.0, round(center + half, 4)))


def is_randomized(randomize) -> bool:
    """True iff the scenario's randomize block actually jitters something — otherwise all trials
    are identical and a confidence interval would be meaningless."""
    jp, jo = randomize.robot_pose, randomize.obstacles
    return any(v != 0 for v in (jp.x, jp.y, jp.yaw, jo.x, jo.y, jo.yaw))


def aggregate_metrics(metrics_list: list[dict]) -> dict:
    """Per numeric metric key, {mean, std, min, max, count} across the trials that reported it.
    Non-numeric values (dicts like topic_message_counts, bools) are skipped; std is None for n<2."""
    keys: set = set()
    for m in metrics_list:
        keys |= set(m)
    out: dict = {}
    for k in sorted(keys):
        vals = [m[k] for m in metrics_list if k in m]
        if not vals or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            continue
        n = len(vals)
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5 if n >= 2 else None
        out[k] = {"mean": round(mean, 4), "std": round(std, 4) if std is not None else None,
                  "min": min(vals), "max": max(vals), "count": n}
    return out
