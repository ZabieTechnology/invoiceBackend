# db/global_data_dal.py
from bson.objectid import ObjectId
import logging
from datetime import datetime

# Define collection names for global data
GLOBAL_COUNTRIES_COLLECTION = "regional_settings"
GLOBAL_INDUSTRIES_COLLECTION = "industry_classifications"
GLOBAL_DOC_RULES_COLLECTION = "document_rules" # Collection for Document Rules

# A constant for the name of the single document that holds all rules
GLOBAL_DOC_RULES_NAME = "global_document_rules"

logging.basicConfig(level=logging.INFO)

def _convert_id(doc):
    """Converts a document's _id from ObjectId to string."""
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

# --- Country DAL Functions ---

def get_all_countries(db_conn):
    """Fetches all documents from the global countries collection."""
    try:
        countries = list(db_conn[GLOBAL_COUNTRIES_COLLECTION].find({}))
        return [_convert_id(c) for c in countries]
    except Exception as e:
        logging.error(f"Error fetching all global countries: {e}")
        raise

def add_country(db_conn, data):
    """Adds a new country document."""
    try:
        result = db_conn[GLOBAL_COUNTRIES_COLLECTION].insert_one(data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error adding global country: {e}")
        raise

def update_country(db_conn, item_id, data):
    """Updates a specific country document by its ID."""
    try:
        result = db_conn[GLOBAL_COUNTRIES_COLLECTION].update_one(
            {"_id": ObjectId(item_id)},
            {"$set": data}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating global country {item_id}: {e}")
        raise

def delete_country(db_conn, item_id):
    """Deletes a specific country document by its ID."""
    try:
        result = db_conn[GLOBAL_COUNTRIES_COLLECTION].delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting global country {item_id}: {e}")
        raise

# --- Industry DAL Functions ---

def get_all_industries(db_conn):
    """Fetches all documents from the global industries collection."""
    try:
        industries = list(db_conn[GLOBAL_INDUSTRIES_COLLECTION].find({}))
        return [_convert_id(i) for i in industries]
    except Exception as e:
        logging.error(f"Error fetching all global industries: {e}")
        raise

def add_industry(db_conn, data):
    """Adds a new industry document."""
    try:
        result = db_conn[GLOBAL_INDUSTRIES_COLLECTION].insert_one(data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error adding global industry: {e}")
        raise

def update_industry(db_conn, item_id, data):
    """Updates a specific industry document by its ID."""
    try:
        result = db_conn[GLOBAL_INDUSTRIES_COLLECTION].update_one(
            {"_id": ObjectId(item_id)},
            {"$set": data}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating global industry {item_id}: {e}")
        raise

def delete_industry(db_conn, item_id):
    """Deletes a specific industry document by its ID."""
    try:
        result = db_conn[GLOBAL_INDUSTRIES_COLLECTION].delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting global industry {item_id}: {e}")
        raise

# --- Document Rules DAL Functions ---

def get_or_create_rules(db_conn):
    """
    Fetches the single global document containing all document rules.
    If it doesn't exist, it creates it with a default structure.
    """
    try:
        collection = db_conn[GLOBAL_DOC_RULES_COLLECTION]
        rules_doc = collection.find_one({"name": GLOBAL_DOC_RULES_NAME})
        if not rules_doc:
            logging.info("No global document rules found. Creating a default one.")
            default_doc = {
                "name": GLOBAL_DOC_RULES_NAME,
                "business_rules": [],
                "other_rules": [],
                "created_date": datetime.utcnow(),
                "updated_date": datetime.utcnow(),
                "updated_user": "System_Init"
            }
            collection.insert_one(default_doc)
            rules_doc = collection.find_one({"name": GLOBAL_DOC_RULES_NAME})

        return _convert_id(rules_doc)
    except Exception as e:
        logging.error(f"Error getting or creating document rules: {e}")
        raise

def save_rules(db_conn, data, user="System"):
    """
    Saves the entire single document of rules. It replaces the existing document.
    """
    try:
        collection = db_conn[GLOBAL_DOC_RULES_COLLECTION]

        # Prepare data for update, ensuring metadata is handled correctly.
        update_data = {k: v for k, v in data.items() if k not in ['_id', 'name', 'created_date']}
        update_data['updated_date'] = datetime.utcnow()
        update_data['updated_user'] = user

        result = collection.update_one(
            {"name": GLOBAL_DOC_RULES_NAME},
            {"$set": update_data}
        )
        # Returns True if a document was matched, regardless of modification.
        return result.matched_count > 0
    except Exception as e:
        logging.error(f"Error saving document rules: {e}")
        raise
