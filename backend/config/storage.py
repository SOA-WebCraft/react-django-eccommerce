import io
import posixpath
import time
from pathlib import PurePosixPath
from urllib.request import urlopen

import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.crypto import get_random_string
from django.utils.deconstruct import deconstructible


def _configure_cloudinary():
    if not settings.CLOUDINARY_URL:
        raise RuntimeError('CLOUDINARY_URL is required for Cloudinary storage.')
    cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL, secure=True)


@deconstructible
class PublicCloudinaryStorage(Storage):
    resource_type = 'image'
    delivery_type = 'upload'

    def _save(self, name, content):
        _configure_cloudinary()
        path = PurePosixPath(name)
        public_id = posixpath.join(
            str(path.parent) if str(path.parent) != '.' else '',
            f'{path.stem}-{get_random_string(10)}',
        ).strip('/')
        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            resource_type=self.resource_type,
            type=self.delivery_type,
            overwrite=False,
        )
        return f"{result['public_id']}.{result['format']}"

    def _open(self, name, mode='rb'):
        return File(urlopen(self.url(name), timeout=30), name=name)

    def delete(self, name):
        if not name:
            return
        _configure_cloudinary()
        public_id = str(PurePosixPath(name).with_suffix(''))
        cloudinary.uploader.destroy(
            public_id,
            resource_type=self.resource_type,
            type=self.delivery_type,
            invalidate=True,
        )

    def exists(self, name):
        if not name:
            return False
        _configure_cloudinary()
        public_id = str(PurePosixPath(name).with_suffix(''))
        try:
            cloudinary.api.resource(
                public_id,
                resource_type=self.resource_type,
                type=self.delivery_type,
            )
        except Exception:
            return False
        return True

    def size(self, name):
        _configure_cloudinary()
        public_id = str(PurePosixPath(name).with_suffix(''))
        return cloudinary.api.resource(
            public_id,
            resource_type=self.resource_type,
            type=self.delivery_type,
        )['bytes']

    def url(self, name):
        _configure_cloudinary()
        path = PurePosixPath(name)
        return cloudinary.utils.cloudinary_url(
            str(path.with_suffix('')),
            format=path.suffix.lstrip('.'),
            resource_type=self.resource_type,
            type=self.delivery_type,
            secure=True,
        )[0]


@deconstructible
class PrivateCloudinaryStorage(Storage):
    resource_type = 'raw'
    delivery_type = 'authenticated'

    def _save(self, name, content):
        _configure_cloudinary()
        path = PurePosixPath(name)
        public_id = posixpath.join(
            'invoices',
            str(path.parent) if str(path.parent) != '.' else '',
            f'{path.stem}-{get_random_string(10)}{path.suffix}',
        ).strip('/')
        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            resource_type=self.resource_type,
            type=self.delivery_type,
            overwrite=False,
        )
        return result['public_id']

    def private_url(self, name, expires_in=300):
        _configure_cloudinary()
        return cloudinary.utils.private_download_url(
            name,
            None,
            resource_type=self.resource_type,
            type=self.delivery_type,
            expires_at=int(time.time()) + expires_in,
        )

    def _open(self, name, mode='rb'):
        response = urlopen(self.private_url(name), timeout=30)
        return File(io.BytesIO(response.read()), name=PurePosixPath(name).name)

    def delete(self, name):
        if not name:
            return
        _configure_cloudinary()
        cloudinary.uploader.destroy(
            name,
            resource_type=self.resource_type,
            type=self.delivery_type,
            invalidate=True,
        )

    def exists(self, name):
        if not name:
            return False
        _configure_cloudinary()
        try:
            cloudinary.api.resource(
                name,
                resource_type=self.resource_type,
                type=self.delivery_type,
            )
        except Exception:
            return False
        return True

    def size(self, name):
        _configure_cloudinary()
        return cloudinary.api.resource(
            name,
            resource_type=self.resource_type,
            type=self.delivery_type,
        )['bytes']

    def url(self, name):
        return self.private_url(name)
