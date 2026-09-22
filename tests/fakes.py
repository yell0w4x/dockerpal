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
        self.collection = None

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
        if self.collection is not None:
            self.collection._containers.pop(self.id, None)


class FakeContainers:
    def __init__(self, containers):
        self._containers = {c.id: c for c in containers}
        for c in containers:
            c.collection = self

    def list(self, all=False, **kwargs):
        return [c for c in self._containers.values() if all or c.status == 'running']

    def get(self, container_id):
        for key, c in self._containers.items():
            if key == container_id or key.startswith(container_id) or c.name == container_id:
                return c
        raise docker.errors.NotFound(f'No such container: {container_id}')

    def remove(self, container_id, **kwargs):
        self.get(container_id).remove(**kwargs)


class FakeNetwork:
    def __init__(self, network_id, name, driver='bridge', scope='local', attrs=None):
        self.id = network_id
        self.short_id = network_id[:12]
        self.name = name
        self.attrs = attrs or {'Id': self.id, 'Name': name, 'Driver': driver, 'Scope': scope}
        self.collection = None
        self.calls = []

    def remove(self):
        if self.name in ('bridge', 'host', 'none'):
            raise docker.errors.APIError(
                'forbidden', explanation=f'{self.name} is a pre-defined network and cannot be removed')
        self.calls.append('remove')
        if self.collection is not None:
            self.collection._networks.pop(self.id, None)


class FakeNetworks:
    def __init__(self, networks):
        self._networks = {n.id: n for n in networks}
        for n in networks:
            n.collection = self

    def list(self, **kwargs):
        return list(self._networks.values())

    def get(self, network_id, **kwargs):
        for key, n in self._networks.items():
            if key == network_id or key.startswith(network_id) or n.name == network_id:
                return n
        raise docker.errors.NotFound(f'No such network: {network_id}')


class FakeVolume:
    def __init__(self, name, driver='local', mountpoint=None, in_use=False, attrs=None):
        self.id = name
        self.short_id = name[:12]
        self.name = name
        self.in_use = in_use
        mountpoint = mountpoint or f'/var/lib/docker/volumes/{name}/_data'
        self.attrs = attrs or {'Name': name, 'Driver': driver, 'Mountpoint': mountpoint}
        self.collection = None
        self.calls = []

    def remove(self, force=False):
        if self.in_use and not force:
            raise docker.errors.APIError(
                'conflict', explanation=f'volume {self.name} is in use')
        self.calls.append('remove')
        if self.collection is not None:
            self.collection._volumes.pop(self.name, None)


class FakeVolumes:
    def __init__(self, volumes):
        self._volumes = {v.name: v for v in volumes}
        for v in volumes:
            v.collection = self

    def list(self, **kwargs):
        return list(self._volumes.values())

    def get(self, name):
        try:
            return self._volumes[name]
        except KeyError:
            raise docker.errors.NotFound(f'No such volume: {name}')


class FakeClient:
    def __init__(self, images=(), containers=(), networks=(), volumes=()):
        self.images = FakeImages(images)
        self.containers = FakeContainers(containers)
        self.networks = FakeNetworks(networks)
        self.volumes = FakeVolumes(volumes)
