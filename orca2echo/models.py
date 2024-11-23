from django.db import models  # type: ignore
from django.db import models  # type: ignore
from db_connection import db
from pymongo import errors  # type: ignore
from bson import ObjectId  # type: ignore

user_data = db["user_data"]
user_profile = db["user_profile"]
friend_request_list = db["friend_request_list"]
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
        request_count: int = None,
        is_accepted: bool = False,
        acceptance_count: int = None,
        is_rejected: bool = False,
        rejection_count: int = None,
        respond_time: str = None,
        is_cancelled: bool = False,
        cancellation_time: str = None,
    ):
        self.user_name_sender = user_name_sender
        self.user_name_receiver = user_name_receiver
        self.is_active = is_active
        self.request_time = request_time
        self.request_count = request_count
        self.is_accepted = is_accepted
        self.acceptance_count = acceptance_count
        self.is_rejected = is_rejected
        self.rejection_count = rejection_count
        self.respond_time = respond_time
        self.is_cancelled = is_cancelled
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
            "is_rejected": self.is_rejected,
            "rejection_count": self.rejection_count,
            "respond_time": self.respond_time,
            "is_cancelled": self.is_cancelled,
            "cancellation_time": self.cancellation_time,
        }
        try:
            result = friend_request_list.insert_one(
                friend_request_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False
