"""The compiler should catch a robot spawning inside a solid object (wall/obstacle)."""
from robotbase.worldspec.schema import Wall, WorldSpec
from robotbase.worldspec.validate import validate_spawn


def _maze(spawn):
    # A horizontal divider through the origin (like the maze's wall_5): from (-1.5,0) to (4,0).
    return WorldSpec(name="maze", spawn=spawn,
                     walls=[Wall.model_validate({"from": [-1.5, 0], "to": [4, 0], "height": 1})])


def test_spawn_inside_wall_is_flagged():
    findings = validate_spawn(_maze([0.0, 0.0]))
    assert any(f.code == "spawn-inside-object" and f.severity == "error" for f in findings)
    assert "wall_0" in findings[0].message


def test_spawn_in_clear_corner_is_ok():
    assert validate_spawn(_maze([-3.5, -3.2])) == []


def test_spawn_ignores_non_collidable_goal_marker():
    spec = WorldSpec(name="w", spawn=[3.2, 3.2],
                     goals=[{"name": "marker", "at": [3.2, 3.2], "radius": 0.2}])
    assert validate_spawn(spec) == []   # a goal marker has no collision — not an obstacle


def test_zero_length_wall_rejected(tmp_path):
    # A degenerate wall (from == to) used to compile silently to a 0-length box; reject it clearly.
    import pytest
    from robotbase.worldspec.schema import WorldSpecError
    p = tmp_path / "world.yaml"
    p.write_text("version: 1\nname: w\nwalls:\n  - {from: [1, 1], to: [1, 1], height: 1}\n")
    with pytest.raises(WorldSpecError, match="zero length"):
        WorldSpec.from_yaml(str(p))
