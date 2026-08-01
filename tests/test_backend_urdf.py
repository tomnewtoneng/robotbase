import pytest

from robotbase.robotspec.merge import fixed_joint
from robotbase.robotspec.ir import ShapeSizeError, UnknownShape
from robotbase.robotspec.semantic import (
    RigidBody, Joint, Inertial, RobotModel, InvalidAssembly,
)
from robotbase.robotspec.backends.urdf import render_body, render_joint, render_urdf


# --- render_body: the computed path (plain shapes, inertia auto-computed) ---

def test_render_body_plain_box():
    out = render_body(RigidBody("base_link", ("box", [0.4, 0.2, 0.1]), mass=6.0))
    assert out.startswith('\n  <link name="base_link">')
    assert '<box size="0.4 0.2 0.1"/>' in out
    assert 'ixx="0.025"' in out          # 6*(0.2^2+0.1^2)/12 = 0.025
    for tok in ("<inertial>", "<collision>", "<visual>"):
        assert tok in out
    assert '<material name="grey">' in out
    assert out.endswith("\n  </link>")


def test_render_body_cylinder_and_sphere_geometry_and_inertia():
    cyl = render_body(RigidBody("mast", ("cylinder", [0.03, 0.5], ), mass=0.2))
    assert '<cylinder radius="0.03" length="0.5"/>' in cyl
    sph = render_body(RigidBody("ball", ("sphere", [0.05]), mass=0.1))
    assert '<sphere radius="0.05"/>' in sph
    assert 'ixx="0.0001"' in sph          # 2/5 * 0.1 * 0.05^2 = 0.0001


def test_render_body_honours_material_and_rgba():
    out = render_body(RigidBody("b", ("box", [1, 1, 1]), mass=2.0, material="body", rgba="0.2 0.2 0.25 1"))
    assert '<material name="body"><color rgba="0.2 0.2 0.25 1"/></material>' in out


def test_render_body_none_geometry_is_a_frame_link():
    assert render_body(RigidBody("base_footprint")) == '\n  <link name="base_footprint"/>'


def test_render_body_validates_geometry_via_the_semantic_path():
    with pytest.raises(ShapeSizeError):
        render_body(RigidBody("chassis", ("box", [1, 2])))
    with pytest.raises(UnknownShape):
        render_body(RigidBody("chassis", ("wedge", [1, 2, 3])))


def test_render_body_raw_xml_is_passed_through_verbatim():
    raw = '\n  <link name="weird"><custom/></link>'
    assert render_body(RigidBody("weird", raw_xml=raw)) == raw


# --- render_joint ---

def test_render_joint_matches_legacy_fixed_joint():
    # fixed_joint is a Joint factory; rendering it gives the historical both-attrs origin
    j = fixed_joint("lidar_joint", "base_link", "lidar_link", xyz="0.1 0 0.2")
    assert render_joint(j) == (
        '\n  <joint name="lidar_joint" type="fixed"><parent link="base_link"/>'
        '<child link="lidar_link"/><origin xyz="0.1 0 0.2" rpy="0 0 0"/></joint>')


def test_render_joint_without_rpy_omits_it():
    j = Joint("base_joint", "fixed", "base_footprint", "base_link", xyz="0 0 0.125")
    assert render_joint(j) == (
        '\n  <joint name="base_joint" type="fixed"><parent link="base_footprint"/>'
        '<child link="base_link"/><origin xyz="0 0 0.125"/></joint>')


def test_render_joint_with_axis_and_limit():
    j = Joint("shoulder_joint", "revolute", "arm_base_link", "upper_arm",
              xyz="0 0 0.05", axis="0 1 0", limit=("-3.14", "3.14", "100", "3.0"))
    assert render_joint(j) == (
        '\n  <joint name="shoulder_joint" type="revolute"><parent link="arm_base_link"/>'
        '<child link="upper_arm"/><origin xyz="0 0 0.05"/><axis xyz="0 1 0"/>'
        '<limit lower="-3.14" upper="3.14" effort="100" velocity="3.0"/></joint>')


# --- enriched render_body (explicit inertia / origins / friction / visual-only) ---

def test_render_body_uses_explicit_inertia_and_origins():
    # the arm's upper_arm: hand-tuned inertia + an inertial/collision/visual origin offset
    b = RigidBody("upper_arm", ("cylinder", [0.035, 0.40]), mass=0.15,
                  inertia=Inertial(0.15, 0.002, 0.002, 0.0002),
                  inertial_origin='xyz="0 0 0.2"', collision_origin='xyz="0 0 0.2"',
                  visual_origin='xyz="0 0 0.2"', material="upper_arm_mat", rgba="0.2 0.5 0.8 1")
    assert render_body(b) == (
        '\n  <link name="upper_arm">'
        '\n    <inertial><origin xyz="0 0 0.2"/><mass value="0.15"/>'
        '<inertia ixx="0.002" ixy="0" ixz="0" iyy="0.002" iyz="0" izz="0.0002"/></inertial>'
        '\n    <collision><origin xyz="0 0 0.2"/><geometry><cylinder radius="0.035" length="0.4"/></geometry></collision>'
        '\n    <visual><origin xyz="0 0 0.2"/><geometry><cylinder radius="0.035" length="0.4"/></geometry>'
        '<material name="upper_arm_mat"><color rgba="0.2 0.5 0.8 1"/></material></visual>'
        '\n  </link>')


def test_render_body_friction_and_no_material():
    # the caster: an ODE friction surface on the collision and a bare visual (no material)
    b = RigidBody("caster", ("sphere", [0.05]), inertia=Inertial(0.1, 0.0001, 0.0001, 0.0001),
                  friction=(0.0, 0.0), material=None)
    assert render_body(b) == (
        '\n  <link name="caster">'
        '\n    <inertial><mass value="0.1"/><inertia ixx="0.0001" ixy="0" ixz="0" iyy="0.0001" iyz="0" izz="0.0001"/></inertial>'
        '\n    <collision><geometry><sphere radius="0.05"/></geometry>'
        '<surface><friction><ode><mu>0</mu><mu2>0</mu2></ode></friction></surface></collision>'
        '\n    <visual><geometry><sphere radius="0.05"/></geometry></visual>'
        '\n  </link>')


def test_render_body_visual_only_omits_collision():
    b = RigidBody("rotor_fl", ("cylinder", [0.05, 0.01]), inertia=Inertial(0.02, 1e-5, 1e-5, 1e-5),
                  has_collision=False, material="rotor_fl_m", rgba="0.9 0.2 0.2 1")
    out = render_body(b)
    assert "<collision>" not in out
    assert '<inertia ixx="1e-05" ixy="0" ixz="0" iyy="1e-05" iyz="0" izz="1e-05"/>' in out
    assert out.endswith(
        '\n    <visual><geometry><cylinder radius="0.05" length="0.01"/></geometry>'
        '<material name="rotor_fl_m"><color rgba="0.9 0.2 0.2 1"/></material></visual>'
        '\n  </link>')


# --- render_urdf assembly + tree validation ---

def test_render_urdf_assembles_header_bodies_joints_gazebo():
    model = RobotModel(
        name="robot", root="base_footprint",
        bodies=[RigidBody("base_footprint"), RigidBody("base_link", ("box", [0.3, 0.2, 0.1]), mass=5.0)],
        joints=[Joint("base_joint", "fixed", "base_footprint", "base_link", xyz="0 0 0.1")],
        gazebo=['\n  <gazebo><plugin filename="x" name="y"></plugin></gazebo>'])
    urdf = render_urdf(model)
    assert urdf.startswith('<?xml version="1.0"?>\n<!-- Generated by Robotbase')
    assert '<robot name="robot" xmlns:xacro="http://ros.org/wiki/xacro">' in urdf
    assert '\n  <link name="base_footprint"/>' in urdf
    assert '\n  <joint name="base_joint" type="fixed">' in urdf
    assert urdf.endswith('</plugin></gazebo>\n</robot>\n')


def test_render_urdf_validates_the_tree():
    dup = RobotModel(name="r", root="base", bodies=[RigidBody("base"), RigidBody("base")])
    with pytest.raises(InvalidAssembly):
        render_urdf(dup)
    orphan = RobotModel(name="r", root="base",
                        bodies=[RigidBody("base"), RigidBody("floating")], joints=[])
    with pytest.raises(InvalidAssembly):
        render_urdf(orphan)
