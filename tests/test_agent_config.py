import json
import os
import sys

from robotbase import agent_config as ac


def test_interpreter_is_current_python():
    assert ac.interpreter() == sys.executable


def test_mcp_entry_shape(tmp_path):
    e = ac.mcp_server_entry(str(tmp_path))
    assert e["command"] == sys.executable
    assert e["args"] == ["-m", "robotbase.mcp_server"]
    assert e["env"]["ROBOTBASE_PROJECT_DIR"] == os.path.abspath(str(tmp_path))


def test_fix_mcp_interpreter_rewrites_bare_python3(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps({"mcpServers": {"robotbase": {
        "command": "python3", "args": ["-m", "robotbase.mcp_server"],
        "env": {"ROBOTBASE_PROJECT_DIR": "."}}}}))
    ac.fix_mcp_interpreter(str(tmp_path))
    got = json.loads(p.read_text())["mcpServers"]["robotbase"]
    assert got["command"] == sys.executable
    assert got["env"]["ROBOTBASE_PROJECT_DIR"] == "."   # env preserved (portable default)


def test_fix_mcp_interpreter_absent_returns_none(tmp_path):
    assert ac.fix_mcp_interpreter(str(tmp_path)) is None


def test_write_project_mcp_json(tmp_path):
    path = ac.write_project_mcp_json(str(tmp_path))
    d = json.loads(open(path).read())
    assert d["mcpServers"]["robotbase"]["command"] == sys.executable


def test_codex_toml_snippet(tmp_path):
    s = ac.codex_toml_snippet(str(tmp_path))
    assert "[mcp_servers.robotbase]" in s and "-m" in s and sys.executable in s
