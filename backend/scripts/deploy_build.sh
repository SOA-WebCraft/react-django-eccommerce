#!/usr/bin/env sh
set -eu
python manage.py collectstatic --noinput
