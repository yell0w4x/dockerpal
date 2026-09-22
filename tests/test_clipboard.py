import subprocess

import pytest

from dockerpal import clipboard
# Bound at import time, so the autouse clipboard guard in conftest does not
# replace the very function these tests exercise.
from dockerpal.clipboard import copy


@pytest.fixture
def fake_tools(monkeypatch):
    """Pretend the named tools exist and record what gets run."""
    runs = []

    def make(available, failing=()):
        monkeypatch.setattr(clipboard.shutil, 'which',
                            lambda tool: f'/usr/bin/{tool}' if tool in available else None)

        def run(argv, **kwargs):
            runs.append((argv, kwargs.get('input')))
            if argv[0].rsplit('/', 1)[-1] in failing:
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 0)

        monkeypatch.setattr(clipboard.subprocess, 'run', run)
        return runs

    return make


def test_copy_uses_xclip_on_x11(fake_tools):
    runs = fake_tools({'xclip', 'xsel'})
    assert copy('hello') == 'xclip'
    argv, text = runs[0]
    assert argv == ['/usr/bin/xclip', '-selection', 'clipboard']
    assert text == b'hello'


def test_copy_prefers_wl_copy_when_present(fake_tools):
    runs = fake_tools({'wl-copy', 'xclip'})
    assert copy('hello') == 'wl-copy'
    assert runs[0][0] == ['/usr/bin/wl-copy']


def test_copy_falls_through_to_the_next_tool_when_one_fails(fake_tools):
    runs = fake_tools({'wl-copy', 'xclip'}, failing={'wl-copy'})
    assert copy('hello') == 'xclip'
    assert [argv[0] for argv, _ in runs] == ['/usr/bin/wl-copy', '/usr/bin/xclip']


def test_copy_returns_none_when_no_tool_is_available(fake_tools):
    fake_tools(set())
    assert copy('hello') is None


def test_copy_handles_a_missing_binary(monkeypatch):
    monkeypatch.setattr(clipboard.shutil, 'which', lambda tool: '/usr/bin/xclip' if tool == 'xclip' else None)

    def boom(*args, **kwargs):
        raise OSError('no such file')

    monkeypatch.setattr(clipboard.subprocess, 'run', boom)
    assert copy('hello') is None
