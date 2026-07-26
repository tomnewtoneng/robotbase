"""The Agent interface + a deterministic StubAgent (offline, no API) so the whole harness
pipeline is testable without the Claude Agent SDK. The RealAgent (Phase 2) implements the same
Protocol. See docs/design/robotbench-validation.md."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class AgentResult:
    claimed_solved: bool
    controller_edits: int
    agent_turns: int
    wall_clock_s: float
    tokens: int | None
    stop_reason: str
    transcript: str


@dataclass
class Caps:
    max_edits: int = 15
    timeout_s: int = 1200
    max_turns: int = 40


class Agent(Protocol):
    def run(self, project_dir: str, arm: str, task: dict, caps: Caps) -> AgentResult: ...


def _controller_path(project_dir: str) -> str:
    hits = glob.glob(os.path.join(project_dir, "src", "*", "*", "controller.py"))
    if not hits:
        raise FileNotFoundError(f"no controller.py under {project_dir}/src/*/*/")
    return hits[0]


@dataclass
class StubAgent:
    solution: str
    claim: bool
    edits: int = 1
    turns: int = 1
    stop_reason: str = "declared_done"

    def run(self, project_dir: str, arm: str, task: dict, caps: Caps) -> AgentResult:
        with open(_controller_path(project_dir), "w", encoding="utf-8") as fh:
            fh.write(self.solution)
        return AgentResult(claimed_solved=self.claim, controller_edits=self.edits,
                           agent_turns=self.turns, wall_clock_s=0.0, tokens=None,
                           stop_reason=self.stop_reason, transcript="<stub>")
