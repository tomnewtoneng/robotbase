from robotbase.describe import describe
from robotbase.generator import create_project, template_dir


def _describe_created(name, template, dest):
    # describe a freshly-created project (real compiled output), not a committed template artifact
    return describe(create_project(name, dest, template_dir(template)))


def test_describe_differential_drive(tmp_path):
    d = _describe_created("dbot", "differential-drive", str(tmp_path))
    assert d["robot"]["template"] == "differential-drive"
    assert d["robot"]["fixed_base"] is False
    base = next(l for l in d["robot"]["links"] if l["name"] == "base_link")
    assert base["shape"] == "box" and base["size"][:2] == [0.35, 0.3]   # real body geometry
    # arena bounds come from the walls, not the (much larger) ground plane
    assert d["world"]["bounds"] == {"x": [-4.05, 4.05], "y": [-4.05, 4.05]}
    names = {s["name"] for s in d["scenarios"]}
    assert names == {"drive-forward"}   # minimal all-green scaffold; challenges live in examples/
    fwd = next(s for s in d["scenarios"] if s["name"] == "drive-forward")
    assert "robot_moved_minimum_distance" in fwd["assertions"]
    assert "diff-drive" in {c["kind"] for c in d["robot"]["controllers"]}   # control config is surfaced


def test_describe_arm(tmp_path):
    d = _describe_created("armbot", "arm", str(tmp_path))
    assert d["robot"]["fixed_base"] is True
    joints = {j["name"]: j for j in d["robot"]["joints"]}
    assert joints["shoulder_joint"]["type"] == "revolute"
    assert joints["shoulder_joint"]["limits"] == [-3.14, 3.14]
    assert d["ready_topics"] == ["/joint_states"]
    assert d["command_joints"]["shoulder"]["command_topic"] == "/shoulder_cmd"
    assert d["scenarios"][0]["name"] == "reach-configuration"
    # the compiled joint-position controllers + their tunable gains are surfaced as ground truth
    ctrl = {c["joint"]: c["params"] for c in d["robot"]["controllers"] if c["kind"] == "joint-position"}
    assert ctrl["shoulder_joint"]["p_gain"] == "80" and ctrl["elbow_joint"]["p_gain"] == "60"
