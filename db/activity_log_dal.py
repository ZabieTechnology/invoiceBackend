# db/activity_log_dal.py
from datetime import datetime
import logging
from bson import ObjectId

from .database import mongo

ACTIVITY_LOG_COLLECTION = 'activity_log'

def add_activity(action_type, user, details, document_id=None, collection_name=None, tenant_id="default_tenant"):
    """
    Adds an entry to the activity log.

    Args:
        action_type (str): Type of action (e.g., "CREATE_GST_RATE", "UPDATE_CA_TAX_CESS").
        user (str): User performing the action.
        details (str): A descriptive string of the action.
        document_id (ObjectId or str, optional): The ID of the document affected.
        collection_name (str, optional): The name of the collection affected.
        tenant_id (str, optional): The tenant ID associated with the activity.
    """
    try:
        db = mongo.db
        log_entry = {
            "timestamp": datetime.utcnow(),
            "action_type": action_type,
            "user": user,
            "details": details,
            "tenant_id": tenant_id,
        }
        if document_id:
            log_entry["document_id"] = ObjectId(document_id) if not isinstance(document_id, ObjectId) else document_id
        if collection_name:
            log_entry["collection_name"] = collection_name

        result = db[ACTIVITY_LOG_COLLECTION].insert_one(log_entry)
        logging.info(f"Activity logged: {action_type} by {user}. Log ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error logging activity: {e}")
        # Decide if this error should propagate or just be logged
        # For now, just log it and don't let it break the main operation
