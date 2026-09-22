import pytest

from tests.fakes import FakeClient, FakeContainer, FakeImage, FakeNetwork


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
        FakeContainer('1' * 64, 'web', images[0], status='running'),
        FakeContainer('2' * 64, 'db', images[1], status='exited'),
    ]


@pytest.fixture
def networks():
    return [
        FakeNetwork('3' * 64, 'bridge'),
        FakeNetwork('4' * 64, 'app_net', driver='overlay', scope='swarm'),
    ]


@pytest.fixture
def client(images, containers, networks):
    return FakeClient(images=images, containers=containers, networks=networks)
