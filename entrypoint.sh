#!/bin/sh
set -e

# Set default credentials (not secure)
DJANGO_SUPERUSER_USERNAME=admin-snow
DJANGO_SUPERUSER_EMAIL=snowflake.2k04@gmail.com
DJANGO_SUPERUSER_PASSWORD=admin-snow


# Run Django migrations
python manage.py migrate --noinput

# Collect static files into the STATIC_ROOT directory
python manage.py collectstatic --noinput


# Create a superuser with the specified username and password
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
"

# Start the app using Gunicorn and the WSGI server
# exec gunicorn --bind 0.0.0.0:8004 orca.wsgi:application

# exec uvicorn orca.asgi:application --reload --host 127.0.0.1 --port 8004
exec uvicorn orca.asgi:application --reload --host 0.0.0.0 --port 8004