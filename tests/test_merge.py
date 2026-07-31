import pytest
from robotbase.robotspec.ir import Bridge, Fragment
from robotbase.robotspec.semantic import RigidBody, InvalidAssembly
from robotbase.robotspec.merge import fixed_joint, build_model
from robotbase.robotspec.backends.urdf import render_urdf


def _base_fragment():
    f = Fragment()
    f.links += [RigidBody("base_footprint"), RigidBody("base_link")]
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
    f.links.append(RigidBody("lidar_link"))
    f.joints.append(fixed_joint("lidar_joint", "base_link", "lidar_link", xyz="0.1 0 0.1"))
    f.gazebo.append("\n  <gazebo reference='lidar_link'><sensor type='gpu_lidar'/></gazebo>")
    f.world_systems.append("gz-sim-sensors-system")   # duplicate on purpose
    f.ready_topics.append("/scan")
    f.manifest_sensors["lidar"] = {"enabled": True, "topic": "/scan"}
    return f


def test_build_model_merges_and_dedups_systems():
    model = build_model("warehouse_bot", "base_footprint", [_base_fragment(), _sensor_fragment()])
    urdf = render_urdf(model)
    assert 'name="warehouse_bot"' in urdf
    for tok in ("base_footprint", "base_link", "lidar_link", "gpu_lidar", "<plugin"):
        assert tok in urdf, tok
    assert model.world_systems == ["gz-sim-sensors-system"]            # deduped, order preserved
    assert model.ready_topics == ["/odom", "/scan"]                    # unioned in fragment order
    assert model.fixed_base is False
    assert model.control["velocity_topic"] == "/cmd_vel"
    assert set(model.manifest_sensors) == {"lidar"}
    assert [b.arg for b in model.bridges] == ["/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"]


def test_missing_mount_target_raises():
    bad = Fragment(links=[RigidBody("cam")], joints=[fixed_joint("j", "nonexistent", "cam")])
    with pytest.raises(InvalidAssembly, match="nonexistent"):
        render_urdf(build_model("r", "base_footprint", [_base_fragment(), bad]))


def test_orphan_link_raises():
    orphan = Fragment(links=[RigidBody("floating")])
    with pytest.raises(InvalidAssembly, match="not connected|orphan"):
        render_urdf(build_model("r", "base_footprint", [_base_fragment(), orphan]))


def test_duplicate_link_name_raises():
    dup = Fragment(links=[RigidBody("base_link")])
    with pytest.raises(InvalidAssembly, match="duplicate"):
        render_urdf(build_model("r", "base_footprint", [_base_fragment(), dup]))


def test_cycle_through_root_raises():
    f = Fragment()
    f.links += [RigidBody("a"), RigidBody("b")]
    f.joints.append(fixed_joint("ab", "a", "b"))   # b child of a
    f.joints.append(fixed_joint("ba", "b", "a"))   # a child of b -> ring through root a
    with pytest.raises(InvalidAssembly):
        render_urdf(build_model("r", "a", [f]))
