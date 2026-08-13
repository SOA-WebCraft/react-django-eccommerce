from .settings import *  # noqa: F403


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': STORAGES['staticfiles'],  # noqa: F405
}
CLOUDINARY_URL = ''
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
