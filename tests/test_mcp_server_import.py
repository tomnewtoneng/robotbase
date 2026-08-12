def test_mcp_server_module_imports():
    # the exact top-level import (`from mcp.server.fastmcp import FastMCP`) that a fresh install
    # with mcp>=2 breaks. Passing here proves the resolved mcp exposes fastmcp.
    import importlib
    m = importlib.import_module("robotbase.mcp_server")
    assert hasattr(m, "mcp") and hasattr(m, "main")
