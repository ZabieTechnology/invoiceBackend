# db/quote_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# To get the next number, we import the settings DAL function
from .quote_settings_dal import get_quote_settings

QUOTE_COLLECTION = 'quotes'
QUOTE_SETTINGS_COLLECTION = 'quote_settings' # Define settings collection name

logging.basicConfig(level=logging.INFO)

def create_quote(db_conn, quote_data, user, tenant_id):
    """
    Creates a new quote in the database.
    It fetches the next quote number from settings and increments it.
    """
    try:
        quote_collection = db_conn[QUOTE_COLLECTION]
        settings_collection = db_conn[QUOTE_SETTINGS_COLLECTION]
        now = datetime.utcnow()

        # Get current quote settings to determine the next quote number
        settings = get_quote_settings(db_conn, tenant_id)
        next_number = settings.get('nextNumber', 1)
        prefix = settings.get('prefix', 'QUO-')

        # Prepare quote data
        quote_data['quoteNumber'] = f"{prefix}{next_number}"
        quote_data['tenant_id'] = tenant_id
        quote_data['created_date'] = now
        quote_data['updated_date'] = now
        quote_data['created_by'] = user
        quote_data.pop('_id', None)

        logging.info(f"Attempting to create quote for tenant '{tenant_id}' with number '{quote_data['quoteNumber']}'.")
        # Insert the new quote
        result = quote_collection.insert_one(quote_data)
        inserted_id = result.inserted_id
        logging.info(f"Successfully created quote '{quote_data['quoteNumber']}' with ID: {inserted_id} for tenant '{tenant_id}'.")

        # Atomically increment the next quote number in settings
        settings_collection.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"nextNumber": 1}}
        )
        logging.info(f"Incremented nextNumber for tenant '{tenant_id}'.")

        return inserted_id

    except Exception as e:
        logging.error(f"Error in create_quote for tenant {tenant_id}: {e}")
        raise


def get_all_quotes(db_conn, tenant_id, filters=None):
    """
    Fetches all quotes for a specific tenant.
    """
    try:
        quote_collection = db_conn[QUOTE_COLLECTION]
        query = {"tenant_id": tenant_id}
        if filters:
            query.update(filters)

        logging.info(f"Fetching all quotes for tenant '{tenant_id}' with filters: {filters}")
        quotes = list(quote_collection.find(query).sort("created_date", -1))

        for quote in quotes:
            quote['_id'] = str(quote['_id'])

        logging.info(f"Found {len(quotes)} quotes for tenant '{tenant_id}'.")
        return quotes
    except Exception as e:
        logging.error(f"Error in get_all_quotes for tenant {tenant_id}: {e}")
        raise

def get_quote_by_id(db_conn, quote_id, tenant_id):
    """
    Fetches a single quote by its ID.
    """
    try:
        quote_collection = db_conn[QUOTE_COLLECTION]
        logging.info(f"Fetching quote by ID '{quote_id}' for tenant '{tenant_id}'.")
        quote = quote_collection.find_one({"_id": ObjectId(quote_id), "tenant_id": tenant_id})
        if quote:
            quote['_id'] = str(quote['_id'])
            logging.info(f"Found quote ID '{quote_id}'.")
        else:
            logging.warning(f"Quote with ID '{quote_id}' not found for tenant '{tenant_id}'.")
        return quote
    except Exception as e:
        logging.error(f"Error in get_quote_by_id for ID {quote_id}: {e}")
        raise
