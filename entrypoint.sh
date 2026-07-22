#!/bin/sh
set -e

# Bind port. Honours PORT from the environment (docker-compose passes .env
# through), falling back to 8004 when it is not set.
PORT="${PORT:-8004}"

# Always bind all interfaces inside the container. HOST from .env is meant for
# running on the host directly, where 127.0.0.1 is correct; inside a container
# that would make the app unreachable from outside.
BIND_HOST=0.0.0.0

# Run Django migrations
python manage.py migrate --noinput

# Create the MongoDB indexes the app relies on. Non-fatal so the container
# still starts if MongoDB is not reachable yet.
python manage.py init_mongo || echo "init_mongo skipped: MongoDB not reachable"

# Collect static files into the STATIC_ROOT directory
python manage.py collectstatic --noinput

# Optionally create a superuser. Credentials come from the environment only,
# there are deliberately no defaults: a committed default password would give
# anyone who runs this image full admin access. Skipped unless all three are set.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username,
        os.environ['DJANGO_SUPERUSER_EMAIL'],
        os.environ['DJANGO_SUPERUSER_PASSWORD'],
    )
"
else
    echo "Superuser env vars not set, skipping superuser creation."
    echo "Run 'docker compose exec django python manage.py createsuperuser' if you need admin access."
fi

# The container binds all interfaces, so if this host is reachable from a
# network then DEBUG=True exposes the settings module to anyone who can
# trigger an error. Warn loudly rather than fail, since DEBUG is legitimate
# for a container running only on a developer machine.
if [ "$DEBUG" = "True" ]; then
    echo "=============================================================="
    echo " WARNING: DEBUG=True and the app is bound to ${BIND_HOST}."
    echo " Error pages will expose configuration to anyone who can reach"
    echo " this port. Set DEBUG=False before exposing it to a network."
    echo "=============================================================="
fi

echo "Starting ASGI server on ${BIND_HOST}:${PORT}"

# Uses the same management command documented in the README. Auto-reload is
# off: a container should not be watching files in a deployment.
exec python manage.py runasgi --host "$BIND_HOST" --port "$PORT" --no-reload
