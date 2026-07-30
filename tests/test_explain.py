"""Explainability: every compiled artifact is attributed to the spec declaration that made it, and
the explanation cannot drift from the compiler (the explained links must match the compiled URDF)."""
import re

from robotbase.robotspec.compile import compile_robot
from robotbase.robotspec.explain import explain_robot
from robotbase.robotspec.schema import RobotSpec


def _spec(d):
    return RobotSpec.model_validate({"name": "robot", **d})


def test_explain_attributes_each_declaration():
    ex = explain_robot(_spec({"base": "differential-drive", "sensors": [{"type": "lidar"}]}))
    by_source = {e["source"].split(":")[0].strip(): e for e in ex["produced"]}
    base = next(e for e in ex["produced"] if e["source"].startswith("base"))
    assert "base_link" in base["links"] and "/cmd_vel" in base["ros_topics"]
    lidar = next(e for e in ex["produced"] if "lidar" in e["source"])
    assert lidar["links"] == ["lidar_link"] and lidar["ros_topics"] == ["/scan"]
    assert lidar["gz_world_systems"] == ["gz-sim-sensors-system"]


def test_sensor_on_nonbase_link_is_attributed_to_that_link():
    ex = explain_robot(_spec({
        "base": "differential-drive",
        "parts": [{"links": [{"name": "mast", "shape": "cylinder", "size": [0.02, 0.5], "mass": 0.1}],
                   "joints": [{"name": "mast_joint", "parent": "base_link", "child": "mast",
                               "xyz": [0, 0, 0.3]}]}],
        "sensors": [{"type": "lidar", "on": "mast"}]}))
    lidar = next(e for e in ex["produced"] if "lidar" in e["source"])
    assert "on mast" in lidar["source"]


def test_authored_project_urdf_carries_a_source_map():
    import os
    import tempfile
    from robotbase.generator import create_project, template_dir
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("smbot", tmp, template_dir("differential-drive"))
        urdf = open(os.path.join(dest, "src", "smbot_description", "urdf", "smbot.urdf.xacro"),
                    encoding="utf-8").read()
        assert "Source map" in urdf and "base: differential-drive" in urdf


def test_provenance_distinguishes_authored_from_default():
    from robotbase.robotspec.explain import provenance
    spec = _spec({"base": "differential-drive", "body": {"size": [0.4, 0.3, 0.15]}})
    rows = {r["field"]: r["source"] for r in provenance(spec)}
    assert rows["body.size"] == "authored"          # the agent set it
    assert rows["body.mass"] == "default"           # left to the compiler default
    assert rows["link inertia"] == "inferred"       # computed
    # provenance rides along in the explain report
    assert "provenance" in explain_robot(spec)


def test_explained_links_match_compiled_urdf_no_drift():
    spec = _spec({"base": "differential-drive", "sensors": [{"type": "lidar"}, {"type": "camera"}]})
    explained = {name for e in explain_robot(spec)["produced"] for name in e["links"]}
    compiled = set(re.findall(r'<link name="([^"]+)"', compile_robot(spec).urdf))
    assert explained == compiled, f"explain drifted from compile: {explained ^ compiled}"
