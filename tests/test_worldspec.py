from robotbase.worldspec.schema import WorldSpec


def test_parse_world_yaml_fields():
    spec = WorldSpec.model_validate({
        "name": "warehouse", "ground": True, "light": "sun",
        "obstacles": [{"shape": "box", "size": [0.3, 0.3, 0.5], "at": [2, 0, 0.25]}],
        "walls": [{"from": [-3, -3], "to": [3, -3], "height": 0.5}],
        "goals": [{"name": "dock", "at": [4, 0], "radius": 0.3}],
        "include": ["conveyor.sdf"],
    })
    assert spec.name == "warehouse"
    assert spec.obstacles[0].at == [2, 0, 0.25]
    assert spec.walls[0].from_ == [-3, -3] and spec.walls[0].to == [3, -3]
    assert spec.goals[0].name == "dock"
    assert spec.include == ["conveyor.sdf"]
