import json
import logging

# sync_to_async lets the synchronous Django/PyMongo calls run from the
# async consumer without blocking the event loop.
from asgiref.sync import sync_to_async  # type: ignore
from channels.generic.websocket import AsyncWebsocketConsumer  # type: ignore

logger = logging.getLogger(__name__)


# Example of adapting your existing synchronous functions for async context
@sync_to_async
def save_message_to_db(conversation_id, sender_username, message_text, receiver_username, created_at_str):
    from .models import Conversation
    # Your Conversation class and its save method are used here.
    # Ensure it's imported correctly and works as expected.
    conversation_document = Conversation(
        conversation_id=conversation_id,
        sender=sender_username,
        message=message_text,
        receiver=receiver_username,
        created_at=created_at_str,  # Ensure your save method handles this string or parse it
    )
    return conversation_document.save()  # This should return True/False or raise error


@sync_to_async
def get_conv_id(user1, user2):
    from .services.mongo_service import get_conversation_id_for_friendship
    return get_conversation_id_for_friendship(user1, user2)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # The encrypted_conversation_id is passed in the URL by the frontend
        # e.g., ws://localhost:8000/ws/chat/{encrypted_conversation_id}/
        self.encrypted_conversation_id = self.scope['url_route']['kwargs']['encrypted_conversation_id']
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Use a sanitized version of the encrypted_conversation_id for the room group name
        # Replacing characters that might be problematic in group names.
        safe_group_id_part = self.encrypted_conversation_id.replace('=', '_').replace('/', '_').replace('+', '_')
        self.room_group_name = f"chat_{safe_group_id_part}"

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
        message = data['message']
        friend_id = data['friend_id']  # This is the receiver's username
        created_at_str = data['created_at']  # DD-MM-YYYY HH:MM:SS:ms (from client)
        formatted_time = data['formatted_time']  # h:mm am/pm (from client, for display)

        sender_username = self.user.username

        if not message or not friend_id:
            logger.error("Missing message or friend_id in WebSocket message")
            return

        # Get the actual conversation ID for database saving
        # This uses the same logic as your HTTP views.
        conversation_id_actual = await get_conv_id(sender_username, friend_id)
        if not conversation_id_actual:
            logger.error(f"Could not determine conversation ID between {sender_username} and {friend_id}")
            # Optionally send an error back to the client
            await self.send(text_data=json.dumps({
                'error': 'Failed to identify conversation.'
            }))
            return

        # Save message to database
        save_successful = await save_message_to_db(
            conversation_id_actual,
            sender_username,
            message,
            friend_id,  # receiver
            created_at_str
        )

        if not save_successful:
            logger.error(f"Failed to save message from {sender_username} to {friend_id} for conversation {conversation_id_actual}")
            # Optionally send an error back to the client
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
                'formatted_time': formatted_time,  # Use client-generated display time
                'created_at': created_at_str  # Original full timestamp
            }
        )

    # Receive message from room group and send to WebSocket client
    async def chat_message(self, event):
        message = event['message']
        sender_username = event['sender_username']
        formatted_time = event['formatted_time']

        # Send message to WebSocket (to the specific client this consumer instance represents)
        await self.send(text_data=json.dumps({
            'message': message,
            'sender_username': sender_username,
            'formatted_time': formatted_time,
            # 'is_sender' could be determined client-side by comparing event.sender_username with currentUsername
        }))
