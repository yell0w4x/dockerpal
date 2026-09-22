import docker.errors
import pytest
from textual.widgets import Input, Label

from dockerpal.app import DockerPalApp
from tests.test_actions_menu import menu_labels, open_menu, choose
from tests.test_containers import goto_containers


def prompt_input(app):
    return app.screen.query_one('#prompt-input', Input)


def prompt_title(app):
    return str(app.screen.query_one('#prompt-title', Label).content)


def notifications(app):
    return [n.message for n in app._notifications]


async def test_commit_is_offered_in_the_containers_menu(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        assert 'Commit as image' in menu_labels(app)


async def test_commit_prompts_with_a_default_name(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        await choose(pilot, menu_labels(app).index('Commit as image'))
        assert app.screen.id == 'prompt-screen'
        assert prompt_title(app) == 'Commit web as:'
        assert prompt_input(app).value == 'web:latest'


async def test_commit_creates_the_image(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.pause()
        for _ in range(len('web:latest')):
            await pilot.press('backspace')
        await pilot.press(*'snapshot:v1')
        await pilot.press('enter')
        await pilot.pause()
        assert containers[0].calls == [('commit', 'snapshot', 'v1')]
        assert app.screen.id == 'containers-screen'
        assert any('snapshot:v1' in m for m in notifications(app))


async def test_commit_without_a_tag_defaults_to_latest(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.pause()
        for _ in range(len('web:latest')):
            await pilot.press('backspace')
        await pilot.press(*'snapshot')
        await pilot.press('enter')
        await pilot.pause()
        assert containers[0].calls == [('commit', 'snapshot', 'latest')]


async def test_commit_keeps_a_registry_port_out_of_the_tag(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.pause()
        for _ in range(len('web:latest')):
            await pilot.press('backspace')
        await pilot.press(*'reg.local:5000/web')
        await pilot.press('enter')
        await pilot.pause()
        assert containers[0].calls == [('commit', 'reg.local:5000/web', 'latest')]


async def test_escape_cancels_the_commit(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert containers[0].calls == []
        assert app.screen.id == 'containers-screen'
        assert app.focused.id == 'containers-table'
        assert not app._exit


async def test_empty_name_does_not_commit(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.pause()
        for _ in range(len('web:latest')):
            await pilot.press('backspace')
        await pilot.press('enter')
        await pilot.pause()
        assert containers[0].calls == []
        assert app.screen.id == 'containers-screen'


async def test_commit_reports_docker_errors(client, containers, monkeypatch):
    def boom(**kwargs):
        raise docker.errors.APIError('nope', explanation='invalid reference format')

    monkeypatch.setattr(containers[0], 'commit', boom)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('c')
        await pilot.press('enter')
        await pilot.pause()
        assert any('invalid reference format' in m for m in notifications(app))


async def test_commit_uses_the_cursor_row_even_with_a_selection(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('+')          # select both
        await pilot.press('j')          # cursor on db
        await pilot.press('c')
        await pilot.pause()
        assert prompt_title(app) == 'Commit db as:'
        await pilot.press('enter')
        await pilot.pause()
        assert containers[0].calls == []
        assert containers[1].calls == [('commit', 'db', 'latest')]
