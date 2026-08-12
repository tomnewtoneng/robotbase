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


def eval_report(name: str, per_trial: list[dict], randomized: bool) -> dict:
    """Assemble one scenario's statistical report from its per-trial records. per_trial items are
    {index, seed, run_id, passed, metrics}. Emits a CI only when randomized (the honesty guard)."""
    n = len(per_trial)
    passed = sum(1 for t in per_trial if t["passed"])
    deterministic = not randomized
    return {
        "scenario": name,
        "n": n,
        "passed": passed,
        "success_rate": round(passed / n, 4) if n else 0.0,
        "randomized": randomized,
        "deterministic": deterministic,
        "ci95": None if deterministic else list(wilson_ci(passed, n)),
        "per_trial": [{"index": t["index"], "seed": t["seed"],
                       "run_id": t["run_id"], "passed": t["passed"]} for t in per_trial],
        "metrics": aggregate_metrics([t["metrics"] for t in per_trial]),
    }


def suite_eval_report(reports: list[dict]) -> dict:
    """Aggregate per-scenario eval reports into a suite report, sorted worst success-rate first."""
    n = len(reports)
    mean = round(sum(r["success_rate"] for r in reports) / n, 4) if n else 0.0
    return {"scenarios": n, "mean_success_rate": mean,
            "results": sorted(reports, key=lambda r: r["success_rate"])}


def _metrics_table(metrics: dict) -> str:
    if not metrics:
        return ""
    lines = ["", "## Metrics (across trials)", "", "| metric | mean | std | min | max |",
             "|---|---|---|---|---|"]
    for k, s in metrics.items():
        std = "—" if s["std"] is None else s["std"]
        lines.append(f"| {k} | {s['mean']} | {std} | {s['min']} | {s['max']} |")
    return "\n".join(lines)


def _single_card(report: dict) -> str:
    cfg = report.get("config", {})
    head = [f"# Robotbase eval — {report['scenario']}", "",
            f"- **Success rate:** {report['success_rate']:.0%}  ({report['passed']}/{report['n']})"]
    if report["deterministic"]:
        head.append("- _Deterministic scenario (no randomization) — effective n=1; "
                    "not a sampled rate, no confidence interval._")
    else:
        lo, hi = report["ci95"]
        head.append(f"- **95% CI (Wilson):** [{lo:.0%}, {hi:.0%}]")
    head.append(f"- **Trials:** {report['n']}   **Base seed:** {cfg.get('seed', 0)}   "
                f"**Eval ID:** {report.get('eval_id', '—')}")
    return "\n".join(head) + "\n" + _metrics_table(report["metrics"]) + "\n"


def _suite_card(report: dict) -> str:
    cfg = report.get("config", {})
    lines = ["# Robotbase eval — suite", "",
             f"- **Scenarios:** {report['scenarios']}   "
             f"**Mean success rate:** {report['mean_success_rate']:.0%}   "
             f"**Base seed:** {cfg.get('seed', 0)}", "",
             "| scenario | success rate | 95% CI | n |", "|---|---|---|---|"]
    for r in report["results"]:
        ci = "deterministic" if r["deterministic"] else f"[{r['ci95'][0]:.0%}, {r['ci95'][1]:.0%}]"
        lines.append(f"| {r['scenario']} | {r['success_rate']:.0%} | {ci} | {r['n']} |")
    return "\n".join(lines) + "\n"


def render_markdown(report: dict) -> str:
    """A paste-able benchmark card — suite if the report has `results`, else a single scenario."""
    return _suite_card(report) if "results" in report else _single_card(report)
