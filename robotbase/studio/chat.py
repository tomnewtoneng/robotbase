"""ChatSession — the agent runtime behind Studio's chat panel. Reuses the proven Claude Agent SDK
config from robotbase.robotbench.real_agent: an agent with cwd=project, the robotbase MCP server,
and file tools. No web imports; the SDK is imported lazily and `query_fn` is injectable for tests."""
from __future__ import annotations

import os
import sys
from typing import Any, Callable


def _events_for(msg: Any) -> list[dict]:
    """Map one SDK message → UI events (duck-typed by class name so fakes work in tests)."""
    name = type(msg).__name__
    out: list[dict] = []
    if name in ("AssistantMessage", "UserMessage"):
        for b in getattr(msg, "content", None) or []:
            bn = type(b).__name__
            if bn == "TextBlock" and getattr(b, "text", None):
                out.append({"type": "assistant", "text": b.text})
            elif bn in ("ToolUseBlock", "ServerToolUseBlock"):
                out.append({"type": "tool", "name": getattr(b, "name", ""),
                            "input": getattr(b, "input", {}) or {}})
            elif bn in ("ToolResultBlock", "ServerToolResultBlock"):
                out.append({"type": "tool_result", "ok": not getattr(b, "is_error", False)})
    elif name == "ResultMessage":
        out.append({"type": "done", "turns": getattr(msg, "num_turns", None),
                    "_session": getattr(msg, "session_id", None)})
    return out


class ChatSession:
    def __init__(self, project_dir: str, model: str = "claude-sonnet-5",
                 query_fn: Callable | None = None) -> None:
        self.project_dir = project_dir
        self.model = model
        self._query_fn = query_fn      # (message, resume) -> async iterator of SDK messages
        self._resume: str | None = None
        self._busy = False

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "Set ANTHROPIC_API_KEY and restart Studio to enable chat."
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            return False, "Install the studio extra to enable chat:  pip install robotbase-kit[studio]"
        return True, ""

    def _options(self, resume: str | None):
        from claude_agent_sdk import ClaudeAgentOptions
        kw: dict = dict(
            model=self.model, cwd=self.project_dir,
            permission_mode="bypassPermissions", strict_mcp_config=True,
            tools=["Read", "Edit", "Write"],
            mcp_servers={"robotbase": {"command": sys.executable,
                                       "args": ["-m", "robotbase.mcp_server"],
                                       "env": {"ROBOTBASE_PROJECT_DIR": self.project_dir}}},
        )
        if resume:
            kw["resume"] = resume       # multi-turn continuity
        return ClaudeAgentOptions(**kw)

    def _default_query(self, message: str, resume: str | None):
        from claude_agent_sdk import query
        return query(prompt=message, options=self._options(resume))

    async def run(self, message: str):
        if self._busy:
            yield {"type": "busy"}
            return
        self._busy = True
        try:
            qf = self._query_fn or self._default_query
            async for msg in qf(message, self._resume):
                for ev in _events_for(msg):
                    sid = ev.pop("_session", None)      # internal — capture for resume, never send to UI
                    if sid:
                        self._resume = sid
                    yield ev
        except Exception as e:  # noqa: BLE001 — surface any agent failure to the UI
            yield {"type": "error", "message": str(e)}
        finally:
            self._busy = False
