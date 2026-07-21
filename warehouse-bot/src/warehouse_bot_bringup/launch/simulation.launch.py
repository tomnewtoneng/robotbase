import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():
    desc_share = get_package_share_directory("warehouse_bot_description")
    world = os.path.join(desc_share, "worlds", "warehouse.sdf")
    urdf_xacro = os.path.join(desc_share, "urdf", "warehouse_bot.urdf.xacro")
    robot_desc = xacro.process_file(urdf_xacro).toxml()

    # Headless Gazebo server: -s server-only, -r run unpaused, software rendering.
    gz = ExecuteProcess(
        cmd=["gz", "sim", "-s", "-r", "--headless-rendering", world],
        output="screen",
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_desc}],
    )

    # Spawn the robot once the world is up.
    spawn = TimerAction(
        period=4.0,
        actions=[
            Node(
                package="ros_gz_sim",
                executable="create",
                output="screen",
                arguments=["-name", "warehouse_bot", "-string", robot_desc, "-z", "0.1"],
            )
        ],
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        output="screen",
        arguments=[
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
            "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model",
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
        ],
    )

    return LaunchDescription([gz, robot_state_publisher, bridge, spawn])
