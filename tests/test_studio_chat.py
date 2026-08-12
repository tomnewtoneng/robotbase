import asyncio

from robotbase.studio.chat import ChatSession


# fake SDK message/block objects (duck-typed by class name + attrs)
class TextBlock:
    def __init__(self, text): self.text = text
class ToolUseBlock:
    def __init__(self, name, inp): self.name = name; self.input = inp
class AssistantMessage:
    def __init__(self, content): self.content = content
class ResultMessage:
    def __init__(self, session_id="s1", num_turns=2): self.session_id = session_id; self.num_turns = num_turns


def _fake_query(message, resume):
    async def gen():
        yield AssistantMessage([TextBlock("looking…"), ToolUseBlock("mcp__robotbase__test", {"scenario": "drive-forward"})])
        yield AssistantMessage([TextBlock("it passed ✓")])
        yield ResultMessage(session_id="sess-42", num_turns=3)
    return gen()


def _collect(session, message):
    async def go():
        return [e async for e in session.run(message)]
    return asyncio.run(go())


def test_run_emits_assistant_and_tool_events():
    s = ChatSession("/tmp/x", query_fn=_fake_query)
    ev = _collect(s, "hi")
    types = [e["type"] for e in ev]
    assert "assistant" in types and "tool" in types and types[-1] == "done"
    tool = next(e for e in ev if e["type"] == "tool")
    assert tool["name"] == "mcp__robotbase__test" and tool["input"]["scenario"] == "drive-forward"
    assert any(e["type"] == "assistant" and "passed" in e["text"] for e in ev)
    assert all("_session" not in e for e in ev)   # internal field never reaches the UI


def test_run_captures_session_for_resume():
    seen = {}
    def qf(message, resume):
        seen["resume"] = resume
        return _fake_query(message, resume)
    s = ChatSession("/tmp/x", query_fn=qf)
    _collect(s, "first")
    _collect(s, "second")
    assert seen["resume"] == "sess-42"      # 2nd turn resumes the captured session


def test_busy_lock_rejects_concurrent_turn():
    import threading
    gate = threading.Event()
    def slow_qf(message, resume):
        async def gen():
            yield AssistantMessage([TextBlock("working")])
            while not gate.is_set():
                await asyncio.sleep(0.01)
            yield ResultMessage()
        return gen()
    s = ChatSession("/tmp/x", query_fn=slow_qf)

    async def _drain(sess, m):
        async for _ in sess.run(m):
            pass

    async def go():
        first = asyncio.create_task(_drain(s, "a"))
        await asyncio.sleep(0.05)
        busy = [e async for e in s.run("b")]
        gate.set()
        await first
        return busy

    assert asyncio.run(go()) == [{"type": "busy"}]


def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ok, reason = ChatSession("/tmp/x").available()
    assert ok is False and "ANTHROPIC_API_KEY" in reason


def test_chat_available_route_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from robotbase.generator import create_project, template_dir
    from robotbase.studio.server import create_app
    project = create_project("cbot", str(tmp_path), template_dir("differential-drive"))
    c = TestClient(create_app(project))
    j = c.get("/api/chat/available").json()
    assert j["available"] is False and "ANTHROPIC_API_KEY" in j["reason"]


def test_chat_route_streams_events(tmp_path):
    # inject a fake-query ChatSession so no key/network is needed; the stream is finite per turn
    from fastapi.testclient import TestClient
    from robotbase.generator import create_project, template_dir
    from robotbase.studio.server import create_app
    from robotbase.studio.service import StudioService
    project = create_project("cbot2", str(tmp_path), template_dir("differential-drive"))
    svc = StudioService(project)
    svc.chat = ChatSession(project, query_fn=_fake_query)
    c = TestClient(create_app(project, service=svc))
    body = c.post("/api/chat", json={"message": "run it"}).text
    assert '"type": "assistant"' in body and '"type": "tool"' in body and '"type": "done"' in body
