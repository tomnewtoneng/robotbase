import json
import os
import sys
import tempfile

from robotbase.generator import create_project, template_dir


def test_created_project_mcp_json_uses_real_interpreter():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("mcpbot", tmp, template_dir("differential-drive"))
        cfg = json.load(open(os.path.join(dest, ".mcp.json")))
        srv = cfg["mcpServers"]["robotbase"]
        assert srv["command"] == sys.executable      # not bare "python3"
        assert srv["args"] == ["-m", "robotbase.mcp_server"]
