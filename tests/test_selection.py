from textual.widgets import DataTable

from dockerpal.app import DockerPalApp


def images_table(app):
    return app.screen.query_one('#images-table', DataTable)


def labels(app):
    return [str(row.label) for row in images_table(app).rows.values()]


def selected_text(app):
    return str(app.screen.query('#table-footer Label')[1].content)


def total_text(app):
    return str(app.screen.query('#table-footer Label')[0].content)


async def test_selection_marker_follows_the_item_through_a_filter(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('j')          # cursor on ubuntu
        await pilot.press('space')      # select it
        assert selected_text(app) == 'Selected: 1'
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.pause()
        assert images_table(app).row_count == 1
        assert selected_text(app) == 'Selected: 1'
        assert '[✓]' in labels(app)[0]


async def test_selection_survives_cancelling_the_search(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')      # select alpine
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('escape')     # drop the filter
        await pilot.pause()
        assert images_table(app).row_count == 3
        assert selected_text(app) == 'Selected: 1'
        assert '[✓]' in labels(app)[0]
        assert '[✓]' not in labels(app)[1]


async def test_selection_survives_refresh(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')
        await pilot.press('r')
        await pilot.pause()
        assert selected_text(app) == 'Selected: 1'
        assert '[✓]' in labels(app)[0]


async def test_select_all_applies_to_visible_rows_only(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.press('+')
        await pilot.pause()
        assert selected_text(app) == 'Selected: 1'
        await pilot.press('escape')     # clear the filter, all rows back
        await pilot.pause()
        assert images_table(app).row_count == 3
        assert selected_text(app) == 'Selected: 1'
        assert '[✓]' in labels(app)[1]


async def test_invert_and_deselect_apply_to_visible_rows_only(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('+')          # select all 3
        assert selected_text(app) == 'Selected: 3'
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.press('-')          # deselect the visible one
        await pilot.pause()
        assert selected_text(app) == 'Selected: 2'
        await pilot.press('*')          # invert the visible one back on
        await pilot.pause()
        assert selected_text(app) == 'Selected: 3'


async def test_delete_acts_on_the_whole_selection(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')      # select alpine
        await pilot.press('slash')      # then hide it behind a filter
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.press('d')
        await pilot.pause()
        assert 'Remove 1 image' in str(app.screen.query_one('#question').content)
        await pilot.press('y')
        await pilot.pause()
        assert client.images.removed == ['sha256:' + 'a' * 64]
        assert selected_text(app) == 'Selected: 0'


async def test_deleted_items_drop_out_of_the_selection(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('space')
        await pilot.press('space')
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert selected_text(app) == 'Selected: 0'
        assert total_text(app) == 'Total: 1'
