from db_connection import db
from pymongo import errors  # type: ignore
from bson import ObjectId  # type: ignore


# result_id = update_fields(email="user@example.com",updates={"full_name": "Snow Flake", "dob": "2024-01-31"})
def update_fields_by_email(
    collection_name: str, email: str, updates: dict
):  # Update user document(s) by email with multiple fields.
    collection = db[collection_name]
    if "email" in updates:
        raise ValueError("Email field cannot be modified.")

    # Perform the update operation with the provided fields and values
    result = collection.update_one(
        {"email": email},  # Filter to find the document by email
        {"$set": updates},  # Update operation to change the specified fields
    )

    # Fetch the updated document to get its id if any modifications were made
    if result.modified_count > 0:
        updated_document = collection.find_one({"email": email})
        return updated_document.get("_id")
    else:
        return None


def update_fields_by_user_name(
    collection_name: str, user_name: str, updates: dict
):  # Update user document(s) by email with multiple fields.
    collection = db[collection_name]
    if "email" in updates:
        raise ValueError("Email field cannot be modified.")

    # Perform the update operation with the provided fields and values
    result = collection.update_one(
        {"user_name": user_name},  # Filter to find the document by email
        {"$set": updates},  # Update operation to change the specified fields
    )

    # Fetch the updated document to get its id if any modifications were made
    if result.modified_count > 0:
        updated_document = collection.find_one({"user_name": user_name})
        return updated_document.get("_id")
    else:
        return None


def get_user_data_by_email(collection_name: str, email: str):
    try:
        collection = db[collection_name]

        # Fetch the user document by email
        return collection.find_one({"email": email})
    except Exception as e:
        print(f"Error fetching user by email: {e}")
        return None


def get_user_data_by_user_name(collection_name: str, user_name: str):
    try:
        collection = db[collection_name]

        # Fetch the user document by email
        return collection.find_one({"user_name": user_name})
    except Exception as e:
        print(f"Error fetching user by user_name: {e}")
        return None


def get_user_by_id(
    collection_name: str, user_id: str
):  # Retrieve a user document by id.
    try:
        collection = db[collection_name]
        user_id = ObjectId(user_id)
        return collection.find_one({"_id": user_id})
    except Exception as e:
        print(f"Error: {e}")
        return None



def find_an_object(collection_name: str, search_criteria: dict):
    """
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": short_name,
                "search_id": id_number,
            },
        )
    """
    try:
        # Access the specified collection
        user_data_collection = db[collection_name]
        # Search using the provided criteria
        user = user_data_collection.find_one(search_criteria)
        return user
    except Exception as e:
        print(f"Error: {e}")
        return None

