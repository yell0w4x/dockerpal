from textual.widgets import DataTable

from dockerpal.app import DockerPalApp


async def goto_networks(pilot):
    await pilot.press('s')
    await pilot.press('down')
    await pilot.press('down')
    await pilot.press('enter')
    await pilot.pause()


def networks_table(app):
    return app.screen.query_one('#networks-table', DataTable)


async def test_sidebar_opens_networks_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_networks(pilot)
        assert app.screen.id == 'networks-screen'
        assert app.sub_title == 'Networks'


async def test_networks_table_lists_networks(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_networks(pilot)
        table = networks_table(app)
        rows = [table.get_row_at(i) for i in range(table.row_count)]
        assert rows == [
            ['3' * 12, 'bridge', 'bridge', 'local'],
            ['4' * 12, 'app_net', 'overlay', 'swarm'],
        ]


async def test_delete_network(client, networks):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_networks(pilot)
        await pilot.press('j')
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert networks[1].calls == ['remove']
        assert networks_table(app).row_count == 1


async def test_delete_predefined_network_reports_error(client, networks):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_networks(pilot)
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert networks_table(app).row_count == 2
        assert any('pre-defined network' in n.message for n in app._notifications)
