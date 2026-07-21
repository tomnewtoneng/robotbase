#!/usr/bin/env bash
# Verify the robot is controllable: drive forward via /cmd_vel, confirm odom moves.
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

ros2 launch warehouse_bot_bringup simulation.launch.py > /tmp/launch.log 2>&1 &
LAUNCH_PID=$!

for i in $(seq 1 45); do
  ros2 topic list 2>/dev/null | grep -qx "/odom" && break
  sleep 1
done
sleep 3  # let the spawn settle

echo "=== odom x BEFORE ==="
timeout 8 ros2 topic echo /odom --once 2>&1 | grep -A3 "position:" | grep -E "^      x:" | head -1

echo "=== driving forward (0.3 m/s for ~3s) ==="
timeout 3 ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}" -r 10 > /dev/null 2>&1
sleep 1

echo "=== odom x AFTER ==="
timeout 8 ros2 topic echo /odom --once 2>&1 | grep -A3 "position:" | grep -E "^      x:" | head -1

kill "$LAUNCH_PID" 2>/dev/null || true
pkill -f "gz sim" 2>/dev/null || true
pkill -f parameter_bridge 2>/dev/null || true
