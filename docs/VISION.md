# Robotbase — Vision

## What Robotbase is

Robotbase is the **batteries-included developer-experience layer for agent-driven
robotics**. It removes the ROS 2 + Gazebo setup headache and gives coding agents
structured, evidence-producing tools — over MCP and a CLI — to build, launch, inspect,
operate, and test a robotics project.

The guiding analogy is **"Supabase for ROS 2" in feeling, not infrastructure**: setup pain
vanishes, the primitives are good, it works instantly. Local-first and open-core. There is
no cloud dependency, no accounts, in the core.

Critically, Robotbase is the **layer on top of the simulator, not a simulator**. The
durable value is the *contract* — the project structure, the scenario format, the tool
interface — with the sim underneath as a swappable backend (Gazebo today; others later).

## The bet

> A declarative local ROS environment plus structured agent tools makes coding agents
> materially better at robotics development.

This is proven at MVP scale: a fresh agent, given no solution, taught itself obstacle
avoidance through the Robotbase tools (see `../PROOF.md`).

## Physical AI: the real position, and the trap

"Physical AI" is the industry's hottest narrative. There are two very different companies
hiding in it:

- **(a) Infrastructure / tooling** — the picks and shovels every robotics team needs
  regardless of whose robot or model they use. Horizontal, defensible.
- **(b) Embodied intelligence** — building the models and robots themselves. Where the
  buzz and the mega-rounds are.

**Robotbase is squarely (a) — and that is the stronger place to start.** The trap is the
narrative gravity of (b): positioning as a "Physical AI lab" before earning it dilutes
focus and invites a comparison we lose. Picks-and-shovels in a gold rush is the position
people envy in hindsight.

## The principle underneath everything

**Great human DX and great agent-operability are two sides of the same coin.** The
affordances that make a tool ergonomic for a human are the same ones that make it legible
to an agent: structured state over terminal-scraping, stable well-named interfaces,
opinionated defaults, fast deterministic feedback loops, evidence over vibes. Robotbase is
built so that "easy for humans" and "seamless for agents" are the same design act — with
one deliberate split: the **core stays structured and headless**, and visualization is a
pluggable, human-only layer, never a dependency.

## The wedge

The sharpened thesis, beyond "streamline robotics": Robotbase is the substrate for
**agent-operated robotics engineering**. Two things are the crown jewels:

1. **The MCP loop** — as coding agents improve, more robotics work gets done by agents, and
   agents need structured, testable environments to act in. Robotbase is that environment.
2. **The scenario runner + machine-readable results** — this is an **evaluation layer**. In
   the LLM era, evals/benchmarks became strategically enormous. Physical AI has almost no
   standardized behavioral eval infrastructure. "The CI/evals layer for robot behaviors" is
   a sharper story than "streamlining," and it compounds: every scenario run accumulates a
   benchmark library and behavioral data a competitor can't clone by copying the CLI.
3. **The episode record** — every run emits a standard **MCAP episode**: the full,
   scenario-labelled trace, not just a pass/fail flag. This is what makes runs *debuggable
   by agents* (query the trace behind a failure instead of guessing) and *replayable by
   humans* (MCAP is Foxglove-native). Because MCAP is the ecosystem standard — Foxglove,
   Rerun, and robot-data platforms all read it — our episodes are portable outward, and the
   accumulating labelled dataset is the un-clonable asset the eval/data layers are built on.
   See `design/mcap-recording.md`.

**Human DX and agent-operability, again:** the same recorded episode serves both — a human
scrubs it in Foxglove, an agent queries a bounded slice of it around a failure. One artifact,
two audiences, zero divergence.

## Business model — open-core

The local engine is open source (MIT): the wedge and the credibility play. Monetization
comes later and optionally, behind the same tool contract — never paywalling the local loop
or the format (that is what spreads the standard).

## The ecosystem (concentric layers)

Each layer only makes sense once the one inside it has traction. The OSS/paid line falls
between "spreads the standard" (free) and "collaboration / hosted compute / private data"
(paid).

- **Layer 0 — open standard (OSS, adoption engine):** the core CLI + runtime + MCP; the
  **scenario/manifest format as an open standard**; sim adapters (Gazebo → Isaac / MuJoCo /
  …); a template & robot library.
- **Layer 1 — hub (freemium, network effects):** a registry for templates, worlds, robot
  models, and **scenario/benchmark packs**; public free, private/org paid. *npm + Hugging
  Face for robotics.* The flywheel.
- **Layer 2 — cloud (paid, revenue engine):** run scenario suites on every commit/PR —
  behavioral regression testing. *Vercel/CircleCI for robot behaviors.* Plus hosted/GPU
  runners, team dashboards, RBAC/SSO.
- **Layer 3 — data & evals (paid, Physical-AI-native):** eval-as-a-service / benchmark
  leaderboards for policies and embodied foundation models; sim-to-data pipelines
  (scenarios → labeled training data). Built on the **MCAP episode record** (Layer 0) —
  every scenario run already leaves a standard, labelled trace, so this layer aggregates
  what the core produces rather than needing new instrumentation. It sits at the *inner-loop
  / pre-deployment* end of the robot-data lifecycle; **fleet-operations data platforms**
  (e.g. Alloy) own the *post-deployment* end. Same MCAP format, adjacent not overlapping —
  Robotbase episodes flow *into* those tools, which is a partnership surface, not a
  collision.
- **Layer 4 — agent (frontier):** a robotics-specialized coding agent living on the MCP
  tools — English → scenarios → implementation → verified behavior.
- **Layer 5 — community & education (OSS/content):** docs, an "Academy," build-in-public.
  Distribution is what kills dev-infra companies; an existing audience is a rare structural
  edge over a better-funded competitor.

## The two strategic anchors

Everything else is supporting cast:
1. **The hub / benchmark network** — moat = network effects + un-clonable accumulated eval
   data.
2. **Cloud CI** — no moat itself, but the clean recurring-revenue engine that funds the
   rest.

## How we win — sequencing

**Earn the narrative in order:** prove the agent-closes-the-loop thesis (done) → make it
genuinely usable and get developers standardizing on the scenario format → *then* the hub →
*then* cloud CI → evals/data. Each layer is a ghost town without the one beneath it. Lead
with the humble tool everyone uses, not the grand narrative; the tool earns the right to
claim the narrative later.

## Honest risks

- **NVIDIA Isaac Sim/Lab** is the gorilla in simulation — free, GPU-native, and NVIDIA is
  courting this exact space. The answer is to be *the layer over sims*: agent-native,
  headless-first, open, sim-agnostic — not to be a sim.
- **AWS RoboMaker was sunset (2025)** — cloud robotics infra has a graveyard. The value was
  never the hosted runner; it's the standard + community. Reinforces local-first + OSS.
- **TAM today is modest** — the set of teams doing serious ROS 2 work who'd pay is real but
  small; part of the bet is the market growing into the tool, so adoption/mindshare matters
  more than near-term revenue.

## Design principles (carried into the code)

- **Local first** — source and compute stay on the user's machine.
- **Opinionated over universal** — support one configuration extremely well, then expand.
- **Structured tools over terminal scraping** — machine-readable state always.
- **Evidence over confidence** — agents must test behavioral claims.
- **Headless first** — structured simulation state matters more than a GUI; visualization
  is optional and additive.
- **Runtime over scaffolding** — the generator attracts users; the build/inspect/test loop
  creates ongoing value.
- **Agent independent** — support multiple coding agents through stable CLI + MCP.
- **Cloud optional** — hosted layers may come later; no cloud dependency in the core.
