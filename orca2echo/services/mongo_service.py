from db_connection import db
from pymongo import errors  # type: ignore
from bson import ObjectId  # type: ignore
from typing import Dict, Optional, Any, List

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






# These functions are for any collection except friend_list      >>>----------------------------------------------------------------->


def find_an_object(collection_name: str, search_criteria: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Search for an object in a MongoDB collection based on search criteria.

    Args:
        collection_name (str): The name of the collection to search in.
        search_criteria (dict): A dictionary containing the search criteria.

    Returns:
        dict | None: The found document or None if no document is found or an error occurs.

    Example:
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": "john_doe",
                "search_id": 12345,
            },
        )
    """
    try:
        # Access the specified collection
        user_data_collection = db[collection_name]  # Assumes `db` is a valid MongoDB database instance
        # Search using the provided criteria
        user = user_data_collection.find_one(search_criteria)
        return user
    except Exception as e:
        # Log the error (it's a good idea to use proper logging instead of print statements)
        print(f"Error occurred while searching for object in collection '{collection_name}': {e}")
        return None



def find_all_objects(collection_name: str, search_criteria: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Search for all objects in a MongoDB collection based on search criteria.

    Args:
        collection_name (str): The name of the collection to search in.
        search_criteria (dict): A dictionary containing the search criteria.

    Returns:
        list | None: A list of documents that match the criteria, or None if an error occurs.

    Example:
        all_users_data = find_all_objects(
            collection_name="user_data",
            search_criteria={
                "status": "active",
            },
        )
    """
    try:
        # Access the specified collection
        user_data_collection = db[collection_name]  # Assumes `db` is a valid MongoDB database instance
        # Search using the provided criteria
        users = user_data_collection.find(search_criteria)
        return list(users)  # Convert cursor to list and return
    except Exception as e:
        # Log the error
        print(f"Error occurred while searching for objects in collection '{collection_name}': {e}")
        return None



def update_objects(
    collection_name: str, 
    search_criteria: Dict[str, Any], 
    update_data: Dict[str, Any]
) -> Optional[str]:
    """
    Update fields of objects in a MongoDB collection based on search criteria.

    Args:
        collection_name (str): The name of the collection to search in.
        search_criteria (dict): A dictionary containing the search criteria.
        update_data (dict): A dictionary containing the fields to update.

    Returns:
        str | None: A success message if update is successful, or None if an error occurs.

    Example:
        update_result = update_objects(
            collection_name="user_data",
            search_criteria={"status": "active"},
            update_data={"status": "inactive"}
        )
    """
    try:
        # Access the specified collection
        collection = db[collection_name]  # Assumes `db` is a valid MongoDB database instance
        
        # Perform the update
        result = collection.update_many(  # Or use update_one if only one document needs updating
            search_criteria,
            {"$set": update_data}  # Use the $set operator to update specific fields
        )
        
        if result.matched_count > 0:
            return "Update successful"
        else:
            return "No documents matched the criteria"
    
    except Exception as e:
        # Log the error
        print(f"Error occurred while updating objects in collection '{collection_name}': {e}")
        return None




# These functions are only for friend_list      >>>----------------------------------------------------------------->


def find_friendship(user1: str, user2: str) -> Optional[Dict[str, Any]]:
    """
    Search for a friendship in the `friend_list` collection where `user1` and `user2`
    exist as either user1_id or user2_id, in any order.

    Args:
        user1 (str): The first user ID.
        user2 (str): The second user ID.

    Returns:
        dict | None: The found friendship document or None if no document is found.

    Example:
        friendship = find_friendship("user1_unique_id", "user2_unique_id")
    """
    try:
        friend_list_collection = db["friend_list"]  # Replace with your collection name

        # Search criteria for either (user1_id=user1 AND user2_id=user2) or (user1_id=user2 AND user2_id=user1)
        search_criteria = {
            "$or": [
                {"user_1": user1, "user_2": user2},
                {"user_1": user2, "user_2": user1},
            ]
        }

        # Find the friendship document
        friendship = friend_list_collection.find_one(search_criteria)
        return friendship
    except Exception as e:
        # Log the error (replace print with proper logging in production)
        print(f"Error occurred while searching for friendship: {e}")
        return None
    




def find_friend_users_alphabetically_sorted(user_name: str) -> List[dict]:
    """
    Find all users who are friends with the given user ID in the `friend_list` collection.
    Fetch the corresponding full name from the `user_data` collection and sort the friends by full name alphabetically.

    Args:
        user_name (str): The user ID to search for.

    Returns:
        List[dict]: A list of dictionaries containing the user IDs and full names of friends, sorted by full name.
    """
    try:
        friend_list_collection = db["friend_list"]  # Replace with your collection name
        user_data_collection = db["user_data"]  # Replace with your collection name for user data

        # Search criteria for user_name matching either user_1 or user_2
        search_criteria = {
            "$or": [
                {"user_1": user_name},
                {"user_2": user_name},
            ]
        }

        # Find all matching friendship documents
        friendships = friend_list_collection.find(search_criteria)

        # Extract the other user from each friendship
        friend_users = []
        for friendship in friendships:
            if friendship["user_1"] == user_name:
                friend_users.append(friendship["user_2"])
            elif friendship["user_2"] == user_name:
                friend_users.append(friendship["user_1"])

        # Fetch full name of each friend from the user_data collection
        friends_with_full_name = []
        for friend_id in friend_users:
            user_data = user_data_collection.find_one({"user_name": friend_id})
            if user_data:
                friends_with_full_name.append({
                    "user_name": friend_id,
                    "full_name": user_data["full_name"]
                })

        # Sort friends by full name alphabetically
        friends_with_full_name.sort(key=lambda x: x["full_name"])

        return friends_with_full_name

    except Exception as e:
        # Log the error (replace print with proper logging in production)
        print(f"Error occurred while searching for friends: {e}")
        return []


def find_friend_users_sorted_by_updated_at(user_name: str) -> List[dict]:
    """
    Find all users who are friends with the given user ID in the `friend_list` collection.
    Fetch the corresponding full name from the `user_data` collection and sort the friends by the `updated_at` field.

    Args:
        user_name (str): The user ID to search for.

    Returns:
        List[dict]: A list of dictionaries containing the user IDs and full names of friends, sorted by the `updated_at` field.
    """
    try:
        friend_list_collection = db["friend_list"]  # Replace with your collection name
        user_data_collection = db["user_data"]  # Replace with your collection name for user data

        # Search criteria for user_name matching either user_1 or user_2
        search_criteria = {
            "$or": [
                {"user_1": user_name},
                {"user_2": user_name},
            ]
        }

        # Find all matching friendship documents, sorted by updated_at field
        friendships = friend_list_collection.find(search_criteria).sort("updated_at", -1)  # -1 for descending order

        # Extract the other user from each friendship
        friend_users = []
        for friendship in friendships:
            if friendship["user_1"] == user_name:
                friend_users.append(friendship["user_2"])
            elif friendship["user_2"] == user_name:
                friend_users.append(friendship["user_1"])

        # Fetch full name of each friend from the user_data collection
        friends_with_full_name = []
        for friend_id in friend_users:
            user_data = user_data_collection.find_one({"user_name": friend_id})
            if user_data:
                friends_with_full_name.append({
                    "user_name": friend_id,
                    "full_name": user_data["full_name"]
                })

        return friends_with_full_name

    except Exception as e:
        # Log the error (replace print with proper logging in production)
        print(f"Error occurred while searching for friends: {e}")
        return []
