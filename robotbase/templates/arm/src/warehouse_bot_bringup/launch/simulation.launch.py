import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import EqualsSubstitution, LaunchConfiguration
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

    # Spawn the arm once the world is up.
    spawn = TimerAction(
        period=4.0,
        actions=[
            Node(
                package="ros_gz_sim",
                executable="create",
                output="screen",
                arguments=["-name", "warehouse_bot", "-string", robot_desc],
            )
        ],
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        output="screen",
        arguments=[
            # Joint position commands (ROS -> gz): publish a target angle in radians.
            "/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double",
            "/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double",
            # Joint states (gz -> ROS): positions/velocities of the arm joints.
            "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model",
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
        ],
    )

    # Optional visualization: a Foxglove bridge, started only when gui:=foxglove.
    foxglove = Node(
        package="foxglove_bridge",
        executable="foxglove_bridge",
        output="screen",
        parameters=[{"port": 8765, "address": "0.0.0.0"}],
        condition=IfCondition(EqualsSubstitution(LaunchConfiguration("gui"), "foxglove")),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("gui", default_value="none"),
            gz,
            robot_state_publisher,
            bridge,
            spawn,
            foxglove,
        ]
    )
