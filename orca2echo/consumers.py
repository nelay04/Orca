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
    from .services.auth_service import encrypt_message

    receiver = User.objects.filter(username=receiver_username).first()
    if receiver is None:
        return None

    friendship = find_friendship(sender, receiver)
    if friendship is None:
        return None

    # created_at is set by the database. It used to arrive in the frame, so a
    # skewed clock or a crafted frame could reorder another user's history.
    # The body is encrypted at rest; the live relay still forwards the plaintext
    # already held in memory over the TLS-protected socket.
    return Message.objects.create(
        friendship=friendship,
        sender=sender,
        receiver=receiver,
        message=encrypt_message(message_text),
    )


@sync_to_async
def trash_message(user, conversation_id, message_public_id):
    """Soft-delete the user's own message, or return None when not permitted.

    Membership is resolved from the database on every frame, exactly as for a
    write: holding the conversation token is not membership, and being a member
    is not permission to trash the other participant's message.
    """
    from .services.data_service import resolve_friendship, trash_message as trash

    resolved = resolve_friendship(conversation_id, user)
    if resolved is None:
        return None

    friendship, _ = resolved
    return trash(friendship, user, message_public_id)


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

        # A trash frame carries an action and the target message's public_id
        # instead of a body; a send frame carries the body and the recipient.
        if data.get('action') == 'trash':
            await self.trash(data)
            return

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
                # The message's public_id, so the sender's optimistic bubble can
                # be tagged and later trashed, and history references stay stable.
                'message_id': str(saved.public_id),
                # Server-generated, so both participants see the same time.
                'formatted_time': format_display_time(saved.created_at),
            }
        )

    async def trash(self, data):
        """Handle a trash frame: soft-delete, then broadcast the tombstone."""
        message_id = data.get('message_id')
        if not message_id:
            return

        trashed = await trash_message(self.user, self.conversation_id, message_id)
        if trashed is None:
            logger.error(f"Refused trash from {self.user.username} for message {message_id}")
            await self.send(text_data=json.dumps({
                'error': 'Message could not be trashed.'
            }))
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_trashed',  # Calls message_trashed below.
                'message_id': str(trashed.public_id),
                'sender_username': self.user.username,
            }
        )

    # Receive message from room group and send to WebSocket client
    async def chat_message(self, event):
        # Send message to WebSocket (to the specific client this consumer instance represents)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_username': event['sender_username'],
            'message_id': event['message_id'],
            'formatted_time': event['formatted_time'],
        }))

    # Relay a trash to this client so its copy of the message becomes a tombstone.
    async def message_trashed(self, event):
        await self.send(text_data=json.dumps({
            'action': 'trashed',
            'message_id': event['message_id'],
            'sender_username': event['sender_username'],
        }))
