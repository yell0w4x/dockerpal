import json
from pathlib import Path

from textual.widgets import TextArea
from textual.widgets.text_area import Selection

from dockerpal.app import DockerPalApp
from tests.test_containers import goto_containers


def details(app):
    return app.screen.query_one('#details', TextArea)


def notifications(app):
    return [n.message for n in app._notifications]


async def open_image_details(pilot):
    await pilot.press('enter')
    await pilot.pause()


async def test_y_copies_the_selected_text(client, no_system_clipboard):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        details(app).selection = Selection(start=(0, 0), end=(1, 0))
        await pilot.pause()
        await pilot.press('y')
        await pilot.pause()
        assert no_system_clipboard == ['{\n']
        assert app.clipboard == '{\n'
        assert any('Copied' in m for m in notifications(app))


async def test_y_without_a_selection_copies_everything(client, no_system_clipboard):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        await pilot.press('y')
        await pilot.pause()
        assert no_system_clipboard == [details(app).text]
        assert app.clipboard == details(app).text
        assert json.loads(app.clipboard)['RepoTags'] == ['alpine:latest']


async def test_e_exports_the_details_to_a_json_file(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        await pilot.press('e')
        await pilot.pause()
        exported = tmp_path / 'alpine_latest.json'
        assert exported.exists()
        assert json.loads(exported.read_text())['RepoTags'] == ['alpine:latest']
        assert any(str(exported) in m for m in notifications(app))


async def test_export_names_the_file_after_the_container(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await goto_containers(pilot)
        await pilot.press('j')
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('e')
        await pilot.pause()
        assert json.loads((tmp_path / 'db.json').read_text())['Name'] == '/db'


async def test_export_never_overwrites_an_existing_file(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'alpine_latest.json').write_text('keep me')
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        await pilot.press('e')
        await pilot.pause()
        assert (tmp_path / 'alpine_latest.json').read_text() == 'keep me'
        assert json.loads((tmp_path / 'alpine_latest-1.json').read_text())['RepoTags']


async def test_export_reports_failures(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)

        def boom(*args, **kwargs):
            raise PermissionError('read-only file system')

        monkeypatch.setattr(Path, 'write_text', boom)
        await pilot.press('e')
        await pilot.pause()
        assert any('read-only file system' in m for m in notifications(app))


async def test_details_footer_advertises_copy_and_export(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        shown = {(b.key, b.description) for b in app.screen._bindings.shown_keys}
        assert shown == {
            ('escape', 'Go back'),
            ('s', 'Sidebar'),
            ('y', 'Copy'),
            ('e', 'Export JSON'),
        }


async def test_copy_goes_to_the_system_clipboard(client, monkeypatch):
    from dockerpal import clipboard

    copied = []
    monkeypatch.setattr(clipboard, 'copy', lambda text: copied.append(text) or 'xclip')
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        await pilot.press('y')
        await pilot.pause()
        assert copied == [details(app).text]
        assert app.clipboard == details(app).text     # OSC 52 as well, for ssh/tmux
        assert any('clipboard' in m for m in notifications(app))


async def test_copy_warns_when_no_clipboard_tool_is_installed(client, monkeypatch):
    from dockerpal import clipboard

    monkeypatch.setattr(clipboard, 'copy', lambda text: None)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_image_details(pilot)
        await pilot.press('y')
        await pilot.pause()
        assert app.clipboard == details(app).text
        warnings = [n for n in app._notifications if n.severity == 'warning']
        assert warnings and 'xclip' in warnings[0].message
