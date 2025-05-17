# db/customer_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo # Import the mongo instance

CUSTOMER_COLLECTION = 'customers'

def create_customer(customer_data, user="System"):
    """
    Creates a new customer document in the database.

    Args:
        customer_data (dict): A dictionary containing all customer fields.
        user (str): The username of the user performing the action.

    Returns:
        ObjectId: The ObjectId of the newly inserted customer document.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        # Add metadata
        customer_data['created_date'] = now
        customer_data['updated_date'] = now
        customer_data['updated_user'] = user
        # Ensure _id is not part of the input data if it's a new creation
        customer_data.pop('_id', None)

        result = db[CUSTOMER_COLLECTION].insert_one(customer_data)
        logging.info(f"Customer created with ID: {result.inserted_id} by {user}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating customer: {e}")
        raise

def get_customer_by_id(customer_id):
    """
    Fetches a single customer by their ObjectId.

    Args:
        customer_id (str): The string representation of the ObjectId.

    Returns:
        dict or None: The customer document if found, otherwise None.
    """
    try:
        db = mongo.db
        return db[CUSTOMER_COLLECTION].find_one({"_id": ObjectId(customer_id)})
    except Exception as e:
        logging.error(f"Error fetching customer by ID {customer_id}: {e}")
        raise

def get_all_customers(page=1, limit=25, filters=None):
    """
    Fetches a paginated list of customers, optionally filtered.

    Args:
        page (int): The page number.
        limit (int): The number of items per page.
        filters (dict, optional): A dictionary of filters to apply. Defaults to None.

    Returns:
        tuple: A list of customer documents and the total count of matching documents.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit

        customers_cursor = db[CUSTOMER_COLLECTION].find(query).skip(skip).limit(limit)
        customer_list = list(customers_cursor)
        total_items = db[CUSTOMER_COLLECTION].count_documents(query)
        return customer_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all customers: {e}")
        raise # Or return ([], 0)

def update_customer(customer_id, update_data, user="System"):
    """
    Updates an existing customer document.

    Args:
        customer_id (str): The string ObjectId of the customer to update.
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

        result = db[CUSTOMER_COLLECTION].update_one(
            {"_id": ObjectId(customer_id)},
            update_payload
        )
        if result.matched_count > 0:
            logging.info(f"Customer {customer_id} updated by {user}")
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating customer {customer_id}: {e}")
        raise

def delete_customer_by_id(customer_id):
    """
    Deletes a customer by their ObjectId.

    Args:
        customer_id (str): The string ObjectId of the customer to delete.

    Returns:
        int: The number of documents deleted (0 or 1).
    """
    try:
        db = mongo.db
        result = db[CUSTOMER_COLLECTION].delete_one({"_id": ObjectId(customer_id)})
        if result.deleted_count > 0:
            logging.info(f"Customer {customer_id} deleted.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting customer {customer_id}: {e}")
        raise
