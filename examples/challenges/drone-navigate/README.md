# drone-navigate — 3-D navigation challenge

A quadrotor with odometry. The `reach-position` scenario asks it to fly to (2, 0, 2) and hover
within 0.4 m. The starter controller commands nothing, so the drone never leaves the ground.

## Run it

```bash
robotbase up
robotbase test reach-position            # read the failed assertion
# edit src/drone_navigate/drone_navigate/controller.py, then:
robotbase test reach-position            # iterate until exit 0
```
