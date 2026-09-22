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


async def test_stop_container_under_cursor(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('x')
        await pilot.pause()
        assert containers[0].calls == ['stop']
        assert containers_table(app).get_row_at(0)[3] == 'exited'


async def test_start_container_under_cursor(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('j')
        await pilot.press('u')
        await pilot.pause()
        assert containers[1].calls == ['start']
        assert containers_table(app).get_row_at(1)[3] == 'running'


async def test_restart_selected_containers(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('+')
        await pilot.press('t')
        await pilot.pause()
        assert containers[0].calls == ['restart']
        assert containers[1].calls == ['restart']


async def test_delete_stopped_container(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('j')
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert containers[1].calls == ['remove']
        assert containers_table(app).row_count == 1


async def test_delete_running_container_reports_error(client, containers):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert containers[0].calls == []
        assert containers_table(app).row_count == 2
        notifications = [n.message for n in app._notifications]
        assert any('cannot remove running container' in m for m in notifications)
