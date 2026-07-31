# Robotbase — Strategy & Roadmap (CURRENT SOURCE OF TRUTH)

> **Read this first for product direction.** This is the most up-to-date strategic analysis
> (2026-07-27). It supersedes the top-level framing in `VISION.md` and `ROADMAP.md` (kept as
> supporting detail). If you are a coding agent picking up work on Robotbase, orient here, then
> use `IDEAS.md` for the ranked backlog.
>
> Primary sources: the adversarial product-vision analysis (`projects/Robotbase/Robotbase Product
> Vision.pdf` in the ToddyOS vault), the business/validation note
> (`projects/Robotbase/business-strategy-and-validation.md`), and the RobotBench experiment spec
> (`docs/design/robotbench-validation.md`).

## 1. The vision, refined

**Robotbase is the declarative language + compiler for robotics projects — "Terraform for
robots."** You describe a robot, its sensors, world, runtime, tests, and evals in YAML; Robotbase
compiles that into a valid, running, verifiable ROS 2 + Gazebo project — reproducibly, and
designed to port toward real hardware.

The **core strategic asset is the language + compiler**, not the templates, Docker, MCP server,
or (future) Studio — those are *surfaces around the core*. The defensible version has:

- a **canonical, backend-decoupled intermediate representation (IR)** — semantic Robot/Joint/
  Sensor/World concepts, with URDF/SDF/launch/etc. as *compiler targets*, not the source of truth;
- **validation ≥ generation** — structural *and physical* correctness (a compiler that generates
  invalid physics faster is worthless);
- **mandatory traceability/explainability** — every important compiler decision is inspectable
  (`explain`/`trace`, source maps in generated files);
- **tests + evaluations as first-class language concepts** — objective behavioural evidence;
- a **knowledge layer** so coding agents edit *source declarations*, compile, and verify before
  claiming success;
- **progressive disclosure** — simple common cases, explicit (portability-breaking) escape hatches;
- **one backend deep before many** (Gazebo production-quality; IR simulator-neutral but don't
  claim cross-sim behavioural parity);
- **best-effort import** (preserve unsupported native assets; no lossless promise);
- **open-core, no lock-in** (open schemas, deterministic output, native export).

**The one bar everything must clear:** does Robotbase express intent at a *substantially higher
level* than the generated formats, **and** does it make coding agents *measurably* better? If not,
the abstraction isn't justified.

## 2. Where the codebase actually stands (honest cross-reference)

**Surfaces: largely delivered. Compiler core: thin — this is where the moat is, and where we are
weakest.**

Aligned with the vision today:
- ✅ Declarative `robot.yaml`/`world.yaml` → URDF/SDF/launch (`robotspec/`, `worldspec/`,
  `generator._compile_specs`).
- ✅ **Higher-level intent, not a thin wrapper** — `base: differential-drive` expands to wheels/
  caster/plugins/bridges; `sensors: [{type: lidar}]` → link+sensor+bridge+derived world system;
  the compiler owns the gotchas (collision-lump naming, scoped contact topics, derived world
  systems). This genuinely clears the "not SDF-with-punctuation" bar.
- ✅ **Tests + evaluations as first-class** — scenarios/assertions/machine-readable results *and*
  domain-randomized robustness/suites/RobotBench (`evals.py`, `bench.py`, `robotbench/`).
- ✅ **RobotBench is exactly the benchmark the vision demands** — native vs Robotbase-assisted,
  measuring false-success-claims and behavioural pass rates. Running now.
- ✅ MCAP episode recording (objective evidence/data layer) — exceeds the doc.
- ✅ One backend deep (Gazebo) + a proven MuJoCo adapter seam; local-first; open (MIT);
  best-effort `--from-urdf` import.

Gaps vs the vision (in moat order):
- ❌ **The IR is a URDF buffer, not a semantic model.** `ir.py` `Fragment.links` hold
  *already-rendered URDF strings*; modules emit URDF directly. The doc's #1 technical
  kill-signal — *"the IR becomes tightly coupled to Gazebo/URDF"* — is already partly true of us.
  Adding an MJCF/Isaac backend today means re-authoring every module, not adding a backend.
- ❌ **No explainability/traceability** (`explain`/`trace`/source maps). `describe` shows facts,
  not "why this was generated / from which source line." Matters *more* now that we've added
  layers (yaml→IR→urdf→sdf→sim).
- ❌ **Validation is mostly runtime, not static/physical.** We validate the link *tree* and
  auto-compute inertia, but there are no static physical checks (mass ratios, COM, overlapping
  collision, disconnected-TF, joint-limit sanity) and no measured/inferred/default value
  provenance. "Silent physical assumptions are dangerous."
- 🟡 **Runtime not fully compiled** — we compile URDF+world but launch/controller/manifest stay
  *template-owned* (why an imported camera/depth sensor renders but isn't ROS-bridged).
- 🟡 **Knowledge layer** — `AGENTS.md` exists, but no packaged Claude Code skill / schema docs /
  failure-pattern tables. 🟡 **Units** are bare floats, not first-class (`0.55 m`).

## 3. The roadmap — highest leverage first

**Principle: validation-first, then depth on the compiler core — NOT more breadth.** The doc
explicitly warns breadth (more robots/sensors) is not the moat, and that the agent-native thesis
must be *tested, not assumed*.

### P0 — RobotBench (the gate). ✅ VALIDATED (v2 authoring, n=1, 2026-07-31)
Prove the core hypothesis before deepening the compiler: *do coding agents build reliable robotics
faster, with fewer false-success claims, WITH Robotbase than with native ROS?* **The clean v2 run
says yes** (`docs/ROBOTBENCH-RESULTS.md`; Sonnet, 4 authoring tasks × both arms × 1 trial, a fair
harness — identical prompt/rules/contract/controller/judge/caps, the only difference being
Robotbase's declarative compiler + tools vs. raw URDF/SDF/launch):

| arm | solved | capped | self-verify acc. | false-positive | mean turns |
|---|---|---|---|---|---|
| **with** | **0.75** | 0.0 | **0.75** | 0.25 | 33 |
| **without** | **0.0** | 0.5 | 0.0 | **1.0** | 40 |

WITH agents solved 3/4 tasks and correctly knew it; raw-ROS agents solved 0/4, ran out of turns
half the time, and every time they *did* conclude they were **wrong** (100% false-positive — claimed
success on a robot that doesn't do the task). That is the vision's headline failure — *"an agent can
write robot code; it can't tell if the robot works"* — measured. **Caveats:** n=1 (one trial/task,
so treat as directional not statistical); WITH is not perfect (one genuine false-confidence on the
hardest custom-URDF import task). **Gate passed → proceed with P1–P4.** (Cost: $6.47; a contaminated
earlier double-run was discarded and a concurrency lock added so it cannot recur.)

### Post-RobotBench-v2 review — what the build EMPIRICALLY taught the roadmap (2026-07-30)

Building + live-running the v2 authoring benchmark (Tasks 0–10) didn't just *test* the roadmap — it
turned several of its items from "believed important" into "measured to be the WITH arm's active
ingredients," and advanced three of them as byproducts. This reprioritizes what's next.

**n=1 signal (both arms fair, one task):** WITH — solved, self-verified correct, 2 edits, 22 turns,
clean finish. WITHOUT — solved, **but cut off at the turn cap before it could verify (claimed=False)**,
5 edits. Both built a working robot; only WITH did it fast *and knew it worked*. That "solved but
can't tell" on the raw arm is the vision's headline failure mode, observed live. (Full n=3 × 4 tasks
running now; n=1 is directional, not proof.)

**What the dogfooding + smoke proved about specific roadmap items:**
- **P5 (knowledge layer) is decisive, not optional.** With the old (missing) knowledge layer the WITH
  agent *failed a solvable task* (guessed the world schema, hit the turn cap). Adding a **general,
  schema-derived** authoring reference (`robotspec/schema_docs.authoring_reference()` — fields +
  archetype/sensor vocab from the real registries, zero task specifics, test-guarded against leakage)
  flipped it to a clean 2-edit self-verified solve. **The WITH advantage largely IS the knowledge
  layer + validation. Promote P5.**
- **P3 (validation ≥ generation) started + proven.** The schemas silently accepted a wrong obstacle
  key and defaulted the box onto the robot — a *silent physical failure* that cost the agent the task
  with no error. `extra="forbid"` (errors naming the bad field) is the first, high-value slice of P3;
  the deeper physical checks (inertia/mass-ratio/COM/overlap/disconnected-TF) are the natural next
  step and the bench will keep surfacing them.
- **P2 (compile the runtime) advanced.** The launch's ROS↔gz bridge list was template-hardcoded, so an
  authored camera rendered but wasn't bridged; it's now **compiled from the robot's sensors**
  (`urdf/bridges.json`). Spawn/world/robot_state_publisher are still template-owned — finishing that
  (and making the spawn model-name compiler-owned, not "= project name") closes real friction the
  smoke hit.
- **P1 (explainability) is the amplifier of the money metric.** The differentiator that showed up is
  *self-verifiability* ("did the robot actually do the task, and can the agent tell?"). `explain`/
  `trace`/source-maps directly amplify that edge — this is the highest-leverage *new* capability once
  P0 lands.

**Reprioritized next-steps (pending the n=3 result — the n=1 says it will validate):**
1. **Finish P0:** complete the n=3 run → publish `ROBOTBENCH-RESULTS.md` (the killer artifact:
   product + marketing + validation in one). This is also Tom's distribution trigger (PyPI/Docker).
2. **Lead with P5 + P3** (proven the WITH arm's active ingredients): package the knowledge layer as a
   first-class surface (expose the schema/vocabulary as a `robotbase` tool + a Claude skill, add
   failure-pattern tables, emit JSON Schema) and extend validation from "strict keys" to **static
   physical checks + value provenance**.
3. **Finish P2:** compile the launch + manifest (not just URDF/SDF/bridges) so the whole runtime is
   compiler-owned — removes the residual template coupling (spawn name, world name, RSP).
4. **Then P1 (explainability):** `explain`/`trace` + source maps — amplifies self-verifiability.
5. **Defer P4 (semantic IR refactor)** until the thesis is *firmly* validated and P1–P3 are in — it is
   the biggest, riskiest refactor; do it only when the payoff (MJCF/Isaac backends) is committed.

**Harness rigor to close before scaling any claim:** (a) wire the `-x/-y/-z` seeded spawn override in
`real_bringup_with` so per-seed robustness is real (currently degenerate — all seeds identical); (b)
the raised turn cap (50) is in for the n=3 so WITHOUT's `claimed_solved` isn't a cut-off artifact; (c)
report per-arm success-rate / iterations / wall-clock / **false-confidence** (claimed-but-unsolved),
the metric the vision demands.

### Dogfooding findings — authoring the RobotBench v2 references (2026-07-28)

Authored the 4 v2 reference robots+worlds through the compiler by hand (the product-first probe
before building the v2 harness). Results:

- ✅ **`diff-lidar-world`** and ✅ **`two-sensor`** compiled cleanly first try — robot+sensor+world
  + gz sensor-systems all correct. The declarative *core* (robot.yaml → URDF/SDF) is genuinely good.
- 🔧 **FIXED — import + add-sensor injected no sensor XML.** `compile_robot`'s custom-import branch
  produced a `/scan` bridge but no gz `<sensor>` in the URDF → silent `/scan`. Now the sensor
  link/joint/gazebo XML is spliced into the imported URDF (body still verbatim). Commit + regression
  test landed.
- 🔧 **FIXED — `base:` + `parts:` silently dropped the base.** The natural way to add a mast
  (`base: differential-drive` + a mast part) errored with a confusing `missing base_link`. Now
  `base:` composes as the first part. Commit + regression test landed.
- ✅ **FIXED — the authoring loop is now closed** (commit ff11de9). Was: `robot.yaml`/`world.yaml`
  compiled to URDF/SDF **only at `create` time**; `build`/`up` never recompiled, so an agent that
  authored/edited a spec and ran `robotbase up` got **no effect**. Now `build`/`up` call
  `generator.recompile_project` before colcon. Custom imports keep the pristine URDF separate
  (`.imported.urdf`) and compile into the runnable `.urdf.xacro` so re-injection is idempotent;
  imported-URDF sensors are recognised by a scan (wire only) vs author-added sensors (inject XML).
  `runtime.build` now surfaces real errors instead of an empty list. **Verified live: import a
  sensorless URDF, add a lidar, `robotbase up` → `/scan` publishes in Gazebo.** 151 tests.

**Verdict:** the compiler *core* is strong and the compile *loop* is now closed — an agent can author
or edit a spec and `robotbase up` reflects it. **The v2 harness is now unblocked** and worth building:
resume the plan at `docs/superpowers/plans/2026-07-27-robotbench-suite-v2.md` (Task 0 spike first).

### v2 harness — Task 9 (reference calibration + dogfooding) ✅ COMPLETE (2026-07-30)

Offline harness complete (Tasks 0–8, pushed): v2 authoring task set, provided `stop_at_1m`
controller, per-arm scaffolds + env-only orientation, kind-aware authoring prompt, acceptance
registry + pure predicates, behavioral author judge, durable run manifest, real bring-up wiring.
Then ran the live dogfooding gate — **all 4 reference solutions now score `solved` through the real
`author_judge`** (real bring-up + ground-truth pose probe). What it took:

- ✅ **Full live pipeline proven.** Real project → `robotbase up` (recompiles) + `launch` → run the
  *actual* provided controller → read Gazebo ground-truth pose → predicate → teardown. The robot
  reliably stops **1.37 m (centre-to-centre) from a 0.5 m box**.
- 🔧 **Calibrated the acceptance band to reality.** Synthetic band (centre-distance ∈ [0.8,1.2]) was
  wrong for where a real 1 m-from-face stop lands; retuned to **[1.1, 1.7]** (below ≈1.1 ≈ nearly
  hit; above ≈1.7 ≈ stopped too early / never moved — a non-mover sits at the ~2 m spawn).
- 🔧 **FIXED (compiler) — authored camera rendered but not ROS-bridged.** The two-sensor task failed
  because the launch's `parameter_bridge` list was hardcoded in the template (default diff-drive
  sensors), so an authored camera published gz `/image` but never reached ROS. Now the bridge list
  is **compiled from the robot's sensors** (`urdf/bridges.json`) and the launch builds its bridge
  from that — any authored sensor is bridged. This is the P2 "compile the runtime" gap, closed for
  bridges. Regression test landed. (3rd real bug the dogfooding gate has surfaced + fixed.)
- 🔧 **Redesigned the mast task to be physically coherent.** It previously asked the robot to drive
  *past* a solid 0.2 m barrier its mast-high LiDAR couldn't see — but a 0.2 m barrier physically
  blocks the ~0.2 m chassis regardless of sensor height. The mast's real discriminator is the
  multi-link, non-base sensor mount, so it's now a stop-before-box check against a single 0.6 m box
  a 0.5 m mast LiDAR sensibly sees.
- 🔧 **WITH scaffold is now a real `robotbase up`-able project named `robot`** (Gazebo spawn `-name`
  = project name, per the interface contract), with specs reset to authoring stubs for parity with
  the empty WITHOUT workspace. Added `robotbase/__main__.py` so bring-up invokes the CLI
  PATH-independently.
- 📌 **Committed the live gate:** `tests/test_reference_solutions_live.py` (skipped unless
  `ROBOTBENCH_LIVE=1`) parametrizes all 4 references → each must be `solved` by the real judge.

**Known limitation (deferred):** `real_bringup_with` still spawns at the world default, so seeded
spawn-jitter isn't applied yet — per-seed robustness is degenerate (all seeds identical). Wire the
`-x/-y/-z` spawn override before robustness across seeds is meaningful.

**Next:** Task 10 — the n=1 pilot (WITH vs WITHOUT agents actually authoring), which spends API +
Docker; stop and report before the definitive n=3.

### v2 harness — Task 0 (ground-truth pose probe) spike ✅ VERIFIED (2026-07-28)

The authoring judge must score behaviour from Gazebo **ground truth**, not the robot's own sensors
(so a robot that mis-reports its own `/scan` can't fake a pass). Spike proved this is feasible via
`gz topic -e /world/<world>/dynamic_pose/info`, read through an injected `sh(cmd)` callable
(`robotbase/robotbench/gz_probe.py`): the top-level model entry carries the world x/y by name (gz
omits near-zero fields → parse as 0.0). Verified live against a fresh `robotbase create` diff-drive
project: drove `/cmd_vel` forward at 0.3 m/s and `sample_model_pose` returned a clean monotonic
trace — x 0 → +1.036 m over ~3.8 s, y ≈ 0 exactly as commanded. `cmd_vel_is_live` (interface
contract check) and the pure parsers are unit-tested (5 tests). The probe is arm-agnostic (same `sh`
seam works for the WITH `docker compose exec` and WITHOUT raw-launch envs). **Task 0 done; proceed
to Task 1 (v2 task set + benchmark version bump).**

### P1 — Explainability & traceability (`robotbase explain` / `trace` + source maps)
Highest-leverage *new* capability: the doc makes traceability mandatory, it's our own debugging
pain now that we've added layers, and it's a defensibility feature (Terraform-style inspectability).
`explain robot.drive` → which artifacts, why, derived properties, backend; source maps in generated
files. **Effort: medium. Moat: high.**

### P2 — Compile the full runtime (not just URDF/SDF)
Own the launch file, controller config, and manifest — compiled from the specs / a `runtime.yaml`,
not template-owned. Closes a real correctness gap (imported sensors not bridged) and matches the
doc's "compiler owns launch/controller/docker." **Effort: medium. Already a backlog item.**

### P3 — Static physical validation + value provenance
A real semantic-validation stage: inertia sanity, mass-ratio/COM checks, overlapping-collision and
disconnected-TF detection, joint-limit validation; and tag every value as measured / imported /
inferred / default / estimated. Moves validation from "launch the sim and see" to static.
"Validation ≥ generation." **Effort: medium-high. Moat: high.**

### P4 — Lift the IR to a semantic model (the big one)
Decouple the IR from URDF strings: typed Robot/RigidBody/Joint/Sensor/Actuator/Controller/World
concepts; URDF/SDF/launch become *pure backends* over the IR. This is the deepest moat (kills the
"IR coupled to Gazebo" signal; makes MJCF/Isaac real) **and** the biggest, riskiest refactor — so
do it **after** P1–P3 and only if the thesis validates. **Effort: high. Moat: highest.**

### P5 — Knowledge layer for agents
A packaged Claude Code skill + schema docs + failure-pattern tables (borrow the ground-truth check
scripts from the ROS2-skills projects — see the competitive scan in the vault note). Amplifies the
agent-native thesis. **Effort: medium.**

### Later (post-core)
MuJoCo as a *first-class* backend (unlocked by P4); Studio (§H — the GUI, a *client* of the core,
built only once the compiler+runtime are useful standalone); import depth; units as first-class;
opportunistic breadth (quadruped/grasping/multi-robot) — breadth is not the moat.

## 4. Kill criteria — watch for these (honest off-ramps)

Reconsider or narrow if: users only scaffold once then edit generated files; declarations get as
verbose as URDF/SDF; most real projects need backend overrides; **agents do NOT perform better with
Robotbase (RobotBench says no)**; the IR stays coupled to Gazebo; physical defaults routinely
create unstable sims; validation stays impossible without launching the sim; import becomes an
engineering sink; or the target users don't regularly start new robotics projects / setup pain
matters less than calibration + hardware integration.

## 5. Positioning discipline

External promise stays **precise and demonstrable** (the internal vision can be broad). Do **not**
yet claim: universal robotics support, full simulator independence, lossless import, production
hardware deployment, or "an OS for Physical AI." Do claim: *"Define your robot, world, runtime,
tests, and evals in YAML — Robotbase compiles and runs the complete ROS + Gazebo project,"* and
*"a safe, structured language for a coding agent to build and verify robots."*
