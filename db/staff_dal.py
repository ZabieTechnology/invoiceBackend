# db/staff_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo # Import the mongo instance

STAFF_COLLECTION = 'staff'

def create_staff_member(staff_data, user="System"):
    """
    Creates a new staff member document in the database.

    Args:
        staff_data (dict): A dictionary containing all staff fields.
        user (str): The username of the user performing the action.

    Returns:
        ObjectId: The ObjectId of the newly inserted staff document.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        # Add metadata
        staff_data['created_date'] = now
        staff_data['updated_date'] = now
        staff_data['updated_user'] = user
        staff_data.pop('_id', None) # Ensure _id is not part of input for new creation

        result = db[STAFF_COLLECTION].insert_one(staff_data)
        logging.info(f"Staff member created with ID: {result.inserted_id} by {user}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating staff member: {e}")
        raise

def get_staff_member_by_id(staff_id):
    """
    Fetches a single staff member by their ObjectId.

    Args:
        staff_id (str): The string representation of the ObjectId.

    Returns:
        dict or None: The staff document if found, otherwise None.
    """
    try:
        db = mongo.db
        return db[STAFF_COLLECTION].find_one({"_id": ObjectId(staff_id)})
    except Exception as e:
        logging.error(f"Error fetching staff member by ID {staff_id}: {e}")
        raise

def get_all_staff_members(page=1, limit=25, filters=None):
    """
    Fetches a paginated list of staff members, optionally filtered.

    Args:
        page (int): The page number.
        limit (int): The number of items per page.
        filters (dict, optional): A dictionary of filters to apply. Defaults to None.

    Returns:
        tuple: A list of staff documents and the total count of matching documents.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit

        staff_cursor = db[STAFF_COLLECTION].find(query).skip(skip).limit(limit)
        staff_list = list(staff_cursor)
        total_items = db[STAFF_COLLECTION].count_documents(query)
        return staff_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all staff members: {e}")
        raise

def update_staff_member(staff_id, update_data, user="System"):
    """
    Updates an existing staff member document.

    Args:
        staff_id (str): The string ObjectId of the staff member to update.
        update_data (dict): A dictionary of fields to update.
        user (str): The username of the user performing the action.

    Returns:
        int: The number of documents matched (0 or 1).
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        update_data.pop('_id', None)
        
        update_payload = {
            "$set": {
                **update_data,
                "updated_date": now,
                "updated_user": user
            }
        }
        result = db[STAFF_COLLECTION].update_one(
            {"_id": ObjectId(staff_id)},
            update_payload
        )
        if result.matched_count > 0:
            logging.info(f"Staff member {staff_id} updated by {user}")
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating staff member {staff_id}: {e}")
        raise

def delete_staff_member_by_id(staff_id):
    """
    Deletes a staff member by their ObjectId.

    Args:
        staff_id (str): The string ObjectId of the staff member to delete.

    Returns:
        int: The number of documents deleted (0 or 1).
    """
    try:
        db = mongo.db
        result = db[STAFF_COLLECTION].delete_one({"_id": ObjectId(staff_id)})
        if result.deleted_count > 0:
            logging.info(f"Staff member {staff_id} deleted.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting staff member {staff_id}: {e}")
        raise
