from textual.widgets import DataTable

from dockerpal.app import DockerPalApp


async def goto_containers(pilot):
    # Sidebar: Images is highlighted first; one step down is Containers.
    await pilot.press('s')
    await pilot.press('down')
    await pilot.press('enter')
    await pilot.pause()


def containers_table(app):
    return app.screen.query_one('#containers-table', DataTable)


async def test_sidebar_opens_containers_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        assert app.screen.id == 'containers-screen'
        assert app.sub_title == 'Containers'


async def test_containers_table_lists_all_containers(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        table = containers_table(app)
        rows = [table.get_row_at(i) for i in range(table.row_count)]
        assert rows == [
            ['1' * 12, 'web', 'alpine:latest', 'running'],
            ['2' * 12, 'db', 'ubuntu:22.04', 'exited'],
        ]
