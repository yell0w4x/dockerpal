from textual.widgets import DataTable

from dockerpal.app import DockerPalApp


async def goto_volumes(pilot):
    await pilot.press('s')
    await pilot.press('down')
    await pilot.press('down')
    await pilot.press('down')
    await pilot.press('enter')
    await pilot.pause()


def volumes_table(app):
    return app.screen.query_one('#volumes-table', DataTable)


async def test_sidebar_opens_volumes_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_volumes(pilot)
        assert app.screen.id == 'volumes-screen'
        assert app.sub_title == 'Volumes'


async def test_volumes_table_lists_volumes(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_volumes(pilot)
        table = volumes_table(app)
        rows = [table.get_row_at(i) for i in range(table.row_count)]
        assert rows == [
            ['pgdata', 'local', '/var/lib/docker/volumes/pgdata/_data'],
            ['5' * 64, 'local', '/var/lib/docker/volumes/' + '5' * 64 + '/_data'],
        ]


async def test_delete_volume(client, volumes):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_volumes(pilot)
        await pilot.press('j')
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert volumes[1].calls == ['remove']
        assert volumes_table(app).row_count == 1


async def test_delete_volume_in_use_reports_error(client, volumes):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_volumes(pilot)
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert volumes_table(app).row_count == 2
        assert any('is in use' in n.message for n in app._notifications)
