"""RealAgent: drives the Claude Agent SDK (claude-agent-sdk) as the live coding agent for a
RobotBench trial. Conforms to the Task-4 `Agent` protocol (`agent.py`). The WITH arm points the
SDK at the robotbase MCP server (`python -m robotbase.mcp_server`, `ROBOTBASE_PROJECT_DIR` set to
the project); the WITHOUT arm gets a raw bash shell instead. All `claude_agent_sdk` imports are
lazy/local so Phase-1 modules keep importing without the `bench-agent` extra installed.
See docs/design/robotbench-validation.md."""
from __future__ import annotations

import asyncio
import dataclasses
import glob
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from robotbase.robotbench.agent import AgentResult, Caps
from robotbase.robotbench.apikey import ensure_api_key
from robotbase.robotbench.arms import arm_context

FINAL_PROMPT = (
    "Do you believe you solved the task? Reply with only the single word "
    "SOLVED or NOT_SOLVED."
)


# The v2 agent AUTHORS the robot/world (it must not touch the provided controller), so an "edit"
# is a change to the authoring surface: robot.yaml/world.yaml for WITH, the src/ package for
# WITHOUT. The provided stop_at_1m controller is excluded — editing it is forbidden.
_AUTHOR_EXCLUDE = "stop_at_1m.py"


def _authoring_files(project_dir: str, arm: str) -> list[str]:
    if arm == "with":
        return [os.path.join(project_dir, f) for f in ("robot.yaml", "world.yaml")]
    hits: list[str] = []
    for ext in ("*.urdf", "*.sdf", "*.xacro", "*.py", "*.world", "*.xml"):
        hits += glob.glob(os.path.join(project_dir, "src", "**", ext), recursive=True)
    return [h for h in hits if _AUTHOR_EXCLUDE not in h]


def _authoring_hash(project_dir: str, arm: str) -> str:
    h = hashlib.sha256()
    for p in sorted(_authoring_files(project_dir, arm)):
        if os.path.isfile(p):
            h.update(p.encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def _sum_tokens(usage: dict[str, Any] | None) -> int | None:
    if not usage:
        return None
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


def _serialize_message(msg: Any) -> dict:
    if dataclasses.is_dataclass(msg) and not isinstance(msg, type):
        try:
            return {"type": type(msg).__name__, **dataclasses.asdict(msg)}
        except TypeError:
            pass
    return {"type": type(msg).__name__, "repr": repr(msg)}


@dataclass
class RealAgent:
    """Live coding agent via the Claude Agent SDK. Satisfies `robotbase.robotbench.agent.Agent`."""

    model: str

    def run(self, project_dir: str, arm: str, task: dict, caps: Caps) -> AgentResult:
        ensure_api_key()
        return asyncio.run(self._run_async(project_dir, arm, task, caps))

    def _build_options(self, project_dir: str, arm: str, caps: Caps):
        from claude_agent_sdk import ClaudeAgentOptions

        common: dict[str, Any] = dict(
            model=self.model,
            cwd=project_dir,
            permission_mode="bypassPermissions",
            max_turns=caps.max_turns,
            strict_mcp_config=True,
        )
        if arm == "with":
            return ClaudeAgentOptions(
                **common,
                tools=["Read", "Edit", "Write"],
                mcp_servers={
                    "robotbase": {
                        "command": sys.executable,
                        "args": ["-m", "robotbase.mcp_server"],
                        "env": {"ROBOTBASE_PROJECT_DIR": project_dir},
                    },
                },
            )
        if arm == "without":
            return ClaudeAgentOptions(
                **common,
                tools=["Bash", "Read", "Edit", "Write"],
                mcp_servers={},
            )
        raise ValueError(f"unknown arm {arm!r}; expected 'with' or 'without'")

    async def _run_async(self, project_dir: str, arm: str, task: dict, caps: Caps) -> AgentResult:
        from claude_agent_sdk import AssistantMessage, ResultMessage, query

        ctx = arm_context(arm, project_dir, task)
        options = self._build_options(project_dir, arm, caps)

        start = time.monotonic()
        transcript: list[dict] = []
        edits = 0
        turn_estimate = 0
        final_turns: int | None = None
        token_estimate = 0
        final_tokens: int | None = None
        stop_reason = "unknown"
        session_id: str | None = None
        last_hash = _authoring_hash(project_dir, arm)

        agen = query(prompt=ctx["prompt"], options=options)
        try:
            async with asyncio.timeout(caps.timeout_s):
                async for msg in agen:
                    transcript.append(_serialize_message(msg))
                    if isinstance(msg, AssistantMessage):
                        turn_estimate += 1
                        if msg.session_id:
                            session_id = msg.session_id
                        t = _sum_tokens(msg.usage)
                        if t is not None:
                            token_estimate += t
                    elif isinstance(msg, ResultMessage):
                        session_id = msg.session_id
                        final_turns = msg.num_turns
                        final_tokens = _sum_tokens(msg.usage)
                        stop_reason = msg.stop_reason or msg.subtype or "unknown"

                    new_hash = _authoring_hash(project_dir, arm)
                    if new_hash != last_hash:
                        edits += 1
                        last_hash = new_hash
                    if edits >= caps.max_edits:
                        stop_reason = "max_edits"
                        break
        except TimeoutError:
            stop_reason = "timeout"
        except Exception as e:  # the SDK raises an error result on max-turns and other failures
            emsg = str(e)
            stop_reason = "turns_cap" if "maximum number of turns" in emsg.lower() else "error"
            transcript.append({"type": "error", "message": emsg[:500]})
        finally:
            await agen.aclose()

        wall = time.monotonic() - start
        turns = final_turns if final_turns is not None else turn_estimate
        tokens = final_tokens if final_tokens is not None else (token_estimate or None)

        claimed = False
        if session_id is not None:
            try:
                claimed, extra_tokens, final_msgs = await self._ask_solved(options, session_id)
                transcript.extend(final_msgs)
                if extra_tokens is not None:
                    tokens = (tokens or 0) + extra_tokens
            except Exception as e:  # best-effort: a capped/errored session may reject resume
                transcript.append({"type": "final_error", "message": str(e)[:300]})

        return AgentResult(
            claimed_solved=claimed,
            controller_edits=edits,
            agent_turns=turns,
            wall_clock_s=wall,
            tokens=tokens,
            stop_reason=stop_reason,
            transcript=json.dumps(transcript),
        )

    async def _ask_solved(self, options, session_id: str) -> tuple[bool, int | None, list[dict]]:
        from claude_agent_sdk import ResultMessage, query

        follow_up = dataclasses.replace(options, resume=session_id, max_turns=1)
        claimed = False
        tokens: int | None = None
        msgs: list[dict] = []
        agen = query(prompt=FINAL_PROMPT, options=follow_up)
        try:
            async for msg in agen:
                msgs.append(_serialize_message(msg))
                if isinstance(msg, ResultMessage):
                    tokens = _sum_tokens(msg.usage)
                    result_text = (msg.result or "").strip().upper()
                    claimed = result_text == "SOLVED"
        finally:
            await agen.aclose()
        return claimed, tokens, msgs
