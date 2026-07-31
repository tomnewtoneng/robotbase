from robotbase.robotspec.ir import link_from_shape
from robotbase.robotspec.merge import fixed_joint
from robotbase.robotspec.semantic import RigidBody, Joint
from robotbase.robotspec.backends.urdf import render_body, render_joint


def test_render_body_matches_legacy_link_from_shape_box():
    legacy = link_from_shape("base_link", "box", [0.35, 0.30, 0.15], 5.0).xml
    body = RigidBody(name="base_link", geometry=("box", [0.35, 0.30, 0.15]), mass=5.0)
    assert render_body(body) == legacy


def test_render_body_matches_legacy_for_cylinder_and_sphere():
    for shape, size, mass in (("cylinder", [0.05, 0.1], 0.5), ("sphere", [0.05], 0.1)):
        legacy = link_from_shape("l", shape, size, mass).xml
        assert render_body(RigidBody("l", (shape, size), mass)) == legacy


def test_render_body_honours_material_and_rgba():
    legacy = link_from_shape("b", "box", [1, 1, 1], 2.0, material="body", rgba="0.2 0.2 0.25 1").xml
    body = RigidBody("b", ("box", [1, 1, 1]), 2.0, material="body", rgba="0.2 0.2 0.25 1")
    assert render_body(body) == legacy


def test_render_body_none_geometry_is_a_frame_link():
    assert render_body(RigidBody("base_footprint")) == '\n  <link name="base_footprint"/>'


def test_render_joint_matches_legacy_fixed_joint():
    legacy = fixed_joint("lidar_joint", "base_link", "lidar_link", xyz="0.1 0 0.2").xml
    j = Joint("lidar_joint", "fixed", "base_link", "lidar_link", xyz="0.1 0 0.2", rpy="0 0 0")
    assert render_joint(j) == legacy


def test_render_joint_without_rpy_omits_it():
    # module joints (e.g. base_joint) emit an xyz-only origin
    j = Joint("base_joint", "fixed", "base_footprint", "base_link", xyz="0 0 0.125")
    assert render_joint(j) == (
        '\n  <joint name="base_joint" type="fixed"><parent link="base_footprint"/>'
        '<child link="base_link"/><origin xyz="0 0 0.125"/></joint>')


def test_link_from_shape_delegates_to_the_backend():
    # after Task 4, ir.link_from_shape is a thin adapter over render_body — one renderer.
    for shape, size, mass in (("box", [0.3, 0.2, 0.1], 4.0), ("cylinder", [0.05, 0.1], 0.5), ("sphere", [0.05], 0.1)):
        assert link_from_shape("x", shape, size, mass).xml == render_body(RigidBody("x", (shape, size), mass))


def test_link_from_shape_still_validates_via_the_semantic_path():
    import pytest
    from robotbase.robotspec.ir import ShapeSizeError, UnknownShape
    with pytest.raises(ShapeSizeError):
        link_from_shape("chassis", "box", [1, 2], 1.0)
    with pytest.raises(UnknownShape):
        link_from_shape("chassis", "wedge", [1, 2, 3], 1.0)


def test_render_joint_with_axis_and_limit():
    j = Joint("shoulder_joint", "revolute", "arm_base_link", "upper_arm",
              xyz="0 0 0.05", axis="0 1 0", limit=("-3.14", "3.14", "100", "3.0"))
    assert render_joint(j) == (
        '\n  <joint name="shoulder_joint" type="revolute"><parent link="arm_base_link"/>'
        '<child link="upper_arm"/><origin xyz="0 0 0.05"/><axis xyz="0 1 0"/>'
        '<limit lower="-3.14" upper="3.14" effort="100" velocity="3.0"/></joint>')
