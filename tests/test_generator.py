import os

import pytest

from robotbase.generator import create_project


def _make_template(tmp_path):
    t = tmp_path / "template"
    (t / "src" / "warehouse_bot" / "warehouse_bot").mkdir(parents=True)
    (t / "src" / "warehouse_bot" / "package.xml").write_text("<name>warehouse_bot</name>")
    (t / "src" / "warehouse_bot" / "resource").mkdir()
    (t / "src" / "warehouse_bot" / "resource" / "warehouse_bot").write_text("")
    (t / "src" / "warehouse_bot" / "warehouse_bot" / "ctrl.py").write_text("# warehouse_bot node")
    (t / "robotbase.yaml").write_text(
        "project:\n  name: warehouse-bot\nrobot:\n  name: warehouse_bot\n"
        "launch:\n  package: warehouse_bot_bringup\n"
        "simulation:\n  world_name: warehouse\n"
    )
    (t / "scripts").mkdir()
    (t / "scripts" / "metrics_collector.py").write_text("# keep me")
    (t / "scripts" / "probe.sh").write_text("echo throwaway")
    (t / "build").mkdir()
    (t / "build" / "junk").write_text("x")
    return str(t)


def test_create_renames_and_replaces(tmp_path):
    template = _make_template(tmp_path)
    dest = create_project("obstacle-bot", str(tmp_path / "out"), template)

    assert dest.endswith("obstacle-bot")
    # package directories (including the nested one and the resource marker) renamed
    assert os.path.isdir(os.path.join(dest, "src", "obstacle_bot", "obstacle_bot"))
    assert os.path.isfile(os.path.join(dest, "src", "obstacle_bot", "resource", "obstacle_bot"))
    # file contents rewritten, no template identifier left behind
    pkg = open(os.path.join(dest, "src", "obstacle_bot", "package.xml")).read()
    assert "obstacle_bot" in pkg and "warehouse_bot" not in pkg
    manifest = open(os.path.join(dest, "robotbase.yaml")).read()
    assert "name: obstacle-bot" in manifest
    assert "obstacle_bot_bringup" in manifest
    # the bare world name "warehouse" is preserved (not part of the robot identifier)
    assert "world_name: warehouse" in manifest
    # build artifacts skipped, throwaway probe skipped, metrics_collector kept
    assert not os.path.exists(os.path.join(dest, "build"))
    assert not os.path.exists(os.path.join(dest, "scripts", "probe.sh"))
    assert os.path.isfile(os.path.join(dest, "scripts", "metrics_collector.py"))


def test_create_rejects_existing(tmp_path):
    template = _make_template(tmp_path)
    create_project("obstacle-bot", str(tmp_path / "out"), template)
    with pytest.raises(FileExistsError):
        create_project("obstacle-bot", str(tmp_path / "out"), template)
