#!/bin/sh
set -eu

# Compose waits for PostgreSQL's health check; migrations then run before Django serves.
python manage.py migrate --noinput

exec "$@"
