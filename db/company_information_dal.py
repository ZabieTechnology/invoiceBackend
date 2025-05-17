# db/company_information_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# Import the mongo instance from the central database module
from .database import mongo

COMPANY_INFO_COLLECTION = 'company_information' # Define collection name constant

def get_company_information():
    """
    Fetches the first company information document found.
    Assumes a single document for simplicity, or the relevant one based on context.

    Returns:
        dict or None: The company information document if found, otherwise None.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        # In a multi-tenant app, you would add a filter here, e.g., {'tenant_id': current_user_tenant}
        # find_one() returns None if no document matches
        return db[COMPANY_INFO_COLLECTION].find_one()
    except Exception as e:
        logging.error(f"Error fetching company information: {e}")
        raise # Re-raise the exception to be handled by the API layer

def create_or_update_company_information(data, user="System"):
    """
    Creates a new company information document or updates the existing one using upsert.
    Handles logo filename separately if provided.

    Args:
        data (dict): Dictionary containing company information fields.
        user (str): The user performing the action.

    Returns:
        ObjectId or None: The ObjectId of the inserted/updated document or None on failure.
    Raises:
        Exception: If there's an error during database interaction.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        # Add/update metadata fields directly in the input data dictionary
        data['updated_date'] = now
        data['updated_user'] = user

        # Prepare update data for $set, excluding _id if present in input `data`
        # This prevents trying to modify the immutable _id field during an update
        update_data = {k: v for k, v in data.items() if k != '_id'}

        # Use upsert=True:
        # - If a document matches the filter ({}), it gets updated with $set.
        # - If no document matches, a new one is inserted using fields from
        #   both $set and $setOnInsert.
        result = db[COMPANY_INFO_COLLECTION].update_one(
            {}, # Empty filter assumes updating the single document or the first one found.
                 # For multi-tenant, filter by tenant_id: {'tenant_id': tenant_id}
            {
                "$set": update_data,
                "$setOnInsert": {"created_date": now} # Set created_date only when inserting
            },
            upsert=True # This is the key option for create-or-update behavior
        )

        # Check the result of the upsert operation
        if result.upserted_id:
            # A new document was inserted
            logging.info(f"Company information created with ID: {result.upserted_id}")
            return result.upserted_id
        elif result.matched_count > 0:
            # An existing document was updated
            logging.info("Company information updated.")
            # If updated, we need to fetch the _id as update_one doesn't return it directly on update
            # We use the same filter used for the update to retrieve the updated document's ID
            updated_doc = db[COMPANY_INFO_COLLECTION].find_one({}, {"_id": 1})
            return updated_doc['_id'] if updated_doc else None # Return the ObjectId
        else:
             # This case should generally not happen with an empty filter and upsert=True,
             # unless there was a concurrent deletion or another issue.
             logging.warning("Company information update/insert operation had no effect (no match, no upsert).")
             return None

    except Exception as e:
        logging.error(f"Error creating/updating company information: {e}")
        raise # Re-raise the exception for the API layer to handle

# Note: The incorrect 'add_companyinformation' function with hardcoded data
# and syntax errors has been removed as it's redundant and non-functional.
# The 'create_or_update_company_information' function handles initial creation.

