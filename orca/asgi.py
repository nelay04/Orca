"""
ASGI config for orca project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import orca2echo.routing # We'll create this next

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orca.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            orca2echo.routing.websocket_urlpatterns
        )
    ),
})
