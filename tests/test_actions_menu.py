from textual.widgets import DataTable, Label, ListView

from dockerpal.app import DockerPalApp
from tests.test_containers import goto_containers
from tests.test_networks import goto_networks
from tests.test_volumes import goto_volumes


def menu(app):
    return app.screen.query_one('#actions-list', ListView)


def menu_labels(app):
    return [str(item.query_one('.action-label', Label).content) for item in menu(app).children]


def menu_title(app):
    return str(app.screen.query_one('#actions-title', Label).content)


async def open_menu(pilot):
    await pilot.press('a')
    await pilot.pause()


async def choose(pilot, index):
    for _ in range(index):
        await pilot.press('down')
    await pilot.press('enter')
    await pilot.pause()


async def test_a_opens_the_actions_menu_for_containers(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        assert app.screen.id == 'actions-menu'
        assert menu_labels(app) == [
            'Start', 'Stop', 'Restart', 'Remove', 'Force remove', 'Details',
        ]
        assert menu_title(app) == 'Actions: 1 container'


async def test_menu_title_reflects_the_selection(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('+')
        await open_menu(pilot)
        assert menu_title(app) == 'Actions: 2 containers'


async def test_choosing_stop_stops_the_container(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        await choose(pilot, 1)          # Stop
        assert app.screen.id == 'containers-screen'
        assert containers[0].calls == ['stop']
        assert app.screen.query_one(DataTable).get_row_at(0)[2] == 'exited'


async def test_choosing_start_starts_the_container(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('j')
        await open_menu(pilot)
        await choose(pilot, 0)          # Start
        assert containers[1].calls == ['start']


async def test_choosing_remove_asks_for_confirmation(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('j')
        await open_menu(pilot)
        await choose(pilot, 3)          # Remove
        assert app.screen.id == 'confirm-screen'
        assert 'Remove 1 container?' in str(app.screen.query_one('#question', Label).content)
        await pilot.press('y')
        await pilot.pause()
        assert containers[1].calls == ['remove']


async def test_force_remove_kills_a_running_container(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        await choose(pilot, 4)          # Force remove
        assert 'Force remove 1 container?' in str(app.screen.query_one('#question', Label).content)
        await pilot.press('y')
        await pilot.pause()
        assert containers[0].calls == ['remove']
        assert app.screen.query_one(DataTable).row_count == 1


async def test_choosing_details_opens_the_details_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        await choose(pilot, 5)          # Details
        assert app.screen.id == 'details-screen'
        assert app.sub_title == 'Container details'


async def test_escape_closes_the_menu_without_acting(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        await pilot.press('escape')
        await pilot.pause()
        assert app.screen.id == 'containers-screen'
        assert app.focused.id == 'containers-table'
        assert containers[0].calls == []
        assert not app._exit


async def test_images_menu(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_menu(pilot)
        assert menu_labels(app) == ['Remove', 'Force remove', 'Details']
        assert menu_title(app) == 'Actions: 1 image'
        await choose(pilot, 0)
        assert 'Remove 1 image?' in str(app.screen.query_one('#question', Label).content)
        await pilot.press('y')
        await pilot.pause()
        assert client.images.removed == ['sha256:' + 'a' * 64]


async def test_networks_menu(client, networks):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_networks(pilot)
        await open_menu(pilot)
        assert menu_labels(app) == ['Remove', 'Details']
        assert menu_title(app) == 'Actions: 1 network'
        await pilot.press('escape')
        await pilot.press('j')
        await open_menu(pilot)
        await choose(pilot, 0)
        await pilot.press('y')
        await pilot.pause()
        assert networks[1].calls == ['remove']


async def test_volumes_menu(client, volumes):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_volumes(pilot)
        await open_menu(pilot)
        assert menu_labels(app) == ['Remove', 'Force remove', 'Details']
        assert menu_title(app) == 'Actions: 1 volume'
        await choose(pilot, 1)          # Force remove the in-use volume
        assert 'Force remove 1 volume?' in str(app.screen.query_one('#question', Label).content)
        await pilot.press('y')
        await pilot.pause()
        assert volumes[0].calls == ['remove']


async def test_menu_acts_on_the_whole_selection(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('+')
        await open_menu(pilot)
        await choose(pilot, 2)          # Restart
        assert containers[0].calls == ['restart']
        assert containers[1].calls == ['restart']


def menu_keys(app):
    return [str(item.query_one('.action-key', Label).content) for item in menu(app).children]


async def test_menu_shows_the_keyboard_shortcuts(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await open_menu(pilot)
        assert menu_keys(app) == ['u', 'x', 't', 'd', '', 'enter']


async def test_footer_calls_it_remove(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        descriptions = {b.description for b in app.screen._bindings.shown_keys}
        assert 'Remove' in descriptions
        assert 'Delete' not in descriptions
