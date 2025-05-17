# db/vendor_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo # Import the mongo instance

VENDOR_COLLECTION = 'vendors'

def create_vendor(vendor_data, user="System"):
    """
    Creates a new vendor document in the database.

    Args:
        vendor_data (dict): A dictionary containing all vendor fields.
        user (str): The username of the user performing the action.

    Returns:
        ObjectId: The ObjectId of the newly inserted vendor document.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        # Add metadata
        vendor_data['created_date'] = now
        vendor_data['updated_date'] = now
        vendor_data['updated_user'] = user
        # Ensure _id is not part of the input data if it's a new creation
        vendor_data.pop('_id', None)

        result = db[VENDOR_COLLECTION].insert_one(vendor_data)
        logging.info(f"Vendor created with ID: {result.inserted_id} by {user}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating vendor: {e}")
        raise

def get_vendor_by_id(vendor_id):
    """
    Fetches a single vendor by their ObjectId.

    Args:
        vendor_id (str): The string representation of the ObjectId.

    Returns:
        dict or None: The vendor document if found, otherwise None.
    """
    try:
        db = mongo.db
        return db[VENDOR_COLLECTION].find_one({"_id": ObjectId(vendor_id)})
    except Exception as e:
        logging.error(f"Error fetching vendor by ID {vendor_id}: {e}")
        raise

def get_all_vendors(page=1, limit=25, filters=None):
    """
    Fetches a paginated list of vendors, optionally filtered.

    Args:
        page (int): The page number.
        limit (int): The number of items per page.
        filters (dict, optional): A dictionary of filters to apply. Defaults to None.

    Returns:
        tuple: A list of vendor documents and the total count of matching documents.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit

        vendors_cursor = db[VENDOR_COLLECTION].find(query).skip(skip).limit(limit)
        vendor_list = list(vendors_cursor)
        total_items = db[VENDOR_COLLECTION].count_documents(query)
        return vendor_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all vendors: {e}")
        raise # Or return ([], 0)

def update_vendor(vendor_id, update_data, user="System"):
    """
    Updates an existing vendor document.

    Args:
        vendor_id (str): The string ObjectId of the vendor to update.
        update_data (dict): A dictionary of fields to update.
        user (str): The username of the user performing the action.

    Returns:
        int: The number of documents matched (0 or 1).
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        # Ensure _id is not in update_data to prevent trying to change it
        update_data.pop('_id', None)
        
        # Add metadata for update
        update_payload = {
            "$set": {
                **update_data, # Spread the fields from update_data
                "updated_date": now,
                "updated_user": user
            }
        }

        result = db[VENDOR_COLLECTION].update_one(
            {"_id": ObjectId(vendor_id)},
            update_payload
        )
        if result.matched_count > 0:
            logging.info(f"Vendor {vendor_id} updated by {user}")
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating vendor {vendor_id}: {e}")
        raise

def delete_vendor_by_id(vendor_id):
    """
    Deletes a vendor by their ObjectId.

    Args:
        vendor_id (str): The string ObjectId of the vendor to delete.

    Returns:
        int: The number of documents deleted (0 or 1).
    """
    try:
        db = mongo.db
        result = db[VENDOR_COLLECTION].delete_one({"_id": ObjectId(vendor_id)})
        if result.deleted_count > 0:
            logging.info(f"Vendor {vendor_id} deleted.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting vendor {vendor_id}: {e}")
        raise
