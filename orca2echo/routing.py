from django.urls import re_path  # type: ignore
from . import consumers  # type: ignore

websocket_urlpatterns = [
    # The encrypted_conversation_id is captured from the URL.
    # Ensure the regex matches the format of your encrypted_conversation_id.
    # \w+ might be too restrictive if your ID contains non-alphanumeric characters like '-' or '='.
    # A more permissive regex like r'ws/chat/(?P<encrypted_conversation_id>[^/]+)/$' might be better.
    re_path(r'ws/chat/(?P<encrypted_conversation_id>[a-zA-Z0-9+/=_.-]+)/$', consumers.ChatConsumer.as_asgi()),
]