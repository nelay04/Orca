import uuid

from django.contrib.auth.models import User  # type: ignore
from django.db import models  # type: ignore

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
    ("prefer_not_to_say", "Prefer not to say"),
]

DEFAULT_ABOUT = (
    "Orca, a platform where ideas flow effortlessly and every connection echoes with meaning."
)


class Otp(models.Model):
    otp = models.IntegerField(null=True)  # Store OTP, typically a 6-digit integer
    email = models.EmailField(null=True, blank=True)  # Store the email address
    # created_at drives both expiry and the resend throttle.
    created_at = models.DateTimeField(auto_now=True)
    # Number of failed verification attempts against this OTP.
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return f"OTP for {self.email}"


class Profile(models.Model):
    """Everything the app knows about a user beyond their auth row.

    The identity fields and the picture used to be two MongoDB collections
    joined on the username string. They were always one-to-one, so they are a
    single table here, hanging off auth_user by foreign key. There is no
    user_name or email column: User.username and User.email are the only copy.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    full_name = models.CharField(max_length=150, blank=True)
    # Initials, for example "NK". Not unique on its own: it is only an address
    # when paired with search_id.
    short_name = models.CharField(max_length=16, blank=True)
    # 20 digits, generated from a timestamp plus random padding. Stored as text
    # because it is an identifier rather than a quantity.
    search_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    gender = models.CharField(max_length=32, choices=GENDER_CHOICES, blank=True)
    dob = models.DateField(null=True, blank=True)

    about = models.TextField(default=DEFAULT_ABOUT, blank=True)
    # Base64 PNG held inline, as it was in MongoDB.
    profile_picture = models.TextField(blank=True)
    qr_code = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    # True between the OTP being verified and the signup form being submitted.
    is_new_user = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # The profile lookup behind every share link and QR code.
            models.Index(fields=["short_name", "search_id"]),
        ]

    def __str__(self):
        return self.full_name or self.user.username


class FriendRequest(models.Model):
    """One row per direction of a request, reused across its whole lifecycle.

    Re-sending after a cancel or decline reactivates this row and bumps a
    counter rather than inserting a second one, which is what the unique
    constraint on the pair enforces.
    """

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_friend_requests")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_friend_requests")

    is_active = models.BooleanField(default=True)
    request_time = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0)

    is_accepted = models.BooleanField(default=False)
    acceptance_count = models.PositiveIntegerField(default=0)

    is_declined = models.BooleanField(default=False)
    declination_count = models.PositiveIntegerField(default=0)
    response_time = models.DateTimeField(null=True, blank=True)

    is_cancelled = models.BooleanField(default=False)
    cancellation_count = models.PositiveIntegerField(default=0)
    cancellation_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sender", "receiver"], name="unique_friend_request_pair"),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"


class Friendship(models.Model):
    """An accepted friendship, which is also the conversation between two users.

    public_id is what travels in chat URLs, inside a Fernet token. It replaced
    a "<accepter>_<sender>" string whose ordering every caller had to resolve
    before it could be used. A random UUID has no ordering to get wrong and
    leaks no usernames if a token is ever decrypted.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships_as_user_1")
    user_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships_as_user_2")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_1", "user_2"], name="unique_friendship_pair"),
        ]

    def other_user(self, user):
        """The participant who is not `user`, or None when `user` is not a member.

        Chat authorization depends on this returning None for non-members, so
        it compares ids rather than assuming the caller is in the friendship.
        """
        if self.user_1_id == user.id:
            return self.user_2
        if self.user_2_id == user.id:
            return self.user_1
        return None

    def __str__(self):
        return f"{self.user_1.username} & {self.user_2.username}"


class Message(models.Model):
    # What travels to the client to name a single message, in the same spirit as
    # Friendship.public_id: a random UUID leaks no sequential id and no count.
    # The trash action references a message by this rather than by primary key.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    friendship = models.ForeignKey(Friendship, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")

    message = models.TextField()
    # False once the sender trashes the message. The row is kept so history
    # renders a tombstone in its place; the body is never shown again.
    is_active = models.BooleanField(default=True)
    # Set the first time the sender edits the message. Non-null drives the
    # "Edited" tag; the ordering stays on created_at so an edit never moves the
    # message. Each edit also appends the prior body to MessageHistory.
    edited_at = models.DateTimeField(null=True, blank=True)
    # Server-generated. The browser used to supply this as a formatted string,
    # so clock skew or a crafted WebSocket frame could reorder history.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["friendship", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender.username}: {self.message[:40]}"


class MessageHistory(models.Model):
    """A superseded version of a message body, kept when the sender edits it.

    Before a Message row's body is overwritten by an edit, its current
    (Fernet-encrypted) body is copied here with the time it was replaced. The
    live Message row therefore holds only the latest text, while the full trail
    of prior versions survives here. Rows are never edited or shown to the other
    participant; they exist so nothing a user typed is silently lost.
    """

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="history")
    # The prior body, stored encrypted exactly as it was on the Message row.
    previous_message = models.TextField()
    # When this version was superseded (i.e. when the edit that replaced it ran).
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"history of message {self.message_id} at {self.created_at}"
