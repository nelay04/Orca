from django.db import models
from django.db import models
from db_connection import db, user_data
from pymongo import errors
from bson import ObjectId

# Create your models here.


# SQLite Class
class Otp(models.Model):
    otp = models.IntegerField(null=True)  # Store OTP, typically a 6-digit integer
    email = models.EmailField(null=True, blank=True)  # Store the email address


# Mongo Class
class UserData:
    def __init__(self, email: str = None, name: str = None, is_new_user: bool = True):
        self.email = email
        self.name = name
        self.is_new_user = is_new_user

    def save(self):
        user_document = {                                               # Create a dictionary for the user data
            "email": self.email,
            "name": self.name,
            "is_new_user": self.is_new_user,
        }
        try:
            result = user_data.insert_one(user_document)                # Insert the user document into the 'user_data' collection
            return result.inserted_id                                   # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False


    # result = UserData.update_field(email, "otp", otp)
    @classmethod
    def update_field(cls, email: str, field_name: str, new_value):      # Update a user document by email.
        if field_name == "email":
            raise ValueError("Email field cannot be modified.")
        result = user_data.update_one(
            {"email": email},                                           # Filter to find the document by email
            {
                "$set": {field_name: new_value}                         # Update operation to change the specified field
            },  
        )
        # Fetch the updated document to get its id
        if result.modified_count > 0:
            updated_document = user_data.find_one({"email": email})
            return updated_document.get("_id")
        else:
            return None


    @classmethod
    def get_user_by_email(cls, email):                                  # Retrieve a user document by email.
        try:
            return user_data.find_one({"email": email})
        except Exception as e:
            print(f"Error fetching user by email: {e}")
            return None


    @classmethod
    def get_user_by_id(cls, user_id):                                   # Retrieve a user document by id.
        try:
            user_id = ObjectId(user_id)
            return db["user_data"].find_one({"_id": user_id})
        except Exception as e:
            print(f"Error: {e}")
            return None
