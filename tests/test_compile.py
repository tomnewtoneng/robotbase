

def test_base_and_parts_compose_not_replace():
    # Regression (dogfooding):  +  must compose — the base drivetrain plus the
    # extra mast part — not silently drop the base. The natural authoring form must work.
    from robotbase.robotspec.schema import RobotSpec
    from robotbase.robotspec.compile import compile_robot
    spec = RobotSpec.model_validate({
        "name": "robot", "base": "differential-drive",
        "parts": [{"links": [{"name": "mast", "shape": "cylinder", "size": [0.02, 0.5], "mass": 0.1}],
                   "joints": [{"name": "mast_joint", "parent": "base_link", "child": "mast",
                               "xyz": [0, 0, 0.3]}]}],
        "sensors": [{"type": "lidar", "on": "mast"}]})
    c = compile_robot(spec)
    assert "left_wheel" in c.urdf and "right_wheel" in c.urdf   # base kept
    assert "\"mast\"" in c.urdf or "name=\"mast\"" in c.urdf     # part composed
    assert "lidar_link" in c.urdf                                # sensor on the mast
    assert any("/cmd_vel" in b.arg for b in c.bridges)          # drivetrain wiring intact
