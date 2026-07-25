from robotbase.doctor import check_project, diagnose_environment, overall


def test_overall_worst_status_wins():
    assert overall([{"status": "ok"}, {"status": "ok"}]) == "ok"
    assert overall([{"status": "ok"}, {"status": "warn"}]) == "warn"
    assert overall([{"status": "warn"}, {"status": "fail"}]) == "fail"


def test_check_project_detects_manifest(tmp_path):
    miss = check_project(str(tmp_path))
    assert miss["status"] == "warn" and "fix" in miss

    (tmp_path / "robotbase.yaml").write_text("version: 1\n")
    found = check_project(str(tmp_path))
    assert found["status"] == "ok"


def test_report_is_well_formed(tmp_path):
    report = diagnose_environment(str(tmp_path))
    assert report["status"] in {"ok", "warn", "fail"}
    assert isinstance(report["summary"], str)
    names = {c["check"] for c in report["checks"]}
    assert {"docker", "compose", "runtime-image", "port-8765", "project",
            "container", "python-deps"} <= names
    for c in report["checks"]:
        assert c["status"] in {"ok", "warn", "fail"}
        assert "detail" in c
