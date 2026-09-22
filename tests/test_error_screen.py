from textual.widgets import Label

import dockerpal.app
from dockerpal.app import DockerPalApp


async def test_error_screen_when_docker_is_unreachable(monkeypatch):
    def broken_from_env():
        raise RuntimeError('daemon not running')

    monkeypatch.setattr(dockerpal.app.docker, 'from_env', broken_from_env)
    app = DockerPalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        message = str(app.screen.query_one('#error-label', Label).content)
        assert 'daemon not running' in message
        await pilot.press('escape')
        await pilot.pause()
        assert app._exit
