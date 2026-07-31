"""Task 5 — the URDF backend renders each sensor's gz XML byte-identically to the old sensors.py.

The expected strings below are snapshots of the pre-refactor output; the golden guard
(tests/test_golden_output.py) additionally covers lidar/camera end-to-end in the templates.
"""
from robotbase.robotspec.semantic import Sensor
from robotbase.robotspec.backends.urdf import render_sensor


def test_lidar_renders_link_joint_and_gazebo():
    s = Sensor(kind="lidar", name="lidar", gz_type="gpu_lidar", reference="lidar_link",
               topic="/scan", mount_link="base_link", xyz="0.1 0 0.2", link_name="lidar_link")
    link, joint, gz = render_sensor(s)
    assert link == '\n  <link name="lidar_link"/>'
    assert joint == ('\n  <joint name="lidar_joint" type="fixed"><parent link="base_link"/>'
                     '<child link="lidar_link"/><origin xyz="0.1 0 0.2" rpy="0 0 0"/></joint>')
    assert gz == (
        '\n  <gazebo reference="lidar_link"><sensor name="lidar" type="gpu_lidar">'
        '<topic>scan</topic><gz_frame_id>lidar_link</gz_frame_id>'
        '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
        '<lidar><scan><horizontal><samples>180</samples><resolution>1</resolution>'
        '<min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>'
        '<range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range></lidar></sensor></gazebo>')


def test_imu_gazebo():
    s = Sensor(kind="imu", name="imu", gz_type="imu", reference="imu_link",
               topic="/imu", mount_link="base_link", xyz="0 0 0.075", link_name="imu_link")
    _, _, gz = render_sensor(s)
    assert gz == (
        '\n  <gazebo reference="imu_link"><sensor name="imu" type="imu">'
        '<topic>imu</topic><gz_frame_id>imu_link</gz_frame_id>'
        '<update_rate>50</update_rate><always_on>true</always_on></sensor></gazebo>')


def test_camera_gazebo_with_resolution():
    s = Sensor(kind="camera", name="camera", gz_type="camera", reference="camera_link",
               topic="/image", mount_link="base_link", xyz="0.15 0 0.075", link_name="camera_link",
               resolution=(320, 240))
    _, _, gz = render_sensor(s)
    assert gz == (
        '\n  <gazebo reference="camera_link"><sensor name="camera" type="camera">'
        '<topic>image</topic><gz_frame_id>camera_link</gz_frame_id>'
        '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
        '<camera><horizontal_fov>1.047</horizontal_fov>'
        '<image><width>320</width><height>240</height><format>R8G8B8</format></image>'
        '<clip><near>0.1</near><far>100</far></clip></camera></sensor></gazebo>')


def test_depth_gazebo_with_resolution():
    s = Sensor(kind="depth", name="depth", gz_type="depth_camera", reference="depth_link",
               topic="/depth", mount_link="base_link", xyz="0.15 0 0.075", link_name="depth_link",
               resolution=(320, 240))
    _, _, gz = render_sensor(s)
    assert gz == (
        '\n  <gazebo reference="depth_link"><sensor name="depth" type="depth_camera">'
        '<topic>depth</topic><gz_frame_id>depth_link</gz_frame_id>'
        '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
        '<camera><horizontal_fov>1.047</horizontal_fov>'
        '<image><width>320</width><height>240</height></image>'
        '<clip><near>0.1</near><far>10.0</far></clip></camera></sensor></gazebo>')


def test_contact_gazebo_has_no_link_or_joint():
    collision = "base_footprint_fixed_joint_lump__base_link_collision"
    s = Sensor(kind="contact", name="bumper", gz_type="contact", reference="base_footprint",
               topic="/bumper", collision=collision)
    link, joint, gz = render_sensor(s)
    assert link == "" and joint == ""
    assert gz == (
        '\n  <gazebo reference="base_footprint"><sensor name="bumper" type="contact">'
        '<always_on>true</always_on><update_rate>30</update_rate>'
        f'<contact><collision>{collision}</collision></contact></sensor></gazebo>')
