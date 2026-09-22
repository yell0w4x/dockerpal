import pytest
from textual.widgets import TextArea

from dockerpal.app import DockerPalApp
from tests.test_containers import goto_containers
from tests.test_networks import goto_networks
from tests.test_volumes import goto_volumes


@pytest.mark.parametrize('goto, screen_id, title, expected_text', [
    (goto_containers, 'containers-screen', 'Container details', '"Name": "/db"'),
    (goto_networks, 'networks-screen', 'Network details', '"Name": "app_net"'),
    (goto_volumes, 'volumes-screen', 'Volume details', '"Name": "' + '5' * 64 + '"'),
])
async def test_enter_opens_details_and_escape_returns(client, goto, screen_id, title, expected_text):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto(pilot)
        await pilot.press('j')
        await pilot.press('enter')
        await pilot.pause()
        assert app.screen.id == 'details-screen'
        assert app.sub_title == title
        assert expected_text in app.screen.query_one('#details', TextArea).text
        await pilot.press('escape')
        await pilot.pause()
        assert app.screen.id == screen_id
        assert app.screen.query_one('DataTable').cursor_row == 1


async def test_sidebar_works_from_details_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('enter')
        await pilot.pause()
        assert app.screen.id == 'details-screen'
        await goto_containers(pilot)
        assert app.screen.id == 'containers-screen'


async def test_details_footer_only_offers_keys_that_work(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('enter')
        await pilot.pause()
        assert app.screen.id == 'details-screen'
        shown = {(b.key, b.description) for b in app.screen._bindings.shown_keys}
        assert shown == {('escape', 'Go back'), ('s', 'Sidebar')}


async def test_details_ignores_the_actions_and_search_keys(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('a')
        await pilot.press('slash')
        await pilot.pause()
        assert app.screen.id == 'details-screen'
        assert [n.message for n in app._notifications] == []
