from textual.widgets import DataTable, Input, Label

from dockerpal.app import DockerPalApp
from tests.test_containers import goto_containers


def images_table(app):
    return app.screen.query_one('#images-table', DataTable)


def search_input(app):
    return app.screen.query_one('#search', Input)


def total_text(app):
    return str(app.screen.query('#table-footer Label')[0].content)


def rows(table):
    return [table.get_row_at(i) for i in range(table.row_count)]


async def test_slash_opens_search_input(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert search_input(app).display is False
        await pilot.press('slash')
        await pilot.pause()
        assert search_input(app).display is True
        assert app.focused is search_input(app)


async def test_typing_filters_rows_as_you_type(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.pause()
        table = images_table(app)
        assert rows(table) == [['b' * 12, 'ubuntu:22.04, ubuntu:jammy']]
        assert total_text(app) == 'Total: 1/3'


async def test_search_is_case_insensitive_and_matches_any_column(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'AAA')
        await pilot.pause()
        assert rows(images_table(app)) == [['a' * 12, 'alpine:latest']]


async def test_enter_keeps_the_filter_and_focuses_the_table(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'alpine')
        await pilot.press('enter')
        await pilot.pause()
        assert search_input(app).display is False
        assert app.focused.id == 'images-table'
        assert images_table(app).row_count == 1
        assert total_text(app) == 'Total: 1/3'


async def test_escape_cancels_the_search(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'alpine')
        await pilot.press('escape')
        await pilot.pause()
        assert search_input(app).display is False
        assert app.focused.id == 'images-table'
        assert images_table(app).row_count == 3
        assert total_text(app) == 'Total: 3'
        assert not app._exit


async def test_refresh_keeps_the_filter(client):
    from tests.fakes import FakeImage

    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.pause()
        client.images._images['sha256:' + 'd' * 64] = FakeImage('d' * 64, tags=['ubuntu:24.04'])
        await pilot.press('r')
        await pilot.pause()
        assert images_table(app).row_count == 2
        assert total_text(app) == 'Total: 2/4'


async def test_search_works_on_other_screens(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('slash')
        await pilot.press(*'web')
        await pilot.pause()
        table = app.screen.query_one('#containers-table', DataTable)
        assert [row[1] for row in rows(table)] == ['web']


async def test_delete_acts_on_the_filtered_row(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('d')
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert client.images.removed == ['sha256:' + 'b' * 64]
        assert images_table(app).row_count == 0
        assert total_text(app) == 'Total: 0/2'


async def test_no_match_shows_empty_table(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'nosuchthing')
        await pilot.pause()
        assert images_table(app).row_count == 0
        assert total_text(app) == 'Total: 0/3'
        await pilot.press('d')
        await pilot.press('space')
        await pilot.pause()
        assert app.screen.id == 'images-screen'


async def test_search_prompt_is_shown_while_searching(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        prompt = app.screen.query_one('#search-prompt', Label)
        assert prompt.display is False
        await pilot.press('slash')
        await pilot.pause()
        assert prompt.display is True
        assert str(prompt.content) == '/'
        await pilot.press('escape')
        await pilot.pause()
        assert prompt.display is False


async def test_active_filter_is_shown_in_the_footer_after_enter(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.pause()
        prompt = app.screen.query_one('#search-prompt', Label)
        assert prompt.display is True
        assert str(prompt.content) == '/ubuntu'
        assert search_input(app).display is False


async def test_escape_clears_an_active_filter_before_quitting(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert images_table(app).row_count == 3
        assert total_text(app) == 'Total: 3'
        assert app.screen.query_one('#search-prompt', Label).display is False
        assert not app._exit
        await pilot.press('escape')
        await pilot.pause()
        assert app._exit


async def test_reopening_search_keeps_the_previous_query(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('slash')
        await pilot.press(*'ubuntu')
        await pilot.press('enter')
        await pilot.press('slash')
        await pilot.pause()
        assert search_input(app).value == 'ubuntu'
