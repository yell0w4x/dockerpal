from textual.widgets import DataTable, Label

from dockerpal.app import DockerPalApp


def images_table(app):
    return app.screen.query_one('#images-table', DataTable)


async def test_delete_asks_for_confirmation(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('d')
        await pilot.pause()
        assert app.screen.id == 'confirm-screen'
        question = str(app.screen.query_one('#question', Label).content)
        assert 'Remove 1 image' in question
        assert client.images.removed == []


async def test_confirming_deletes(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')
        await pilot.press('space')
        await pilot.press('d')
        await pilot.pause()
        assert 'Remove 2 images' in str(app.screen.query_one('#question', Label).content)
        await pilot.press('y')
        await pilot.pause()
        assert app.screen.id == 'images-screen'
        assert len(client.images.removed) == 2
        assert images_table(app).row_count == 1


async def test_cancelling_keeps_everything(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.screen.id == 'images-screen'
        assert client.images.removed == []
        assert images_table(app).row_count == 3
        assert app.focused.id == 'images-table'
