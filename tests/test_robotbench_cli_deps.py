import pytest
from robotbase.robotbench.cli_deps import expand_tasks, expand_arms


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
