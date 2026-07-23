import json
import logging

# sync_to_async lets the synchronous Django ORM calls run from the
# async consumer without blocking the event loop.
from asgiref.sync import sync_to_async  # type: ignore
from channels.generic.websocket import AsyncWebsocketConsumer  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from django.utils import timezone  # type: ignore

logger = logging.getLogger(__name__)


@sync_to_async
def save_message(sender, receiver_username, message_text):
    """Persist a message, or return None when the two users are not friends.

    Membership is resolved from the database on every frame. A client that
    holds a conversation token is not thereby a member of the conversation.
    """
    from .models import Message
    from .services.data_service import find_friendship

    receiver = User.objects.filter(username=receiver_username).first()
    if receiver is None:
        return None

    friendship = find_friendship(sender, receiver)
    if friendship is None:
        return None

    # created_at is set by the database. It used to arrive in the frame, so a
    # skewed clock or a crafted frame could reorder another user's history.
    return Message.objects.create(
        friendship=friendship,
        sender=sender,
        receiver=receiver,
        message=message_text,
    )


def format_display_time(moment):
    """The h:mm am/pm label shown next to a bubble, in the project timezone."""
    local = timezone.localtime(moment)
    return local.strftime("%I:%M %p").lstrip("0").lower()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # The conversation id is passed in the URL by the frontend
        # e.g., ws://localhost:8000/ws/chat/{conversation_id}/
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f"chat_{self.conversation_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        logger.info(f"CONNECT    - User: {self.user.username}  Room: {self.room_group_name}")

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f"DISCONNECT - User: {self.user.username}  Room: {self.room_group_name}")

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        friend_id = data.get('friend_id')  # This is the receiver's username

        sender_username = self.user.username

        if not message or not friend_id:
            logger.error("Missing message or friend_id in WebSocket message")
            return

        # Save message to database. This also resolves the friendship, so a
        # None result means the pair are not friends and nothing is broadcast.
        saved = await save_message(self.user, friend_id, message)

        if saved is None:
            logger.error(f"Refused message from {sender_username} to {friend_id}")
            await self.send(text_data=json.dumps({
                'error': 'Message could not be saved.'
            }))
            return

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',  # This will call the chat_message method below
                'message': message,
                'sender_username': sender_username,
                # Server-generated, so both participants see the same time.
                'formatted_time': format_display_time(saved.created_at),
            }
        )

    # Receive message from room group and send to WebSocket client
    async def chat_message(self, event):
        # Send message to WebSocket (to the specific client this consumer instance represents)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_username': event['sender_username'],
            'formatted_time': event['formatted_time'],
        }))
