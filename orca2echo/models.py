from django.db import models
from db_connection import db, user_data
from pymongo import errors
from bson import ObjectId

# Create your models here.

class User:
    def __init__(self, email: str = None, name: str = None, otp: int = None, is_new_user : bool = True):
        self.email = email
        self.name = name
        self.otp = otp
        self.is_new_user = is_new_user

    def save(self):
    # Create a dictionary for the user data
        user_document = {
            "email": self.email,
            "name": self.name,
            "otp": self.otp,
            "is_new_user": self.is_new_user,
        }
        try:
            # Insert the user document into the 'user_data' collection
            result = user_data.insert_one(user_document)
            return result.inserted_id  # Return the ID of the newly inserted document
        except errors.DuplicateKeyError:
            return False
    
    @classmethod
    def update_field(cls, email: str, field_name: str, new_value):
        # Ensure that email is not modified
        if field_name == "email":
            raise ValueError("Email field cannot be modified.")

        # Update the specified field in the document with the given email
        result = user_data.update_one(
            {"email": email},  # Filter to find the document by email
            {"$set": {field_name: new_value}}  # Update operation to change the specified field
        )

        # Fetch the updated document to get its id
        if result.modified_count > 0:
            updated_document = user_data.find_one({"email": email})
            return updated_document.get("_id")  # Return the id of the updated document
        else:
            return None  # Return None if no document was updated

    
    @classmethod
    def get_user_by_email(cls, email):
        return db['user_data'].find_one({"email": email})


    @classmethod
    def get_user_by_id(cls, user_id):
        try:
            # Convert the string user_id to an ObjectId before querying
            user_id = ObjectId(user_id)
            return db['user_data'].find_one({"_id": user_id})
        except Exception as e:
            # Handle the error if ObjectId conversion fails
            print(f"Error: {e}")
            return None
