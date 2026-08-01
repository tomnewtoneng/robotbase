"""The RobotBench live bring-up applies the seeded spawn pose (so per-seed robustness is real)."""
from robotbase.robotbench.cli_deps import _apply_spawn_pose


def test_apply_spawn_pose_issues_gz_set_pose_for_the_seeded_pose():
    calls = []
    sh = lambda cmd, timeout=60: calls.append(cmd) or ""
    _apply_spawn_pose(sh, (0.12, -0.2, 0.0))
    assert len(calls) == 1
    c = calls[0]
    assert "/set_pose" in c and 'name: "robot"' in c
    assert "x: 0.12" in c and "y: -0.2" in c
