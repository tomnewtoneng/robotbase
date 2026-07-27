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

### P0 — NOW: finish RobotBench (the gate). 🚧 in progress
Prove the core hypothesis before deepening the compiler: *do coding agents build reliable robotics
faster, with fewer false-success claims, WITH Robotbase than with native ROS?* The pilot already
hints yes (WITH solved in 1 edit / correct self-verification; WITHOUT made 0 edits and capped).
Finish the breadth run → the full run → publish `ROBOTBENCH-RESULTS.md`. **If it validates, do
P1–P4. If it doesn't, the kill-criteria (§4) are the honest off-ramp — weeks spent, not months.**

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
