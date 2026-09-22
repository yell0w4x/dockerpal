"""In-memory stand-ins for the docker SDK objects used by the app."""

import docker.errors


class FakeImage:
    def __init__(self, image_id, tags=None, attrs=None):
        self.id = f'sha256:{image_id}'
        self.short_id = f'sha256:{image_id[:12]}'
        self.tags = tags or []
        self.attrs = attrs or {'Id': self.id, 'RepoTags': self.tags}


class FakeImages:
    def __init__(self, images):
        self._images = {img.id: img for img in images}
        self.removed = []

    def list(self, **kwargs):
        return list(self._images.values())

    def get(self, image_id):
        for key, img in self._images.items():
            if key == image_id or key.endswith(image_id) or image_id in img.tags:
                return img
        raise docker.errors.ImageNotFound(f'No such image: {image_id}')

    def remove(self, image_id, **kwargs):
        img = self.get(image_id)
        del self._images[img.id]
        self.removed.append(img.id)


class FakeContainer:
    def __init__(self, container_id, name, image, status='running', attrs=None):
        self.id = container_id
        self.short_id = container_id[:12]
        self.name = name
        self.image = image
        self.status = status
        self.attrs = attrs or {'Id': self.id, 'Name': f'/{name}', 'State': {'Status': status}}
        self.calls = []

    def start(self):
        self.calls.append('start')
        self.status = 'running'

    def stop(self):
        self.calls.append('stop')
        self.status = 'exited'

    def restart(self):
        self.calls.append('restart')
        self.status = 'running'

    def remove(self, **kwargs):
        if self.status == 'running' and not kwargs.get('force'):
            raise docker.errors.APIError(
                'conflict', explanation=f'cannot remove running container {self.short_id}')
        self.calls.append('remove')


class FakeContainers:
    def __init__(self, containers):
        self._containers = {c.id: c for c in containers}

    def list(self, all=False, **kwargs):
        return [c for c in self._containers.values() if all or c.status == 'running']

    def get(self, container_id):
        for key, c in self._containers.items():
            if key == container_id or key.startswith(container_id) or c.name == container_id:
                return c
        raise docker.errors.NotFound(f'No such container: {container_id}')

    def remove(self, container_id, **kwargs):
        c = self.get(container_id)
        c.remove(**kwargs)
        del self._containers[c.id]


class FakeClient:
    def __init__(self, images=(), containers=()):
        self.images = FakeImages(images)
        self.containers = FakeContainers(containers)
