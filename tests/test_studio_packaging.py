import subprocess
import sys


def test_version_flag(capsys):
    import robotbase.cli as cli
    from robotbase import __version__
    cli.main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_core_import_does_not_pull_fastapi():
    # importing the core (cli) must not import fastapi — studio deps stay optional
    code = "import robotbase.cli, sys; assert 'fastapi' not in sys.modules, 'core imported fastapi'"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_studio_command_hint_without_extra(monkeypatch, capsys):
    # when the studio extra import fails, the CLI prints the install hint and exits non-zero
    import builtins
    import pytest
    import robotbase.cli as cli
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("robotbase.studio"):
            raise ImportError("no fastapi")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SystemExit) as exc:
        cli.main(["studio"])
    assert exc.value.code != 0
    assert "pip install robotbase-kit[studio]" in capsys.readouterr().out
