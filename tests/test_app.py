from textual.widgets import DataTable

from dockerpal.app import DockerPalApp


async def test_app_starts_on_images_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.id == 'images-screen'
        assert app.sub_title == 'Images'
        table = app.screen.query_one('#images-table', DataTable)
        assert table.row_count == 3


async def test_images_table_shows_short_id_and_tags(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one('#images-table', DataTable)
        rows = [table.get_row_at(i) for i in range(table.row_count)]
        assert rows[0] == ['a' * 12, 'alpine:latest']
        assert rows[1] == ['b' * 12, 'ubuntu:22.04, ubuntu:jammy']
        assert rows[2] == ['c' * 12, '<None>']
