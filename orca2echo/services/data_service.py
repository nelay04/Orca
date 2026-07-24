"""Query helpers for the application's own tables.

Views and the WebSocket consumer go through this module rather than building
querysets inline, so the access patterns that matter for authorization and for
query count stay in one place.
"""

from typing import List, Optional, Tuple

from django.contrib.auth.models import User  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore
from django.db.models import OuterRef, Q, Subquery  # type: ignore

from ..models import FriendRequest, Friendship, Message, Profile


def get_profile(username: str) -> Optional[Profile]:
    """The profile for a username, or None."""
    if not username:
        return None
    return Profile.objects.filter(user__username=username).select_related("user").first()


def get_profile_by_email(email: str) -> Optional[Profile]:
    if not email:
        return None
    return Profile.objects.filter(user__email=email).select_related("user").first()


def find_profile(short_name: str, search_id: str) -> Optional[Profile]:
    """The profile addressed by a share link or QR code.

    Both halves are required: short_name alone is only a set of initials.
    """
    if not short_name or not search_id:
        return None
    return (
        Profile.objects.filter(short_name=short_name, search_id=str(search_id))
        .select_related("user")
        .first()
    )


def get_friend_request(sender: User, receiver: User) -> Optional[FriendRequest]:
    return FriendRequest.objects.filter(sender=sender, receiver=receiver).first()


def list_incoming_requests(user: User) -> List[FriendRequest]:
    """Active requests addressed to this user, with sender profiles attached.

    select_related pulls the sender and their profile in the same query. The
    previous implementation issued two point lookups per row.
    """
    return list(
        FriendRequest.objects.filter(receiver=user, is_active=True)
        .select_related("sender", "sender__profile")
        .order_by("-request_time")
    )


def list_outgoing_requests(user: User) -> List[FriendRequest]:
    return list(
        FriendRequest.objects.filter(sender=user, is_active=True)
        .select_related("receiver", "receiver__profile")
        .order_by("-request_time")
    )


def find_friendship(user_a: User, user_b: User) -> Optional[Friendship]:
    """The friendship between two users, in whichever order it was stored."""
    return Friendship.objects.filter(
        Q(user_1=user_a, user_2=user_b) | Q(user_1=user_b, user_2=user_a)
    ).first()


def resolve_friendship(public_id: str, user: User) -> Optional[Tuple[Friendship, User]]:
    """Resolve a conversation token to (friendship, other participant).

    Returns None unless `user` is actually a member. This is the chat
    authorization check: a decryptable token proves only that the app minted
    it at some point, never that the bearer belongs in the conversation.
    """
    if not public_id:
        return None
    try:
        friendship = (
            Friendship.objects.filter(public_id=public_id)
            .select_related("user_1", "user_2")
            .first()
        )
    except (ValidationError, ValueError, TypeError):
        # Not a UUID. A tampered or stale token, not an error worth raising.
        return None

    if friendship is None:
        return None

    other = friendship.other_user(user)
    if other is None:
        return None
    return friendship, other


def _friendships_for(user: User):
    return (
        Friendship.objects.filter(Q(user_1=user) | Q(user_2=user))
        .select_related("user_1", "user_1__profile", "user_2", "user_2__profile")
    )


def list_friends_by_recent_activity(user: User) -> List[dict]:
    """Friends ordered by their latest message, most recent first.

    Each entry carries the friendship (for its public_id), the friend's
    profile, and the last message, so the chat list renders without a
    per-friend query. The old ordering was on a friend_list.updated_at column
    that nothing ever wrote to.
    """
    # Subqueries rather than a follow-up query per friendship: the whole chat
    # list, preview text included, is one round trip. The preview text comes
    # back encrypted and is decrypted per entry below.
    from .auth_service import decrypt_message

    latest = Message.objects.filter(friendship=OuterRef("pk"), is_active=True).order_by("-created_at")
    friendships = _friendships_for(user).annotate(
        last_message_at=Subquery(latest.values("created_at")[:1]),
        last_message_text=Subquery(latest.values("message")[:1]),
        last_message_sender=Subquery(latest.values("sender_id")[:1]),
    )

    entries = []
    for friendship in friendships:
        friend = friendship.other_user(user)
        if friend is None:
            continue
        entries.append(
            {
                "friendship": friendship,
                "friend": friend,
                "profile": getattr(friend, "profile", None),
                "last_message_text": decrypt_message(friendship.last_message_text),
                "last_message_is_mine": friendship.last_message_sender == user.id,
                "last_message_at": friendship.last_message_at or friendship.created_at,
            }
        )

    entries.sort(key=lambda entry: entry["last_message_at"], reverse=True)
    return entries


def list_friends_alphabetically(user: User) -> List[dict]:
    """Friends ordered by full name, for the friends page."""
    entries = []
    for friendship in _friendships_for(user):
        friend = friendship.other_user(user)
        if friend is None:
            continue
        entries.append(
            {
                "friendship": friendship,
                "friend": friend,
                "profile": getattr(friend, "profile", None),
            }
        )

    entries.sort(key=lambda entry: (entry["profile"].full_name if entry["profile"] else ""))
    return entries


def get_messages(friendship: Friendship) -> List[Message]:
    """Every message in a conversation, oldest first.

    Trashed messages are kept in the list so history renders a tombstone in
    their place instead of collapsing the surrounding order. Only live bodies
    are decrypted; a trashed body is cleared and never handed to the template.
    """
    from .auth_service import decrypt_message

    messages = list(friendship.messages.select_related("sender"))
    for message in messages:
        if message.is_active:
            # Bodies are stored encrypted; decrypt in memory only for display.
            # These objects are never re-saved, so the ciphertext stays in the DB.
            message.message = decrypt_message(message.message)
        else:
            message.message = ""
    return messages


def trash_message(friendship: Friendship, user: User, public_id: str) -> Optional[Message]:
    """Soft-delete one of the user's own messages, or return None.

    The trash is scoped to a friendship the caller belongs to and to a message
    the caller sent: a member cannot trash the other participant's messages,
    and a valid conversation token is not on its own a claim to any message.
    The row survives; only is_active is flipped, so nothing is ever hard
    deleted and history keeps the message's position.
    """
    if not public_id:
        return None
    try:
        message = (
            friendship.messages.filter(public_id=public_id, sender=user, is_active=True)
            .select_related("sender")
            .first()
        )
    except (ValidationError, ValueError, TypeError):
        # Not a UUID. A tampered or stale reference, not an error worth raising.
        return None

    if message is None:
        return None

    message.is_active = False
    message.save(update_fields=["is_active"])
    return message
