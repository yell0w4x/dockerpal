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


class FakeClient:
    def __init__(self, images=()):
        self.images = FakeImages(images)
