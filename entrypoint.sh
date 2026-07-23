#!/bin/sh
set -e

# Bind port. Honours PORT from the environment (docker-compose passes .env
# through), falling back to 8004 when it is not set.
PORT="${PORT:-8004}"

# Always bind all interfaces inside the container. HOST from .env is meant for
# running on the host directly, where 127.0.0.1 is correct; inside a container
# that would make the app unreachable from outside.
BIND_HOST=0.0.0.0

# A loopback address in a container points at the container itself, not at a
# database running on the host. This is the most common way to misconfigure
# DATABASE_URL, and the resulting connection timeout is not self-explanatory.
for var_pair in "DATABASE_URL=$DATABASE_URL" "REDIS_URL=$REDIS_URL"; do
    name="${var_pair%%=*}"
    value="${var_pair#*=}"
    case "$value" in
        *127.0.0.1*|*localhost*)
            echo "--------------------------------------------------------------"
            echo " WARNING: $name points at $value"
            echo " Inside a container that address is the container itself, so"
            echo " this will not reach a database running on your host."
            echo " Either leave $name blank in .env to use the bundled"
            echo " container, or set it to a reachable host."
            echo "--------------------------------------------------------------"
            ;;
    esac
done

# The bundled databases only exist when their compose profile is active. With
# COMPOSE_PROFILES blank, the app is created and they are not, and the only
# symptom is "Temporary failure in name resolution" from deep inside psycopg.
# Name the actual cause before that happens.
for var_pair in "DATABASE_URL=$DATABASE_URL:postgres" "REDIS_URL=$REDIS_URL:redis"; do
    name="${var_pair%%=*}"
    rest="${var_pair#*=}"
    value="${rest%:*}"
    host="${rest##*:}"
    case "$value" in
        *"@$host:"*|*"//$host:"*)
            if ! getent hosts "$host" > /dev/null 2>&1; then
                echo "--------------------------------------------------------------"
                echo " ERROR: $name points at the bundled '$host' container,"
                echo " but no such container exists on this network."
                echo " COMPOSE_PROFILES in .env decides which database containers"
                echo " are created. For the bundled ones, set:"
                echo "     COMPOSE_PROFILES=bundled-db"
                echo " Or point $name at a database you host yourself."
                echo "--------------------------------------------------------------"
                exit 1
            fi
            ;;
    esac
done

# Run Django migrations
python manage.py migrate --noinput

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
if User.objects.filter(username=username).exists():
    # Deliberately not updated. Re-applying the password on every start would
    # undo any change made through the admin. Say so, because otherwise a
    # changed DJANGO_SUPERUSER_PASSWORD silently has no effect and the login
    # page just says the credentials are wrong.
    print(f\"Superuser '{username}' already exists, leaving its password alone.\")
    print('  To change it: docker compose exec django python manage.py changepassword ' + username)
else:
    User.objects.create_superuser(
        username,
        os.environ['DJANGO_SUPERUSER_EMAIL'],
        os.environ['DJANGO_SUPERUSER_PASSWORD'],
    )
    print(f\"Created superuser '{username}'.\")
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
