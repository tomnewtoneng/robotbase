# mobile-nav — control challenges

A differential-drive robot (LiDAR + odometry) with four scenarios of increasing difficulty.
The starter controller only drives forward, so:

| Scenario | Starter result | The task |
|---|---|---|
| `drive-forward` | ✅ passes | warm-up — the loop works |
| `stop-before-obstacle` | ❌ fails | stop before hitting the box (use `/scan`) |
| `reach-goal` | ❌ fails | drive to a target pose and stop (use `/odom`) |
| `turn-around` | ❌ fails | get to a goal past a wall without colliding |

## Run it

```bash
robotbase up
robotbase test stop-before-obstacle      # read the failed assertions
# edit src/mobile_nav/mobile_nav/controller.py, then:
robotbase test stop-before-obstacle      # iterate until exit 0
```

Or point a coding agent at this directory (it reads `.mcp.json` / `AGENTS.md`) and ask it to
make each scenario pass.
