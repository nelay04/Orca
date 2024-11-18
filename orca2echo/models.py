from django.db import models # type: ignore
from django.db import models # type: ignore
from db_connection import db
from pymongo import errors # type: ignore
from bson import ObjectId # type: ignore
user_data = db['user_data']
profile_picture = db['profile_picture']
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
        is_new_user: bool = True,
    ):
        self.email = email
        self.user_name = user_name
        self.full_name = full_name
        self.dob = dob
        self.gender = gender
        self.is_new_user = is_new_user


    def save(self):
        user_document = {  # Create a dictionary for the user data
            "email": self.email,
            "user_name": self.user_name,
            "full_name": self.full_name,
            "dob": self.dob,
            "gender": self.gender,
            "is_new_user": self.is_new_user,
        }
        try:
            result = user_data.insert_one(
                user_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False

class ProfilePicture:
    def __init__(
        self,
        user_name: str = None,
        profile_picture: str = None,
    ):
        self.user_name = user_name
        self.profile_picture = profile_picture


    def save(self):
        user_document = {  # Create a dictionary for the user data
            "user_name": self.user_name,
            "profile_picture": self.profile_picture,
        }
        try:
            result = profile_picture.insert_one(
                user_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


