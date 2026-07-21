#!/usr/bin/env bash
# NOTE: no `set -u` — ROS setup.bash references unset vars (AMENT_TRACE_SETUP_FILES).
set -o pipefail
source /opt/ros/jazzy/setup.bash

# Headless Gazebo server only (-s), run the world unpaused (-r), server-side rendering.
gz sim -s -r --headless-rendering minimal.sdf &
GZ_PID=$!

# Give Gazebo time to load the world and start the sensor under slow software rendering.
sleep 10

echo "=== gz topics ==="
gz topic -l 2>/dev/null | sort || true

# Bridge the gz LiDAR topic to a ROS 2 /scan topic (quote the arg: [ is a glob char).
ros2 run ros_gz_bridge parameter_bridge \
  '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan' &
BRIDGE_PID=$!

sleep 3
echo "=== ros2 topics ==="
ros2 topic list 2>/dev/null | sort || true

echo "=== checking /scan ==="
python3 check_scan.py
RESULT=$?

kill "$BRIDGE_PID" "$GZ_PID" 2>/dev/null || true
exit $RESULT
