"""Static physical validation: clean robots pass; physically-suspect ones are flagged (not silently
compiled into a broken sim)."""
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.validate import summarize, validate_robot, validate_urdf


def test_compiled_diff_drive_robot_is_physically_clean():
    spec = RobotSpec.model_validate({"name": "robot", "base": "differential-drive",
                                     "sensors": [{"type": "lidar"}]})
    findings = validate_robot(spec)
    assert [f for f in findings if f.severity == "error"] == []
    assert summarize(findings)["ok"] is True


def test_non_positive_mass_is_an_error():
    urdf = ('<robot name="r"><link name="a"><inertial><mass value="0"/>'
            '<inertia ixx="1" iyy="1" izz="1"/></inertial></link></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "non-positive-mass" and x.severity == "error" for x in f)


def test_non_positive_inertia_is_an_error():
    urdf = ('<robot name="r"><link name="a"><inertial><mass value="1"/>'
            '<inertia ixx="1" iyy="0" izz="1"/></inertial></link></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "non-positive-inertia" for x in f)


def test_extreme_mass_ratio_is_a_warning():
    urdf = ('<robot name="r">'
            '<link name="heavy"><inertial><mass value="5000"/><inertia ixx="1" iyy="1" izz="1"/></inertial></link>'
            '<link name="light"><inertial><mass value="0.001"/><inertia ixx="1" iyy="1" izz="1"/></inertial></link>'
            '</robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "mass-ratio" and x.severity == "warning" for x in f)


def test_inverted_joint_limit_is_an_error():
    urdf = ('<robot name="r"><link name="a"/><link name="b"/>'
            '<joint name="j" type="revolute"><parent link="a"/><child link="b"/>'
            '<limit lower="1.0" upper="-1.0"/></joint></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "inverted-joint-limit" for x in f)


def test_massless_frame_links_are_not_flagged():
    # base_footprint / tip have no <inertial> — expected, must not error.
    urdf = '<robot name="r"><link name="base_footprint"/></robot>'
    assert validate_urdf(urdf) == []
