# db/dropdown_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
from .activity_log_dal import add_activity

DROPDOWN_COLLECTION = 'dropdown'

logging.basicConfig(level=logging.INFO)

def get_dropdowns_paginated(db_conn, page=1, limit=25, type_filter=None, tenant_id="default_tenant"):
    try:
        query = {"tenant_id": tenant_id}
        if type_filter:
            query['type'] = type_filter

        sort_order = [("type", 1), ("sub_type", 1), ("label", 1)]

        if limit == -1: # Fetch all items
             dropdown_cursor = db_conn[DROPDOWN_COLLECTION].find(query).sort(sort_order)
             dropdown_list = list(dropdown_cursor)
             total_items = len(dropdown_list)
             return dropdown_list, total_items
        else:
            skip = (page - 1) * limit
            dropdown_cursor = db_conn[DROPDOWN_COLLECTION].find(query).sort(sort_order).skip(skip).limit(limit)
            dropdown_list = list(dropdown_cursor)
            total_items = db_conn[DROPDOWN_COLLECTION].count_documents(query)
            return dropdown_list, total_items
    except Exception as e:
        logging.error(f"Error fetching dropdowns for tenant {tenant_id}: {e}")
        raise

def add_dropdown(db_conn, data, user="System", tenant_id="default_tenant"):
    try:
        now = datetime.utcnow()
        payload = {
            "type": data.get("type"),
            "sub_type": data.get("sub_type", ""), # Add sub_type
            "value": data.get("value"),
            "label": data.get("label"),
            "pages_used": data.get("pages_used", []), # Add pages_used
            "is_locked": data.get("is_locked", False), # Add is_locked
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }
        if not payload["type"] or not payload["value"] or not payload["label"]:
            raise ValueError("Dropdown 'type', 'value', and 'label' are required.")

        insert_result = db_conn[DROPDOWN_COLLECTION].insert_one(payload)

        add_activity(
            action_type="CREATE_DROPDOWN_ITEM",
            user=user,
            details=f"Added dropdown: Type='{payload['type']}', Label='{payload['label']}'",
            document_id=insert_result.inserted_id,
            collection_name=DROPDOWN_COLLECTION,
            tenant_id=tenant_id
        )
        return insert_result.inserted_id
    except Exception as e:
        logging.error(f"Error adding dropdown for tenant {tenant_id}: {e}")
        raise

def update_dropdown(db_conn, item_id, data, user="System", tenant_id="default_tenant"):
    try:
        oid = ObjectId(item_id)

        fields_to_update = {
            k: v for k, v in data.items() if k in ['label', 'value', 'type', 'sub_type', 'pages_used', 'is_locked']
        }

        if not fields_to_update:
            return 0

        update_payload = {
            "$set": {
                **fields_to_update,
                "updated_date": datetime.utcnow(),
                "updated_user": user,
            }
        }

        result = db_conn[DROPDOWN_COLLECTION].update_one(
            {"_id": oid, "tenant_id": tenant_id},
            update_payload
        )

        if result.modified_count > 0:
             add_activity(
                action_type="UPDATE_DROPDOWN_ITEM",
                user=user,
                details=f"Updated dropdown item ID: {item_id}. Changed fields: {list(fields_to_update.keys())}",
                document_id=oid,
                collection_name=DROPDOWN_COLLECTION,
                tenant_id=tenant_id
            )

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating dropdown {item_id} for tenant {tenant_id}: {e}")
        raise

def delete_dropdown(db_conn, item_id, user="System", tenant_id="default_tenant"):
    try:
        oid = ObjectId(item_id)

        item_to_delete = db_conn[DROPDOWN_COLLECTION].find_one({"_id": oid, "tenant_id": tenant_id})
        if not item_to_delete:
            return 0 # Item not found

        result = db_conn[DROPDOWN_COLLECTION].delete_one({"_id": oid, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            add_activity(
                action_type="DELETE_DROPDOWN_ITEM",
                user=user,
                details=f"Deleted dropdown item: Type='{item_to_delete.get('type')}', Label='{item_to_delete.get('label')}'",
                document_id=oid,
                collection_name=DROPDOWN_COLLECTION,
                tenant_id=tenant_id
            )
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting dropdown {item_id} for tenant {tenant_id}: {e}")
        raise

def get_dropdown_by_id(db_conn, item_id, tenant_id="default_tenant"):
    try:
        oid = ObjectId(item_id)
        return db_conn[DROPDOWN_COLLECTION].find_one({"_id": oid, "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching dropdown by ID {item_id} for tenant {tenant_id}: {e}")
        raise

def is_dropdown_locked(db_conn, item_id, tenant_id="default_tenant"):
    """Checks if a specific dropdown item is locked."""
    try:
        item = get_dropdown_by_id(db_conn, item_id, tenant_id)
        return item.get('is_locked', False) if item else False
    except Exception as e:
        logging.error(f"Error checking lock status for dropdown {item_id}: {e}")
        return False # Fail safe to prevent edits on error
