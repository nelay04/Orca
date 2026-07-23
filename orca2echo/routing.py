from django.urls import re_path  # type: ignore
from . import consumers  # type: ignore

websocket_urlpatterns = [
    # The conversation id is the friendship's public_id, a UUID. It names the
    # Channels group, so it only has to be stable and opaque, not secret:
    # membership is checked against the database on every message.
    re_path(r'ws/chat/(?P<conversation_id>[0-9a-fA-F-]+)/$', consumers.ChatConsumer.as_asgi()),
]
