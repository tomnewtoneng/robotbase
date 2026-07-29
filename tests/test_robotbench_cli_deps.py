import pytest
from robotbase.robotbench import cli_deps
from robotbase.robotbench.cli_deps import expand_tasks, expand_arms


def test_author_generate_uses_scaffold(tmp_path, monkeypatch):
    seen = {}

    def fake_build_scaffold(task, arm, root):
        seen["call"] = (arm, root)
        return "/scaf"

    monkeypatch.setattr(cli_deps, "build_scaffold", fake_build_scaffold)
    gen = cli_deps.author_generate(str(tmp_path), "without")
    assert gen({"id": "author/x", "kind": "author"}, 0) == "/scaf"
    assert seen["call"][0] == "without"


def test_real_author_judge_returns_callable():
    jf = cli_deps.real_author_judge("with", trials=3, evidence_root="/tmp/e")
    assert callable(jf)


def test_expand_arms():
    assert expand_arms("both") == ["with", "without"]
    assert expand_arms("with") == ["with"]
    assert expand_arms("without") == ["without"]


def test_expand_tasks_all_and_single():
    tasks = expand_tasks("all")
    assert len(tasks) == 4 and all("kind" in t and "prompt" in t for t in tasks)
    one = expand_tasks("import/add-sensor")
    assert len(one) == 1 and one[0]["id"] == "import/add-sensor"


def test_expand_tasks_unknown_raises():
    with pytest.raises(ValueError):
        expand_tasks("nope/does-not-exist")
