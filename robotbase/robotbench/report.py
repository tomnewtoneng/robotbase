"""Aggregate trial records into the with-vs-without comparison + the shareable markdown.
See docs/design/robotbench-validation.md.

Metric design note (learned from the first breadth pass): a run that hit a cap (turns/timeout/
edits/error) was cut off mid-task, so its `claimed_solved` is "I wasn't finished", NOT a
self-verification judgement. Counting a capped `solved=True/claimed=False` as a self-verification
error is an artifact. So **self-verification accuracy is computed only over runs where the agent
concluded on its own** (`stop_reason` not a cap), and the cap rate is reported separately as its
own (meaningful) signal — an agent that always caps out couldn't tell it was done.
"""
from __future__ import annotations

from robotbase.robotbench.records import BENCHMARK_VERSION, TrialRecord

# Stop reasons that mean the agent was cut off, not that it decided it was finished.
CAPPED_STOPS = {"turns_cap", "timeout", "max_edits", "error"}


def _concluded(r: TrialRecord) -> bool:
    return r.stop_reason not in CAPPED_STOPS


def _agg(recs: list[TrialRecord]) -> dict:
    n = len(recs)
    if n == 0:
        return {"solved_rate": 0.0, "capped_rate": 0.0, "mean_edits": 0.0, "mean_turns": 0.0,
                "mean_wall_clock_s": 0.0, "n": 0, "concluded_n": 0,
                "self_verification_accuracy": None, "false_positive_rate": None,
                "false_negative_rate": None}
    term = [r for r in recs if _concluded(r)]
    tn = len(term)
    # self-verification only over runs the agent actually concluded (see module note)
    correct = sum(1 for r in term if r.claimed_solved == r.solved)
    fp = sum(1 for r in term if r.claimed_solved and not r.solved)   # claimed but didn't solve
    fn = sum(1 for r in term if r.solved and not r.claimed_solved)   # solved but didn't claim
    return {
        "solved_rate": round(sum(r.solved for r in recs) / n, 3),
        "capped_rate": round(sum(not _concluded(r) for r in recs) / n, 3),
        "mean_edits": round(sum(r.controller_edits for r in recs) / n, 2),
        "mean_turns": round(sum(r.agent_turns for r in recs) / n, 2),
        "mean_wall_clock_s": round(sum(r.wall_clock_s for r in recs) / n, 1),
        "n": n,
        "concluded_n": tn,
        "self_verification_accuracy": round(correct / tn, 3) if tn else None,
        "false_positive_rate": round(fp / tn, 3) if tn else None,
        "false_negative_rate": round(fn / tn, 3) if tn else None,
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


def _fmt(v) -> str:
    return "-" if v is None else str(v)


def render_markdown(records: list[TrialRecord]) -> str:
    c = compare(records)
    arms = sorted(c["by_arm"])
    lines = [f"# RobotBench Results — {c['benchmark']}", "",
             f"Model: `{c['model']}`. The with-vs-without validation experiment "
             "(see `design/robotbench-validation.md`).", "",
             "## Headline", "",
             "**solved rate** (higher better) · **capped rate** = ran out of turns without "
             "concluding (lower better; an agent that always caps couldn't tell it was done) · "
             "**self-verify acc.** = of the runs the agent *concluded on its own*, fraction where "
             "its SOLVED/NOT_SOLVED claim matched the judge (higher better; capped runs excluded "
             "so 'not finished' isn't miscounted as 'mis-verified') · **fp/fn** = false "
             "positive (claimed but didn't solve) / false negative (solved but didn't claim), "
             "among concluded runs.", "",
             "| arm | solved | capped | self-verify acc. | fp | fn | mean turns | n (concluded) |",
             "|---|---|---|---|---|---|---|---|"]
    for a in arms:
        s = c["by_arm"][a]
        lines.append(
            f"| {a} | {s['solved_rate']} | {s['capped_rate']} | "
            f"{_fmt(s['self_verification_accuracy'])} | {_fmt(s['false_positive_rate'])} | "
            f"{_fmt(s['false_negative_rate'])} | {s['mean_turns']} | {s['n']} ({s['concluded_n']}) |")
    lines += ["", "## Per-task (solved rate)", "",
              "| task | " + " | ".join(arms) + " |",
              "|---|" + "|".join("---" for _ in arms) + "|"]
    for t, per in c["by_task_arm"].items():
        lines.append(f"| {t} | " + " | ".join(str(per[a]["solved_rate"]) for a in arms) + " |")
    return "\n".join(lines) + "\n"
