# db/dropdown_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

DROPDOWNS_COLLECTION = 'dropdown' # Use a consistent collection name

logging.basicConfig(level=logging.INFO)

def get_all_dropdowns(db_conn):
    """ Fetches all dropdown documents from the collection. """
    try:
        # No tenant_id filter
        return list(db_conn[DROPDOWNS_COLLECTION].find({}))
    except Exception as e:
        logging.error(f"Error fetching all dropdowns: {e}")
        raise

def get_dropdown_items_by_type(db_conn, dropdown_type):
    """ Fetches all dropdown items that match a specific type. """
    try:
        # Find all documents matching the type, without tenant_id
        cursor = db_conn[DROPDOWNS_COLLECTION].find({"type": dropdown_type})
        return list(cursor)
    except Exception as e:
        logging.error(f"Error fetching items for dropdown type '{dropdown_type}': {e}")
        raise

def add_dropdown(db_conn, data, user="System"):
    """ Adds a new global dropdown item. """
    try:
        now = datetime.utcnow()
        payload = {
            "type": data.get("type"),
            "sub_type": data.get("sub_type", ""),
            "value": data.get("value"),
            "label": data.get("label"),
            "pages_used": data.get("pages_used", []),
            "is_locked": data.get("is_locked", False),
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            # No tenant_id
        }
        if not payload["type"] or not payload["value"] or not payload["label"]:
            raise ValueError("Dropdown 'type', 'value', and 'label' are required.")

        result = db_conn[DROPDOWNS_COLLECTION].insert_one(payload)
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error adding global dropdown: {e}")
        raise

def update_dropdown(db_conn, item_id, data, user="System"):
    """ Updates a global dropdown item. """
    try:
        oid = ObjectId(item_id)
        fields_to_update = {
            k: v for k, v in data.items() if k in ['label', 'value', 'type', 'sub_type', 'pages_used', 'is_locked']
        }
        if not fields_to_update:
            return False

        update_payload = {
            "$set": {
                **fields_to_update,
                "updated_date": datetime.utcnow(),
                "updated_user": user,
            }
        }
        # No tenant_id in the query
        result = db_conn[DROPDOWNS_COLLECTION].update_one({"_id": oid}, update_payload)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating dropdown {item_id}: {e}")
        raise

def delete_dropdown(db_conn, item_id, user="System"):
    """ Deletes a global dropdown item. """
    try:
        oid = ObjectId(item_id)
        # No tenant_id in the query
        result = db_conn[DROPDOWNS_COLLECTION].delete_one({"_id": oid})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting dropdown {item_id}: {e}")
        raise

def get_dropdown_by_id(db_conn, item_id):
    """ Fetches a single dropdown by its ID. """
    try:
        oid = ObjectId(item_id)
        # No tenant_id
        return db_conn[DROPDOWNS_COLLECTION].find_one({"_id": oid})
    except Exception as e:
        logging.error(f"Error fetching dropdown by ID {item_id}: {e}")
        raise

def is_dropdown_locked(db_conn, item_id):
    """ Checks if a dropdown item is locked. """
    try:
        item = get_dropdown_by_id(db_conn, item_id)
        return item.get('is_locked', False) if item else False
    except Exception as e:
        logging.error(f"Error checking lock status for dropdown {item_id}: {e}")
        return False
