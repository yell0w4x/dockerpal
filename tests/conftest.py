import pytest

from dockerpal import clipboard

from tests.fakes import FakeClient, FakeContainer, FakeImage, FakeNetwork, FakeVolume


@pytest.fixture
def images():
    return [
        FakeImage('a' * 64, tags=['alpine:latest']),
        FakeImage('b' * 64, tags=['ubuntu:22.04', 'ubuntu:jammy']),
        FakeImage('c' * 64),
    ]


@pytest.fixture
def containers(images):
    return [
        FakeContainer('1' * 64, 'web', 'alpine:latest', status='running'),
        FakeContainer('2' * 64, 'db', 'ubuntu:22.04', status='exited'),
    ]


@pytest.fixture
def networks():
    return [
        FakeNetwork('3' * 64, 'bridge'),
        FakeNetwork('4' * 64, 'app_net', driver='overlay', scope='swarm'),
    ]


@pytest.fixture
def volumes():
    return [
        FakeVolume('pgdata', in_use=True),
        FakeVolume('5' * 64),
    ]


@pytest.fixture
def client(images, containers, networks, volumes):
    return FakeClient(images=images, containers=containers, networks=networks, volumes=volumes)


@pytest.fixture(autouse=True)
def no_system_clipboard(monkeypatch):
    """Never let the test suite scribble on the developer's real clipboard.

    Tests that care about the clipboard assert against this recorder instead;
    tests/test_clipboard.py exercises the real module with fake tools.
    """
    copied = []
    monkeypatch.setattr(clipboard, 'copy', lambda text: copied.append(text) or 'xclip')
    return copied
