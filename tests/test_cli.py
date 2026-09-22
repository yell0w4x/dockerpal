import pytest

from dockerpal import __version__
from dockerpal.cli import cli, main


def test_cli_accepts_no_arguments():
    args = cli([])
    assert not hasattr(args, 'change_me')


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli(['--version'])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_main_runs_the_app(monkeypatch):
    calls = []
    monkeypatch.setattr('dockerpal.cli.app', lambda: calls.append('run'))
    monkeypatch.setattr('sys.argv', ['dockerpal'])
    main()
    assert calls == ['run']
