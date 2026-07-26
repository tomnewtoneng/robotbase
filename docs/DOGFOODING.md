# Robotbase Dogfooding Log

Findings from using the declarative compiler to build Robotbase itself. Each entry: what we
tried, what broke, what we did.

## 2026-07-26 — Task 8 (regenerate the differential-drive template from specs)

- **Finding:** `compile_world` did not emit a `<physics>` block or a `<render_engine>` for the
  sensors system, both present in the working hand-written `warehouse.sdf`. Without the physics
  block the sim runs at an untuned rate; without the render engine the rendering sensors don't
  produce data headless.
- **Fix:** `compile_world` now always emits `<physics>` (max_step_size 0.001, real_time_factor
  1.0) and `<render_engine>ogre2</render_engine>` on the Sensors system. (A configurable
  `physics:` field on `WorldSpec` is deferred — sensible defaults first.)
