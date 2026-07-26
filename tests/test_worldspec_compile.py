import xml.dom.minidom

from robotbase.worldspec.schema import WorldSpec
from robotbase.worldspec.compile import compile_world


def _spec():
    return WorldSpec.model_validate({
        "name": "warehouse", "ground": True, "light": "sun",
        "obstacles": [{"shape": "box", "size": [0.3, 0.3, 0.5], "at": [2, 0, 0.25]}],
        "walls": [{"from": [-3, -3], "to": [3, -3], "height": 0.5}],
        "goals": [{"name": "dock", "at": [4, 0], "radius": 0.3}],
        "include": ["conveyor.sdf"],
    })


def test_world_sdf_has_base_and_robot_systems():
    sdf, manifest = compile_world(_spec(), robot_systems=["gz-sim-sensors-system"])
    assert '<world name="warehouse">' in sdf
    for sys_ in ("gz-sim-physics-system", "gz-sim-scene-broadcaster-system",
                 "gz-sim-user-commands-system", "gz-sim-sensors-system"):
        assert sys_ in sdf, sys_


def test_world_sdf_emits_scene_and_goal_manifest():
    sdf, manifest = compile_world(_spec())
    assert "<box><size>0.3 0.3 0.5</size></box>" in sdf     # obstacle
    assert "directional" in sdf                              # sun light
    assert "ground_plane" in sdf                             # ground
    assert "conveyor.sdf" in sdf                             # include
    assert manifest["goals"]["dock"]["radius"] == 0.3


def test_robot_systems_deduped():
    sdf, _ = compile_world(_spec(), robot_systems=["gz-sim-physics-system"])
    assert sdf.count('filename="gz-sim-physics-system"') == 1


def test_world_emits_physics_and_sensors_render_engine():
    sdf, _ = compile_world(WorldSpec(name="w"), robot_systems=["gz-sim-sensors-system"])
    assert "<physics" in sdf and "<max_step_size>0.001</max_step_size>" in sdf
    assert "<real_time_factor>1.0</real_time_factor>" in sdf
    # the sensors system must name a render engine for headless rendering
    assert "<render_engine>ogre2</render_engine>" in sdf


def test_special_characters_produce_wellformed_sdf():
    spec = WorldSpec.model_validate({
        "name": "A & B",
        "goals": [{"name": "dock & load", "at": [1, 1], "radius": 0.2}],
        "include": ["foo & bar.sdf"],
    })
    sdf, manifest = compile_world(spec)
    xml.dom.minidom.parseString(sdf)          # must not raise
    assert manifest["goals"]["dock & load"]["radius"] == 0.2   # raw key preserved
