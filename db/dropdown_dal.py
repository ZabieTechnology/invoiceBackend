# db/dropdown_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# Import the mongo instance from the central database module
from .database import mongo

DROPDOWN_COLLECTION = 'dropdown' # Define collection name constant

def get_dropdowns_paginated(page=1, limit=25, type_filter=None):
    """
    Fetches a paginated list of dropdown items from the database,
    optionally filtered by type. If type_filter is provided, pagination
    is effectively disabled by setting a very high limit to fetch all items of that type.

    Args:
        page (int): The page number to retrieve (used if no type_filter).
        limit (int): The number of items per page (used if no type_filter).
        type_filter (str, optional): The 'type' to filter dropdown items by.

    Returns:
        tuple: A tuple containing:
            - list: A list of dropdown item documents.
            - int: The total number of dropdown items matching the criteria.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db # Access the db instance correctly
        query = {}

        if type_filter:
            query['type'] = type_filter
            # If filtering by type, we usually want all items of that type.
            # Override pagination or set a high limit.
            # For simplicity, let's fetch all matching the type.
            # If you still need pagination with type filter, adjust logic here.
            dropdown_cursor = db[DROPDOWN_COLLECTION].find(query)
            dropdown_list = list(dropdown_cursor)
            total_items = len(dropdown_list) # Count of items matching the type
            return dropdown_list, total_items
        else:
            # Original pagination logic if no type_filter
            skip = (page - 1) * limit
            dropdown_cursor = db[DROPDOWN_COLLECTION].find(query).skip(skip).limit(limit)
            dropdown_list = list(dropdown_cursor)
            total_items = db[DROPDOWN_COLLECTION].count_documents(query)
            return dropdown_list, total_items

    except Exception as e:
        logging.error(f"Error fetching dropdowns: {e}")
        raise # Re-raise the exception to be handled by the caller

def add_dropdown(data, user="System"):
    """
    Adds a new dropdown item to the database.

    Args:
        data (dict): A dictionary containing 'type', 'value', and 'label'.
        user (str): The username performing the action.

    Returns:
        ObjectId: The ObjectId of the newly inserted document.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        insert_result = db[DROPDOWN_COLLECTION].insert_one({
            "type": data["type"],
            "value": data["value"],
            "label": data["label"],
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
        })
        return insert_result.inserted_id
    except Exception as e:
        logging.error(f"Error adding dropdown: {e}")
        raise

def update_dropdown(item_id, data, user="System"):
    """
    Updates an existing dropdown item in the database.

    Args:
        item_id (str): The string representation of the ObjectId to update.
        data (dict): A dictionary containing the fields to update (e.g., 'label').
        user (str): The username performing the action.

    Returns:
        int: The number of documents matched (should be 0 or 1).
    Raises:
        ValueError: If item_id is invalid.
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        oid = ObjectId(item_id) # Validate ObjectId format
        update_data = {
            "$set": {
                **{k: v for k, v in data.items() if k in ['label', 'value', 'type']},
                "updated_date": datetime.utcnow(),
                "updated_user": user,
            }
        }
        result = db[DROPDOWN_COLLECTION].update_one(
            {"_id": oid},
            update_data
        )
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating dropdown {item_id}: {e}")
        raise

def delete_dropdown(item_id):
    """
    Deletes a dropdown item from the database.

    Args:
        item_id (str): The string representation of the ObjectId to delete.

    Returns:
        int: The number of documents deleted (should be 0 or 1).
    Raises:
        ValueError: If item_id is invalid.
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        oid = ObjectId(item_id) # Validate ObjectId format
        result = db[DROPDOWN_COLLECTION].delete_one({"_id": oid})
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting dropdown {item_id}: {e}")
        raise

def get_dropdown_by_id(item_id):
    """
    Fetches a single dropdown item by its ID.

    Args:
        item_id (str): The string representation of the ObjectId.

    Returns:
        dict or None: The dropdown document if found, otherwise None.
    Raises:
        ValueError: If item_id is invalid.
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        oid = ObjectId(item_id)
        return db[DROPDOWN_COLLECTION].find_one({"_id": oid})
    except Exception as e:
        logging.error(f"Error fetching dropdown by ID {item_id}: {e}")
        raise
