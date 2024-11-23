from django.db import models # type: ignore
from django.db import models # type: ignore
from db_connection import db
from pymongo import errors # type: ignore
from bson import ObjectId # type: ignore
user_data = db['user_data']
user_profile = db['user_profile']
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
        short_name:str = None,
        search_id:int=None,
        is_active:bool=True,
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
    ):
        self.user_name = user_name
        self.profile_picture = profile_picture
        self.about = about


    def save(self):
        user_document = {  # Create a dictionary for the user data
            "user_name": self.user_name,
            "profile_picture": self.profile_picture,
            "about": self.about,
        }
        try:
            result = user_profile.insert_one(
                user_document
            )  # Insert the user document into the 'user_data' collection
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


