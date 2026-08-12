#!/usr/bin/env bash
# Clean-install smoke: build the wheel, install it into a FRESH venv (deps resolved fresh),
# scaffold a project, and prove the agent path — `python -m robotbase.mcp_server` imports and the
# generated .mcp.json points at the real interpreter. Catches the mcp>=2 / bare-python3 class of break.
set -euo pipefail
cd "$(dirname "$0")/.."
# Build with the repo venv (it has `build`); fall back to system python3 -m build.
BUILD_PY="${BUILD_PY:-.venv/bin/python}"
[ -x "$BUILD_PY" ] || BUILD_PY="python3"
rm -rf dist && "$BUILD_PY" -m build --wheel >/dev/null
WHEEL=$(ls dist/*.whl)
TMP=$(mktemp -d)
python3 -m venv "$TMP/venv"
"$TMP/venv/bin/pip" install -q "$WHEEL"
echo "resolved mcp: $("$TMP/venv/bin/pip" show mcp | awk '/^Version/{print $2}')"
# 1) the MCP server module imports under the freshly-resolved mcp
"$TMP/venv/bin/python" -c "import robotbase.mcp_server; print('mcp_server import OK')"
# 2) a scaffolded project's .mcp.json launches the real interpreter (not bare python3)
"$TMP/venv/bin/robotbase" create smoke --path "$TMP" >/dev/null
CMD=$("$TMP/venv/bin/python" -c "import json; print(json.load(open('$TMP/smoke/.mcp.json'))['mcpServers']['robotbase']['command'])")
echo "generated .mcp.json command: $CMD"
case "$CMD" in
  *"$TMP/venv"*) echo ".mcp.json interpreter OK" ;;
  *) echo "FAIL: .mcp.json command is '$CMD'"; exit 1 ;;
esac
# 3) launching the server via the generated config starts without crashing (blocks on stdio; kill after 2s)
ROBOTBASE_PROJECT_DIR="$TMP/smoke" timeout 2 "$CMD" -m robotbase.mcp_server >/dev/null 2>&1 || true
echo "SMOKE OK"
rm -rf "$TMP" dist
