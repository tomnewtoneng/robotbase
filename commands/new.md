---
description: Scaffold a new Robotbase project and build a robot that does what you describe (ROS 2 + Gazebo, proven by a passing scenario).
argument-hint: <what the robot should do, e.g. "navigate an S-shaped maze to the goal">
---

Use the **robotbase** skill. Build a robot for this goal:

**$ARGUMENTS**

Work the full loop from an empty session:

1. Make sure Docker is running. Use the `robotbase` CLI — `pip install robotbase-kit` (or a one-off
   `uvx --from robotbase-kit robotbase <cmd>`).
2. `robotbase create <name> --template <t>` — pick the template that fits the goal
   (`differential-drive` for a mobile base, `arm` for manipulation, `drone`, `camera-bot`), then `cd` in.
3. `robotbase describe` and `robotbase schema` for ground truth + the authoring format.
4. Author the world and scenario for the goal, and write the controller — editing only
   `robot.yaml` / `world.yaml` / `simulation/scenarios/*.yaml` / `src/*/*/controller.py`.
5. `robotbase up`, then `robotbase test <scenario>`; iterate with `robotbase diagnose` and
   `robotbase episode …` until it passes.
6. Report the final scenario metrics. **Do not claim success without a passing scenario** (exit 0,
   all assertions true).
