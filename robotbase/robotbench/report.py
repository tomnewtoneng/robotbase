"""Aggregate trial records into the with-vs-without comparison + the shareable markdown.
See docs/design/robotbench-validation.md."""
from __future__ import annotations

from robotbase.robotbench.records import BENCHMARK_VERSION, TrialRecord, false_confidence


def _agg(recs: list[TrialRecord]) -> dict:
    n = len(recs)
    if n == 0:
        return {"solved_rate": 0.0, "false_confidence_rate": 0.0, "mean_edits": 0.0,
                "mean_turns": 0.0, "mean_wall_clock_s": 0.0, "n": 0}
    return {
        "solved_rate": round(sum(r.solved for r in recs) / n, 3),
        "false_confidence_rate": round(sum(false_confidence(r) for r in recs) / n, 3),
        "mean_edits": round(sum(r.controller_edits for r in recs) / n, 2),
        "mean_turns": round(sum(r.agent_turns for r in recs) / n, 2),
        "mean_wall_clock_s": round(sum(r.wall_clock_s for r in recs) / n, 1),
        "n": n,
    }


def compare(records: list[TrialRecord]) -> dict:
    arms = sorted({r.arm for r in records})
    tasks = sorted({r.task_id for r in records})
    by_arm = {a: _agg([r for r in records if r.arm == a]) for a in arms}
    by_task_arm = {t: {a: _agg([r for r in records if r.task_id == t and r.arm == a])
                       for a in arms} for t in tasks}
    model = records[0].model if records else ""
    return {"benchmark": f"RobotBench v{BENCHMARK_VERSION}", "model": model,
            "by_arm": by_arm, "by_task_arm": by_task_arm}


def render_markdown(records: list[TrialRecord]) -> str:
    c = compare(records)
    arms = sorted(c["by_arm"])
    lines = [f"# RobotBench Results — {c['benchmark']}", "",
             f"Model: `{c['model']}`. The with-vs-without validation experiment "
             "(see `design/robotbench-validation.md`).", "",
             "## Headline — self-verification (false-confidence rate)", "",
             "Fraction of trials where the agent **claimed success but the judge disagreed** "
             "(lower is better):", "",
             "| arm | false-confidence | solved rate | mean edits | mean turns | n |",
             "|---|---|---|---|---|---|"]
    for a in arms:
        s = c["by_arm"][a]
        lines.append(f"| {a} | {s['false_confidence_rate']} | {s['solved_rate']} | "
                     f"{s['mean_edits']} | {s['mean_turns']} | {s['n']} |")
    lines += ["", "## Per-task (solved rate)", "",
              "| task | " + " | ".join(arms) + " |",
              "|---|" + "|".join("---" for _ in arms) + "|"]
    for t, per in c["by_task_arm"].items():
        lines.append(f"| {t} | " + " | ".join(str(per[a]["solved_rate"]) for a in arms) + " |")
    return "\n".join(lines) + "\n"
