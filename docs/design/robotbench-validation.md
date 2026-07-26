# RobotBench — the with-vs-without validation experiment (design)

Status: **approved** (2026-07-26). Builds out RobotBench (`robotbase/bench.py`,
`docs/ROBOTBENCH.md`) from a per-project scorecard into a **controlled experiment** that
measures whether Robotbase makes coding agents materially better at robotics — the thesis
Robotbase exists to prove, turned into reproducible numbers + shareable artefacts.

## The claim under test

> A declarative local ROS environment **plus structured agent tools** makes coding agents
> materially better at robotics development.

We test the tooling half rigorously by holding the running simulation **constant** across two
arms and varying only the Robotbase tooling layer. The result is a defensible statement:
*"given the same running sim, structured agent tools make an agent solve more tasks, in fewer
iterations, and — critically — know whether it actually succeeded."*

## The experiment

**Two arms, identical task, identical sim — only the tool layer differs:**

- **WITH** — the generated project + `AGENTS.md` + the **robotbase MCP tools**
  (`test`/`diagnose`/`episode`/`describe`) and its machine-readable results.
- **WITHOUT** — the *same* running Dockerized sim, but the agent has only a **bash tool**
  (`ros2 topic echo`, `gz`, `ros2 launch`, shell). No robotbase verbs, no structured results,
  no `AGENTS.md`.

**Parity (what keeps it honest, not a sabotage):** both arms get the *same neutral task
statement* — what behaviour to achieve, "only edit the controller", "do not claim success
until you have verified it." The WITHOUT arm additionally gets a **minimal ROS orientation** a
competent ROS developer would already have (how to launch the sim, the controller file path,
the list of topics) — so the baseline is *raw-but-competent ROS 2 workflow*, not "dropped in
blind." The measured delta is therefore the **structured tooling** (test/diagnose/episode/
describe + machine-readable results + MCP), not "knows how to start Gazebo."

**The judge is external to both agents.** When an agent stops (declares done, or hits a cap),
the *harness* — not the agent — runs the scenario under **domain randomization** (robotbase's
existing robustness eval, `evals.py`) and that is the verdict. Both arms are scored by the
identical gate, so the WITHOUT agent lacking `robotbase test` never biases the score.

> **Task-set hardening (Phase 2 prerequisite):** the randomized judge is only meaningful for
> tasks that carry a `randomize` block. Today only `stop-before-obstacle` ships one; the other
> three benchmark tasks are currently judged deterministically (a single pass). Adding a
> `randomize` block to all four benchmark scenarios is part of Phase 2, so "solved" means
> *robust*, not *lucky*, uniformly across the set.

### Metrics (per trial → aggregated per task × arm × model)

1. **Solved** — robustness == 1.0 on the harness judge (all randomized trials pass; not a lucky
   single pass). Partial robustness is also recorded.
2. **Iterations-to-solve** — `controller_edits` (writes to the controller file) and `agent_turns`
   (SDK turns) — comparable across arms.
3. **Wall-clock + tokens** — from the SDK (efficiency).
4. **Self-verification accuracy** *(headline)* — the agent's **claimed** outcome vs. the
   ground-truth judge. Recorded as `claimed_solved` vs `actually_solved`; aggregated to a
   **false-confidence rate** (claimed solved but didn't) per arm. Hypothesis: the WITHOUT arm
   falsely claims success far more often, because it cannot truly verify — "vibes over
   evidence." This is Robotbase's sharpest, most ownable result.

**Stop conditions** (recorded): agent declares done · `controller_edits` cap · wall-clock
timeout · `agent_turns` cap.

## Harness architecture

`robotbase/robotbench/` — a standalone, re-runnable package (separate from the existing
`bench.py` per-project scorecard, which it reuses):

- **`records.py`** — the versioned record schema (Pydantic): task id, arm, model, seed, the four
  metric groups, stop reason, `claimed_solved`, `actually_solved`, robustness, transcript path,
  benchmark + model + git versions.
- **`arms.py`** — the two arm definitions: the shared task-prompt builder, the WITHOUT orientation
  text, and each arm's exposed tool set (WITH → the robotbase MCP server; WITHOUT → one sandboxed
  bash tool scoped to the project dir).
- **`agent.py`** — the agent-loop runner. Preferred: the **Claude Agent SDK** (it natively
  connects MCP servers and exposes a bash tool); fallback: a manual Anthropic Messages-API
  tool-use loop. It drives one trial's agent to a stop condition and returns the transcript +
  the agent's final claim. A **`StubAgent`** (deterministic, no API) implements the same
  interface for offline pipeline tests.
- **`judge.py`** — the ground-truth judge: wraps `run_scenario` under domain randomization,
  returns robustness. Identical for both arms.
- **`runner.py`** — orchestrates one **trial** (fresh project via `create` → start sim → agent
  loop → stop → judge → write record + transcript) and a **run** (loop over task × arm × trials).
  Trials run **sequentially** (one sim at a time — the published port 8765 / container are
  singletons) with teardown + fresh project between trials.
- **`report.py`** — aggregates records into the **with-vs-without comparison table** and the
  leaderboard scorecard (extends `bench.py::scorecard` with the arm/model/iteration dimensions),
  and renders `docs/ROBOTBENCH-RESULTS.md` (the shareable "here is the proof" report).
- **CLI:** `robotbase robotbench run --task <id|all> --arm with|without|both --model <m>
  --trials N [--seed S]` and `robotbase robotbench report`.

## Reproducibility, cost & safety

- **Reproducible:** domain-randomization seeds, pinned model version, versioned task set
  (`BENCHMARK_VERSION`), and the git SHA are all recorded. Re-running as models improve yields a
  time-series / leaderboard.
- **Cost-bounded:** real Docker sims + real API calls. Caps (edits/turns/timeout) bound each
  trial; trials are sequential; the first real run is a single model. A dry-run/`--max-cost`
  guard and a printed estimate precede a full run.
- **Isolation:** each trial is a throwaway project under a scratch dir, torn down after (Docker
  bind-mount files are root-owned — cleanup via a busybox container, as in the dogfooding gates).

## Phasing

1. **Harness core + `StubAgent` (offline, no API/Docker for the unit layer).** records/arms/judge/
   runner/report wired end-to-end, driven by a deterministic stub agent (edits the controller to a
   known-good or known-bad solution) so generate→loop→judge→record→report is fully unit-tested.
   The judge and report are pure-logic testable; a single live smoke trial validates the
   Docker+generate path.
2. **Real Claude Agent-SDK integration + the first thesis run.** One capable model
   (**Claude Sonnet**), all 4 tasks, **both arms, 3 trials each = 24 solve-runs** → the first real
   with-vs-without numbers + transcripts + `ROBOTBENCH-RESULTS.md`. One model with/without is
   sufficient to *prove the thesis*.
3. **Leaderboard (later, optional).** Add models (Opus, others) → the "which agent is best at
   writing robot controllers" table. More API spend; deferred.

## Testing

- **Unit (offline):** record schema; the WITHOUT orientation/prompt parity; per-arm tool wiring;
  `judge` robustness mapping (stub scenario results → solved/robustness); `report` aggregation
  (records → comparison table + false-confidence rate); `StubAgent` drives a full trial with a
  faked sim (judge stubbed) proving the orchestration and record shape.
- **Integration (live, Phase 2):** one real trial per arm on `diff/stop-before-obstacle` with
  Sonnet, asserting a record is produced, the judge ran, and the transcript captured — before the
  full 24-run batch.

## Artefacts & how the numbers get used

- Per-trial JSON records + transcripts (the raw evidence).
- `docs/ROBOTBENCH-RESULTS.md` — the with-vs-without table + the false-confidence chart: the
  headline for the README, a launch/Show-HN post, and (later, if the horizon nears) a fundraising
  slide. This is the single artefact that is product proof, marketing, and validation at once.

## Principles

- **The judge is objective and shared.** Neither agent scores itself; the harness's randomized
  robustness gate is the sole verdict, identical across arms.
- **Vary one thing.** Same sim, same task, same caps — only the tool layer differs.
- **Evidence over vibes, measured.** Self-verification accuracy operationalises Robotbase's core
  value claim as a number.
- **Reproducible or it doesn't count.** Seeds, pinned versions, recorded params; re-runnable.
