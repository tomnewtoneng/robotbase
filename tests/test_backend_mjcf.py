"""Task 13 — the MJCF backend proves the semantic IR is backend-neutral: a second backend renders
the SAME RobotModel that the URDF backend does, as an additive file."""
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.compile import compile_model
from robotbase.robotspec.backends.mjcf import render_mjcf


def _diff_drive():
    return compile_model(RobotSpec.model_validate(
        {"name": "robot", "base": "differential-drive", "sensors": [{"type": "lidar"}]}))


def test_mjcf_has_a_body_per_rigid_body():
    mj = render_mjcf(_diff_drive())
    assert "<mujoco" in mj and "</mujoco>" in mj
    assert mj.count("<body") >= 3            # base + two wheels, at least


def test_mjcf_reads_typed_geometry_and_joints_from_the_same_model():
    mj = render_mjcf(_diff_drive())
    assert '<body name="base_link"' in mj
    assert '<geom type="box"' in mj                       # base_link box, read from typed geometry
    assert '<geom type="cylinder"' in mj                  # wheels
    assert '<joint name="left_wheel_joint" type="hinge"' in mj   # continuous -> hinge


def test_mjcf_arm_renders_revolute_joints_as_hinges():
    model = compile_model(RobotSpec.model_validate({"name": "arm", "base": "arm"}))
    mj = render_mjcf(model)
    assert mj.count('type="hinge"') == 2                  # shoulder + elbow (fixed joints fold in)
