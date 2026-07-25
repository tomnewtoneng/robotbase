# Robotbase — Ideas backlog

Where Robotbase could go beyond the current core (CLI + MCP, three robot templates, the
scenario/assertion/metric vocabulary, MCAP episode recording/query/attachments, `describe`,
and a proven sim-agnostic adapter seam). Organized by theme; ranked at the bottom.

North star (from `VISION.md`): the crown jewels are **the MCP loop** and **the evals
layer**, and the moat is **accumulated behavioral eval data a competitor can't clone**.
Bias toward ideas that compound into that.

Status key: 🔲 not started · 🚧 in progress · ✅ done.

## A. Turn scenarios into *evals* (the moat)

A scenario today is a pass/fail test. The leap is making it a benchmark.

- ✅ **Scenario suites + aggregate report** — `robotbase test --all` → per-scenario
  robustness + `fully_passed` / `mean_robustness`. "CI for robot behaviors."
- ✅ **Behavioral regression tracking** — each `--all` run is diffed against the previous
  (stored in `.robotbase/last-suite.json`), flagging scenarios whose robustness dropped.
- ✅ **Domain randomization** — `robotbase test <name> --trials N [--seed S]` jitters the
  setup (obstacle/start pose, per the scenario's `randomize` block) and reports a
  **robustness** fraction. The biggest lever: a controller tuned to one config no longer
  looks solved. (`stop-before-obstacle` ships with a `randomize` block.)
- 🔲 **Flakiness / determinism check** — run ×N *without* perturbation, report variance.
- 🔲 **Friction / physics randomization** — vary friction/mass, not just poses.

## B. Deepen the agent experience (the DX crown jewel)

"Great human DX = great agent-operability."

- 🔲 **Auto-diagnosis of failures** — generate a structured natural-language *why* from the
  episode ("commanded constant vx=0.3, never reacted to /scan as range fell 0.5→0.08m"). An
  LLM-over-episode summarizer. The best demo; on-thesis.
- 🔲 **`robotbase doctor`** — diagnose Docker-down / WSL / port-8765 / engine issues with
  fixes. We hit every one of these as gotchas — pure adoption-friction removal.
- 🔲 **Natural-language scenario authoring** — `robotbase scenario new "circle the obstacle"`
  → drafts the YAML. Zero-barrier authoring.
- 🔲 **Richer inspection** — object-detection summaries over `/image`, replay/step-through.

## C. Own the standard (network effects)

- 🔲 **The hub** — a registry for scenario packs, robot templates, worlds. *npm + Hugging
  Face for robotics.* VISION Layer 1.
- 🔲 **RobotBench — benchmark *AI agents* at robot-controller writing** 🌶️ — formalize the
  dogfooding we've been doing into a fixed scenario set that coding agents attempt, scored on
  pass-rate/iterations. "SWE-bench for robotics agents." Timely, viral, ownable, and it
  *generates the eval data we want anyway.* We already have the harness and the proof.
- 🔲 **Shareable episode viewer** — a web page per episode ("watch my agent solve this").
- 🔲 **Format governance** — publish the scenario/manifest/result format as a spec + JSON
  Schema (SCENARIO-FORMAT.md is the start).

## D. Widen capability (the "can")

- 🔲 More robots: quadruped, **drone/quadrotor**, mobile manipulator, Ackermann car.
- 🔲 More sensors: depth camera, IMU, force/torque.
- 🔲 **Grasping / pick-and-place** — the arm's natural next task.
- 🔲 Multi-robot scenarios (coordination).

## E. Frontier bets (the Physical AI narrative)

- 🔲 **Scenarios as RL / gym environments** — MuJoCo is in-process now; exposing scenarios as
  gym-style training envs is a small step with enormous reach — connects Robotbase to the
  whole policy-learning world. "Train *and* eval in one format."
- 🔲 **VLA / foundation-model eval** — benchmark vision-language-action models on scenarios.
  Layer-3 Physical-AI-native; almost no standard infra exists.
- 🔲 **Sim-to-real bridge** — record real-robot episodes in the same MCAP format, run the same
  scenarios on hardware. The endgame.
- 🔲 **A robotics-specialized coding agent** (VISION Layer 4) living on the MCP tools.

## F. Distribution (the unlock — nothing matters without users)

- 🔲 PyPI package + public `robotbase-runtime` Docker image (needs owner accounts/tokens).
- 🔲 The demo video / GIF (the "agent teaches itself" moment; `PROOF.md` is the written form).
- 🔲 Build-in-public content on the "Build With Toddy" brand (a structural edge).
- 🔲 Integration guides (Claude Code / Cursor / any agent).

---

## Ranking (the order we're working through)

The picks that compound hardest — #1 and #3 both build the un-clonable eval dataset; #2
makes the loop delightful; #4 gets eyes on it:

1. **Domain randomization + scenario suites/regression** (A) — converts tests into evals, the
   whole moat, reachable now.
2. **Auto-diagnosis of failures** (B) — the killer agent-DX feature and best demo.
3. **RobotBench — the AI-agent robotics benchmark** (C) — we're uniquely positioned; doubles
   as the eval-data flywheel.
4. **Distribution** (F) — get it out of the vacuum; content is the structural edge.

Then breadth: widen capability (D) and the frontier bets (E).
