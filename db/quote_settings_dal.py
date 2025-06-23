# db/quote_settings_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# Use the collection name specified by the user
QUOTE_SETTINGS_COLLECTION = 'quote_settings'

logging.basicConfig(level=logging.INFO)

def get_quote_settings(db_conn, tenant_id):
    """
    Fetches quotation settings for a specific tenant from the database.
    If no settings exist for that tenant, it returns a default structure.

    :param db_conn: The database connection object.
    :param tenant_id: The identifier for the tenant whose settings are being fetched.
    :return: A dictionary containing the quotation settings.
    """
    if not tenant_id:
        logging.warning("get_quote_settings called without a tenant_id.")
        return None

    try:
        settings_collection = db_conn[QUOTE_SETTINGS_COLLECTION]
        settings = settings_collection.find_one({"tenant_id": tenant_id})

        if settings:
            settings.pop('_id', None)
            return settings
        else:
            return {
                "defaultTitle": "Quotation",
                "prefix": "QUO-",
                "nextNumber": 1,
                "validityDays": 30,
                "defaultTerms": "",
                "defaultNotes": "Thank you for your business!",
                "footerDetails": ""
            }
    except Exception as e:
        logging.error(f"Error fetching quote settings for tenant {tenant_id}: {e}")
        raise

def save_quote_settings(db_conn, settings_data, user, tenant_id):
    """
    Saves or updates the quotation settings for a specific tenant.

    :param db_conn: The database connection object.
    :param settings_data: A dictionary containing the settings to save.
    :param user: The user performing the action.
    :param tenant_id: The identifier for the tenant whose settings are being saved.
    :return: The result of the update_one operation from pymongo.
    """
    if not tenant_id:
        logging.warning("save_quote_settings called without a tenant_id.")
        return None

    try:
        settings_collection = db_conn[QUOTE_SETTINGS_COLLECTION]
        now = datetime.utcnow()

        # ** FIX **
        # Remove immutable fields from the data payload before saving.
        # This prevents the "conflict" error when updating an existing document.
        settings_data.pop('created_date', None)
        settings_data.pop('tenant_id', None)

        query = {"tenant_id": tenant_id}

        update_payload = {
            "$set": {**settings_data, "updated_date": now, "updated_by": user},
            "$setOnInsert": {"created_date": now, "tenant_id": tenant_id}
        }

        result = settings_collection.update_one(query, update_payload, upsert=True)

        return result
    except Exception as e:
        logging.error(f"Error saving quote settings for tenant {tenant_id}: {e}")
        raise
