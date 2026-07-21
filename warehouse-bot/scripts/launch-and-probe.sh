#!/usr/bin/env bash
# Launch the sim headless, wait for topics, sample data, then tear down.
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

ros2 launch warehouse_bot_bringup simulation.launch.py > /tmp/launch.log 2>&1 &
LAUNCH_PID=$!

# Wait up to 45s for /scan to appear in the ROS graph.
for i in $(seq 1 45); do
  if ros2 topic list 2>/dev/null | grep -qx "/scan"; then break; fi
  sleep 1
done

echo "=== ros2 topics ==="
ros2 topic list | sort

echo "=== gz topics (scan/odom/cmd_vel) ==="
gz topic -l 2>/dev/null | grep -iE "scan|odom|cmd_vel|tf" | sort || true

echo "=== /scan (header + limits) ==="
timeout 12 ros2 topic echo /scan --once 2>&1 | grep -E "frame_id|angle_min|angle_max|range_min|range_max" | head

echo "=== /scan ranges (first line) ==="
timeout 12 ros2 topic echo /scan --once 2>&1 | grep -A1 "^ranges:" | head -2

echo "=== /odom (frames + pose/twist) ==="
timeout 12 ros2 topic echo /odom --once 2>&1 | grep -E "frame_id|child_frame_id|position|orientation|linear|angular|x:|y:|z:" | head -20

echo "=== /tf present? ==="
ros2 topic list | grep -qx "/tf" && echo "tf: yes" || echo "tf: no"

echo "=== launch.log errors ==="
grep -iE "error|exception|traceback|failed|no such|not found|unable" /tmp/launch.log | head -25 || echo "(no obvious errors)"

kill "$LAUNCH_PID" 2>/dev/null || true
pkill -f "gz sim" 2>/dev/null || true
pkill -f parameter_bridge 2>/dev/null || true
