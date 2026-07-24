from __future__ import annotations
import os, uuid
from pydantic import BaseModel, model_validator

def new_run_id() -> str:
    return "run_" + uuid.uuid4().hex[:12]

class Metrics(BaseModel):
    collision_count: int = 0
    contact_count: int = 0
    minimum_obstacle_distance_metres: float | None = None
    distance_travelled_metres: float = 0.0
    final_linear_velocity: float = 0.0
    final_angular_velocity: float = 0.0
    topic_message_counts: dict[str, int] = {}

class AssertionResult(BaseModel):
    type: str
    passed: bool
    expected: float | int | None = None
    actual: float | int | None = None
    detail: str = ""

class Diagnostic(BaseModel):
    source: str
    level: str
    message: str

class ScenarioResult(BaseModel):
    run_id: str
    scenario: str
    passed: bool = False
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    metrics: Metrics
    assertions: list[AssertionResult] = []
    diagnostics: list[Diagnostic] = []

    @model_validator(mode="after")
    def _compute_passed(self) -> "ScenarioResult":
        object.__setattr__(self, "passed",
                           bool(self.assertions) and all(a.passed for a in self.assertions))
        return self

    def write(self, run_dir: str) -> str:
        os.makedirs(run_dir, exist_ok=True)
        path = os.path.join(run_dir, "result.json")
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))
        return path
