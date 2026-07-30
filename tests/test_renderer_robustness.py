"""The renderer must give a clean, actionable error on any bad authoring input — never an opaque
crash (a bare unpack/index/KeyError), which is what made the WITH agent flail. One case per
surface an authoring agent can realistically hit."""
import os
import tempfile

import pytest

from robotbase.robotspec.compile import InvalidRawPart, compile_robot
from robotbase.robotspec.schema import RobotSpec
from robotbase.worldspec.schema import WorldSpec


def _robot(d):
    return RobotSpec.model_validate({"name": "robot", **d})


def _world(d):
    return WorldSpec.model_validate(d)


# ---- schema-level: wrong-length sizes / coords are caught at load, naming the field -----------

@pytest.mark.parametrize("body,needle", [
    ({"shape": "box", "size": [1, 2]}, "box size"),
    ({"shape": "box", "size": [1, 2, 3, 4]}, "box size"),
    ({"shape": "cylinder", "size": [1, 2, 3]}, "cylinder size"),
    ({"shape": "sphere", "size": [1, 2]}, "sphere size"),
    ({"shape": "pyramid", "size": [1, 2, 3]}, "shape"),
])
def test_bad_body_size_is_clean_error(body, needle):
    with pytest.raises(Exception) as e:
        _robot({"base": "differential-drive", "body": body})
    assert needle in str(e.value)


def test_bad_sensor_mount_and_resolution_are_clean_errors():
    with pytest.raises(Exception) as e:
        _robot({"base": "differential-drive", "sensors": [{"type": "lidar", "mount": [1, 2]}]})
    assert "mount" in str(e.value)
    with pytest.raises(Exception) as e:
        _robot({"base": "differential-drive", "sensors": [{"type": "camera", "resolution": [640]}]})
    assert "resolution" in str(e.value)


@pytest.mark.parametrize("obs,needle", [
    ({"shape": "box", "size": [1, 2], "at": [0, 0, 0]}, "box size"),
    ({"shape": "cylinder", "size": [1], "at": [0, 0, 0]}, "cylinder size"),
    ({"shape": "box", "size": [1, 2, 3], "at": [0, 0]}, "at"),
])
def test_bad_obstacle_is_clean_error(obs, needle):
    with pytest.raises(Exception) as e:
        _world({"obstacles": [obs]})
    assert needle in str(e.value)


def test_bad_wall_and_goal_coords_are_clean_errors():
    with pytest.raises(Exception) as e:
        _world({"walls": [{"from": [0, 0, 0], "to": [1, 1]}]})
    assert "from" in str(e.value)
    with pytest.raises(Exception) as e:
        _world({"goals": [{"name": "g", "at": [1]}]})
    assert "at" in str(e.value)


# ---- renderer-level: the raw-part / custom-import escape hatches ------------------------------

def test_raw_part_missing_keys_are_clean_errors():
    with pytest.raises(InvalidRawPart) as e:
        compile_robot(_robot({"parts": [{"links": [{"shape": "box", "size": [1, 1, 1]}]}]}))
    assert "name" in str(e.value)
    with pytest.raises(InvalidRawPart) as e:
        compile_robot(_robot({"parts": [{"links": [{"name": "a", "shape": "box", "size": [1, 1, 1]}],
                                          "joints": [{"name": "j", "parent": "a"}]}]}))
    assert "child" in str(e.value)


def test_custom_import_missing_or_absent_urdf_is_clean_error():
    with pytest.raises(InvalidRawPart) as e:
        compile_robot(_robot({"parts": [{"use": "custom"}]}))
    assert "urdf" in str(e.value)
    with pytest.raises(InvalidRawPart) as e:
        compile_robot(_robot({"parts": [{"use": "custom", "urdf": "/no/such/file.urdf"}]}))
    assert "not found" in str(e.value)


# ---- a non-box body must not crash the geometry math -----------------------------------------

def test_cylinder_body_compiles_without_crash():
    c = compile_robot(_robot({"base": "differential-drive",
                              "body": {"shape": "cylinder", "size": [0.2, 0.15]},
                              "sensors": [{"type": "lidar"}]}))
    assert "<robot" in c.urdf and 'type="gpu_lidar"' in c.urdf
