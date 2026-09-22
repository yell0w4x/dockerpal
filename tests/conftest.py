import pytest

from tests.fakes import FakeClient, FakeImage


@pytest.fixture
def images():
    return [
        FakeImage('a' * 64, tags=['alpine:latest']),
        FakeImage('b' * 64, tags=['ubuntu:22.04', 'ubuntu:jammy']),
        FakeImage('c' * 64),
    ]


@pytest.fixture
def client(images):
    return FakeClient(images=images)
