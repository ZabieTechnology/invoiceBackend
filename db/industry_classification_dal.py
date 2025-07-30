# src/db/industry_classification_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
from .activity_log_dal import add_activity # Import the activity log function

CLASSIFICATION_COLLECTION = 'industry_classifications'
GLOBAL_CLASSIFICATION_DOC_NAME = "global_industry_classifications"

logging.basicConfig(level=logging.INFO)

def get_all_classifications(db_conn):
    """
    Fetches the single global document of classifications.
    If it doesn't exist, it creates one with an empty list.
    """
    try:
        doc = db_conn[CLASSIFICATION_COLLECTION].find_one({"name": GLOBAL_CLASSIFICATION_DOC_NAME})

        if not doc:
            logging.warning("No global classification document found. Creating a new one.")
            default_data = {
                "name": GLOBAL_CLASSIFICATION_DOC_NAME,
                "classifications": [],
                "created_date": datetime.utcnow(),
                "updated_date": datetime.utcnow(),
                "updated_user": "System"
            }
            db_conn[CLASSIFICATION_COLLECTION].insert_one(default_data)
            doc = default_data

        doc['_id'] = str(doc.get('_id'))
        for item in doc.get('classifications', []):
            item['_id'] = str(item.get('_id'))

        return doc.get('classifications', [])
    except Exception as e:
        logging.error(f"Error fetching/creating global classifications: {e}")
        raise

def add_classification(db_conn, data, user):
    """Adds a single classification to the global document and logs the activity."""
    try:
        new_item = {
            "_id": ObjectId(),
            "industry": data.get("industry"),
            "natureOfBusiness": data.get("natureOfBusiness"),
            "code": data.get("code"),
            "isLocked": data.get("isLocked", False)
        }

        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"name": GLOBAL_CLASSIFICATION_DOC_NAME},
            {
                "$push": {"classifications": new_item},
                "$set": {"updated_date": datetime.utcnow(), "updated_user": user}
            },
            upsert=True
        )

        if result.modified_count > 0 or result.upserted_id:
            # Log the activity for the global context
            add_activity("CREATE_INDUSTRY_CLASSIFICATION", user, f"Created new global industry classification: '{new_item['industry']}'", new_item['_id'], CLASSIFICATION_COLLECTION, "global")
            return str(new_item['_id'])
        return None
    except Exception as e:
        logging.error(f"Error adding global classification: {e}")
        raise

def update_classification(db_conn, item_id, data, user):
    """Updates a single classification in the global document and logs the activity."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"name": GLOBAL_CLASSIFICATION_DOC_NAME, "classifications._id": ObjectId(item_id)},
            {
                "$set": {
                    "classifications.$.industry": data.get("industry"),
                    "classifications.$.natureOfBusiness": data.get("natureOfBusiness"),
                    "classifications.$.code": data.get("code"),
                    "classifications.$.isLocked": data.get("isLocked"),
                    "updated_date": datetime.utcnow(),
                    "updated_user": user
                }
            }
        )
        if result.modified_count > 0:
            # Log the activity for the global context
            add_activity("UPDATE_INDUSTRY_CLASSIFICATION", user, f"Updated global industry classification ID: '{item_id}'", ObjectId(item_id), CLASSIFICATION_COLLECTION, "global")
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating global classification {item_id}: {e}")
        raise

def delete_classification(db_conn, item_id, user):
    """Deletes a single classification from the global document and logs the activity."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"name": GLOBAL_CLASSIFICATION_DOC_NAME},
            {
                "$pull": {"classifications": {"_id": ObjectId(item_id)}},
                "$set": {"updated_date": datetime.utcnow(), "updated_user": user}
            }
        )
        if result.modified_count > 0:
            # Log the activity for the global context
            add_activity("DELETE_INDUSTRY_CLASSIFICATION", user, f"Deleted global industry classification ID: '{item_id}'", ObjectId(item_id), CLASSIFICATION_COLLECTION, "global")
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error deleting global classification {item_id}: {e}")
        raise
