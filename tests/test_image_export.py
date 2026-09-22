import json

from dockerpal.app import DockerPalApp
from tests.test_actions_menu import choose_action, menu_labels, open_menu


def notifications(app):
    return [n.message for n in app._notifications]


async def test_images_menu_offers_both_exports(client):
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_menu(pilot)
        assert menu_labels(app) == [
            'Remove', 'Force remove', 'Export JSON', 'Export Dockerfile', 'Details',
        ]


async def test_export_json_writes_the_image_metadata(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_menu(pilot)
        await choose_action(pilot, app, 'Export JSON')
        exported = tmp_path / 'alpine_latest.json'
        assert json.loads(exported.read_text())['RepoTags'] == ['alpine:latest']
        assert any(str(exported) in m for m in notifications(app))
        assert app.screen.id == 'images-screen'


async def test_export_dockerfile_writes_a_reconstruction(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_menu(pilot)
        await choose_action(pilot, app, 'Export Dockerfile')
        exported = tmp_path / 'alpine_latest.Dockerfile'
        lines = [l for l in exported.read_text().splitlines() if not l.startswith('#')]
        assert lines == ['FROM scratch', 'ADD file:deadbeef in /', 'CMD ["/bin/sh"]']
        assert exported.read_text().startswith('# alpine:latest')


async def test_export_covers_the_whole_selection(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('+')          # all three images
        await open_menu(pilot)
        await choose_action(pilot, app, 'Export JSON')
        written = sorted(p.name for p in tmp_path.glob('*.json'))
        assert written == ['alpine_latest.json', 'c' * 12 + '.json', 'ubuntu_22.04.json']
        assert any('Exported 3 files' in m for m in notifications(app))


async def test_export_reports_failures(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()

        from pathlib import Path

        def boom(*args, **kwargs):
            raise PermissionError('read-only file system')

        monkeypatch.setattr(Path, 'write_text', boom)
        await open_menu(pilot)
        await choose_action(pilot, app, 'Export JSON')
        assert any('read-only file system' in m for m in notifications(app))


async def test_dockerfile_export_reports_history_failures(client, images, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import docker.errors

    def boom():
        raise docker.errors.APIError('nope', explanation='image history unavailable')

    monkeypatch.setattr(images[0], 'history', boom)
    app = DockerPalApp(docker_cli=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_menu(pilot)
        await choose_action(pilot, app, 'Export Dockerfile')
        assert any('image history unavailable' in m for m in notifications(app))
