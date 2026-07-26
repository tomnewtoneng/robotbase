"""The versioned RobotBench trial record (see docs/design/robotbench-validation.md)."""
from __future__ import annotations

from pydantic import BaseModel

BENCHMARK_VERSION = 1


class TrialRecord(BaseModel):
    benchmark_version: int = BENCHMARK_VERSION
    task_id: str
    arm: str                         # "with" | "without"
    model: str
    trial: int
    seed: int
    solved: bool
    robustness: float
    claimed_solved: bool
    controller_edits: int
    agent_turns: int
    wall_clock_s: float
    tokens: int | None = None
    stop_reason: str                 # declared_done | edits_cap | timeout | turns_cap
    transcript_path: str | None = None
    git_sha: str | None = None


def false_confidence(rec: TrialRecord) -> bool:
    """The headline failure mode: the agent claimed success but the judge says it didn't."""
    return rec.claimed_solved and not rec.solved
