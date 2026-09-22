from textual.widgets import ListView

from dockerpal.app import DockerPalApp
from tests.test_containers import goto_containers


def sidebar(app):
    return app.screen.query_one('#sidebar', ListView)


async def test_s_toggles_sidebar(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sidebar(app).styles.display == 'none'
        await pilot.press('s')
        assert sidebar(app).styles.display == 'block'
        assert app.focused is sidebar(app)
        await pilot.press('s')
        assert sidebar(app).styles.display == 'none'


async def test_escape_closes_sidebar_instead_of_quitting(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('s')
        await pilot.press('escape')
        await pilot.pause()
        assert app.return_value is None
        assert not app._exit
        assert sidebar(app).styles.display == 'none'
        assert app.focused.id == 'images-table'


async def test_sidebar_highlights_current_screen(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('s')
        await pilot.pause()
        assert sidebar(app).highlighted_child.id == 'containers-sidebar-item'
