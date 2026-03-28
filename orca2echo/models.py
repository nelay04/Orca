from django.db import models  # type: ignore
from db_connection import db
from pymongo import errors  # type: ignore
# from bson import ObjectId  # type: ignore

user_data = db["user_data"]
user_profile = db["user_profile"]
friend_request_list = db["friend_request_list"]
friend_list = db["friend_list"]
conversations = db["conversations"]
# Create your models here.


# SQLite Class
class Otp(models.Model):
    otp = models.IntegerField(null=True)  # Store OTP, typically a 6-digit integer
    email = models.EmailField(null=True, blank=True)  # Store the email address


# Mongo Classes
class UserData:
    def __init__(
        self,
        email: str = None,
        user_name: str = None,
        full_name: str = None,
        dob: str = None,
        gender: str = None,
        short_name: str = None,
        search_id: int = None,
        is_active: bool = True,
        is_new_user: bool = True,
    ):
        self.email = email
        self.user_name = user_name
        self.full_name = full_name
        self.dob = dob
        self.gender = gender
        self.short_name = short_name
        self.search_id = search_id
        self.is_active = is_active
        self.is_new_user = is_new_user

    def save(self):
        user_document = {  # Create a dictionary for the user data
            "email": self.email,
            "user_name": self.user_name,
            "full_name": self.full_name,
            "dob": self.dob,
            "gender": self.gender,
            "short_name": self.short_name,
            "search_id": self.search_id,
            "is_active": self.is_active,
            "is_new_user": self.is_new_user,
        }
        try:
            result = user_data.insert_one(
                user_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


class UserProfile:
    def __init__(
        self,
        user_name: str = None,
        profile_picture: str = None,
        about: str = "Orca, a platform where ideas flow effortlessly and every connection echoes with meaning.",
        qr_code: str = None,
    ):
        self.user_name = user_name
        self.profile_picture = profile_picture
        self.about = about
        self.qr_code = qr_code

    def save(self):
        user_document = {  # Create a dictionary for the user data
            "user_name": self.user_name,
            "profile_picture": self.profile_picture,
            "about": self.about,
            "qr_code": self.qr_code,
        }
        try:
            result = user_profile.insert_one(
                user_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


class FriendRequestList:
    def __init__(
        self,
        user_name_sender: str = None,
        user_name_receiver: str = None,
        is_active: bool = True,
        request_time: str = None,
        request_count: int = 0,
        is_accepted: bool = False,
        acceptance_count: int = 0,
        is_declined: bool = False,
        declination_count: int = 0,
        response_time: str = None,
        is_cancelled: bool = False,
        cancellation_count: int = 0,
        cancellation_time: str = None,
    ):
        self.user_name_sender = user_name_sender
        self.user_name_receiver = user_name_receiver
        self.is_active = is_active
        self.request_time = request_time
        self.request_count = request_count
        self.is_accepted = is_accepted
        self.acceptance_count = acceptance_count
        self.is_declined = is_declined
        self.declination_count = declination_count
        self.response_time = response_time
        self.is_cancelled = is_cancelled
        self.cancellation_count = cancellation_count
        self.cancellation_time = cancellation_time

    def save(self):
        friend_request_document = {  # Create a dictionary for the user data
            "user_name_sender": self.user_name_sender,
            "user_name_receiver": self.user_name_receiver,
            "is_active": self.is_active,
            "request_time": self.request_time,
            "request_count": self.request_count,
            "is_accepted": self.is_accepted,
            "acceptance_count": self.acceptance_count,
            "is_declined": self.is_declined,
            "declination_count": self.declination_count,
            "response_time": self.response_time,
            "is_cancelled": self.is_cancelled,
            "cancellation_count": self.cancellation_count,
            "cancellation_time": self.cancellation_time,
        }
        try:
            result = friend_request_list.insert_one(
                friend_request_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


class FriendList:
    def __init__(
        self,
        user_1: str = None,
        user_2: str = None,
        is_active: bool = True,
        created_at: str = None,
        updated_at: str = None,
        conversation_id: str = None,
        metadata: dict = None,    # Additional friendship details
    ):
        self.user_1 = user_1
        self.user_2 = user_2
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
        self.conversation_id = conversation_id
        self.metadata = metadata

    def save(self):
        friend_request_document = {  # Create a dictionary for the user data
            "user_1": self.user_1,
            "user_2": self.user_2,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "conversation_id": self.conversation_id,
            "metadata": self.metadata,
        }
        try:
            result = friend_list.insert_one(
                friend_request_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


class Conversation:
    def __init__(
        self,
        conversation_id: str = None,
        sender: str = None,
        receiver: str = None,
        message: str = None,
        is_active: bool = True,
        created_at: str = None,
        updated_at: str = None,
    ):
        self.conversation_id = conversation_id
        self.sender = sender
        self.receiver = receiver
        self.message = message
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def save(self):
        conversation_document = {  # Create a dictionary for the user data
            "conversation_id": self.conversation_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message": self.message,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        try:
            result = conversations.insert_one(
                conversation_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False