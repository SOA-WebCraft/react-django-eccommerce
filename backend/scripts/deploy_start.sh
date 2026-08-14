#!/usr/bin/env sh
set -eu
python manage.py migrate --noinput
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
