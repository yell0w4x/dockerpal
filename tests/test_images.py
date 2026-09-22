from textual.widgets import DataTable, Label, TextArea

from dockerpal.app import DockerPalApp


def images_table(app):
    return app.screen.query_one('#images-table', DataTable)


def footer_text(app, index):
    labels = app.screen.query('#table-footer Label')
    return str(labels[index].content)


async def test_footer_shows_total_and_selected(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert footer_text(app, 0) == 'Total: 3'
        assert footer_text(app, 1) == 'Selected: 0'


async def test_space_selects_row_and_moves_cursor_down(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')
        assert footer_text(app, 1) == 'Selected: 1'
        assert images_table(app).cursor_row == 1


async def test_select_all_deselect_all_invert(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('+')
        assert footer_text(app, 1) == 'Selected: 3'
        await pilot.press('-')
        assert footer_text(app, 1) == 'Selected: 0'
        await pilot.press('space')
        await pilot.press('*')
        assert footer_text(app, 1) == 'Selected: 2'


async def test_delete_removes_image_under_cursor(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('j')
        await pilot.press('d')
        await pilot.pause()
        assert client.images.removed == ['sha256:' + 'b' * 64]
        assert images_table(app).row_count == 2
        assert footer_text(app, 0) == 'Total: 2'


async def test_delete_removes_selected_images(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')
        await pilot.press('space')
        await pilot.press('d')
        await pilot.pause()
        assert sorted(client.images.removed) == ['sha256:' + 'a' * 64, 'sha256:' + 'b' * 64]
        assert images_table(app).row_count == 1
        assert footer_text(app, 1) == 'Selected: 0'


async def test_refresh_picks_up_new_images(client):
    from tests.fakes import FakeImage

    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        client.images._images['sha256:' + 'd' * 64] = FakeImage('d' * 64, tags=['new:1'])
        await pilot.press('r')
        await pilot.pause()
        assert images_table(app).row_count == 4
        assert footer_text(app, 0) == 'Total: 4'


async def test_enter_opens_image_details_and_escape_returns(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('j')
        await pilot.press('enter')
        await pilot.pause()
        assert app.screen.id == 'image-details-screen'
        assert app.sub_title == 'Image details'
        details = app.screen.query_one('#image-details', TextArea)
        assert 'ubuntu:22.04' in details.text
        await pilot.press('escape')
        await pilot.pause()
        assert app.screen.id == 'images-screen'
        assert images_table(app).cursor_row == 1
