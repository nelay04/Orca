#!/bin/sh
set -e

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
    echo "Run 'python manage.py createsuperuser' manually if you need admin access."
fi

# Start the app using Gunicorn and the WSGI server
# exec gunicorn --bind 0.0.0.0:8004 orca.wsgi:application

# exec uvicorn orca.asgi:application --reload --host 127.0.0.1 --port 8004
exec uvicorn orca.asgi:application --reload --host 0.0.0.0 --port 8004