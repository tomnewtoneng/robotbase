import pytest
from robotbase.robotspec.ir import Bridge, Fragment, JointIR, LinkIR
from robotbase.robotspec.merge import InvalidAssembly, fixed_joint, merge_and_render


def _base_fragment():
    f = Fragment()
    f.links += [LinkIR("base_footprint", '\n  <link name="base_footprint"/>'),
                LinkIR("base_link", '\n  <link name="base_link"/>')]
    f.joints.append(fixed_joint("base_joint", "base_footprint", "base_link"))
    f.gazebo.append("\n  <gazebo><plugin filename='X' name='Y'/></gazebo>")
    f.bridges.append(Bridge("/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"))
    f.world_systems.append("gz-sim-sensors-system")
    f.ready_topics.append("/odom")
    f.control = {"velocity_topic": "/cmd_vel"}
    f.fixed_base = False
    return f


def _sensor_fragment():
    f = Fragment()
    f.links.append(LinkIR("lidar_link", '\n  <link name="lidar_link"/>'))
    f.joints.append(fixed_joint("lidar_joint", "base_link", "lidar_link", xyz="0.1 0 0.1"))
    f.gazebo.append("\n  <gazebo reference='lidar_link'><sensor type='gpu_lidar'/></gazebo>")
    f.world_systems.append("gz-sim-sensors-system")   # duplicate on purpose
    f.ready_topics.append("/scan")
    f.manifest_sensors["lidar"] = {"enabled": True, "topic": "/scan"}
    return f


def test_merge_renders_one_robot_and_dedups_systems():
    urdf, bridges, systems, manifest = merge_and_render(
        "warehouse_bot", "base_footprint", [_base_fragment(), _sensor_fragment()])
    assert 'name="warehouse_bot"' in urdf
    for tok in ("base_footprint", "base_link", "lidar_link", "gpu_lidar", "<plugin"):
        assert tok in urdf, tok
    assert systems == ["gz-sim-sensors-system"]            # deduped, order preserved
    assert manifest["ready_topics"] == ["/odom", "/scan"]  # unioned in fragment order
    assert manifest["fixed_base"] is False
    assert manifest["control"]["velocity_topic"] == "/cmd_vel"
    assert set(manifest["sensors"]) == {"lidar"}
    assert [b.arg for b in bridges] == ["/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"]


def test_missing_mount_target_raises():
    bad = Fragment(links=[LinkIR("cam", '\n  <link name="cam"/>')],
                   joints=[fixed_joint("j", "nonexistent", "cam")])
    with pytest.raises(InvalidAssembly, match="nonexistent"):
        merge_and_render("r", "base_footprint", [_base_fragment(), bad])


def test_orphan_link_raises():
    orphan = Fragment(links=[LinkIR("floating", '\n  <link name="floating"/>')])
    with pytest.raises(InvalidAssembly, match="not connected|orphan"):
        merge_and_render("r", "base_footprint", [_base_fragment(), orphan])


def test_duplicate_link_name_raises():
    dup = Fragment(links=[LinkIR("base_link", '\n  <link name="base_link"/>')])
    with pytest.raises(InvalidAssembly, match="duplicate"):
        merge_and_render("r", "base_footprint", [_base_fragment(), dup])
