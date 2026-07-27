import pathlib
import pytest
from robotbase.robotbench.apikey import ensure_api_key, _read_key_file


def test_read_key_file_raw_and_dotenv(tmp_path):
    raw = tmp_path / "k1"; raw.write_text("sk-ant-RAW\n")
    assert _read_key_file(raw) == "sk-ant-RAW"
    dot = tmp_path / "k2"; dot.write_text("ANTHROPIC_API_KEY=sk-ant-DOT\n")
    assert _read_key_file(dot) == "sk-ant-DOT"
    assert _read_key_file(tmp_path / "missing") is None


def test_ensure_prefers_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ENV")
    ensure_api_key()  # no-op, no raise


def test_ensure_reads_cwd_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".robotbench_key").write_text("ANTHROPIC_API_KEY=sk-ant-FILE\n")
    ensure_api_key()
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-FILE"


def test_ensure_raises_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "nohome")
    with pytest.raises(RuntimeError, match="No Anthropic API key"):
        ensure_api_key()
