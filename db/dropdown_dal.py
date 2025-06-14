# db/dropdown_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re

from .activity_log_dal import add_activity

DROPDOWN_COLLECTION = 'dropdown'

logging.basicConfig(level=logging.INFO)

def get_dropdowns_paginated(db_conn, page=1, limit=25, type_filter=None, tenant_id="default_tenant"):
    try:
        query = {"tenant_id": tenant_id}
        if type_filter:
            query['type'] = type_filter

        if type_filter:
            dropdown_cursor = db_conn[DROPDOWN_COLLECTION].find(query).sort("label", 1)
            dropdown_list = list(dropdown_cursor)
            total_items = len(dropdown_list)
            return dropdown_list, total_items
        else:
            skip = (page - 1) * limit
            dropdown_cursor = db_conn[DROPDOWN_COLLECTION].find(query).sort("label", 1).skip(skip).limit(limit)
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
            "value": data.get("value"),
            "label": data.get("label"),
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }
        if not payload["type"] or not payload["value"] or not payload["label"]:
            raise ValueError("Dropdown 'type', 'value', and 'label' are required.")

        insert_result = db_conn[DROPDOWN_COLLECTION].insert_one(payload)

        # Corrected: Removed db_conn from add_activity call if it's not an expected parameter
        add_activity(
            action_type="CREATE_DROPDOWN_ITEM",
            user=user,
            details=f"Added dropdown: Type='{payload['type']}', Value='{payload['value']}', Label='{payload['label']}'",
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

        logging.info(f"Attempting to update dropdown item ID: {item_id} for tenant {tenant_id} with data: {data}")

        fields_to_update = {
            k: v for k, v in data.items() if k in ['label', 'value', 'type']
        }

        if not fields_to_update:
            logging.warning(f"No updatable fields (label, value, type) provided for dropdown item ID: {item_id}")
            return 0

        update_payload = {
            "$set": {
                **fields_to_update,
                "updated_date": datetime.utcnow(),
                "updated_user": user,
            }
        }

        logging.info(f"Constructed update payload for ID {item_id}: {update_payload}")

        result = db_conn[DROPDOWN_COLLECTION].update_one(
            {"_id": oid, "tenant_id": tenant_id},
            update_payload
        )

        if result.matched_count > 0:
            logging.info(f"Dropdown item {item_id} matched for update.")
            if result.modified_count > 0:
                logging.info(f"Dropdown item {item_id} updated successfully by {user}.")
                # Corrected: Removed db_conn from add_activity call
                add_activity(
                    action_type="UPDATE_DROPDOWN_ITEM",
                    user=user,
                    details=f"Updated dropdown item ID: {item_id}. Changed fields: {list(fields_to_update.keys())}",
                    document_id=oid,
                    collection_name=DROPDOWN_COLLECTION,
                    tenant_id=tenant_id
                )
            else:
                logging.info(f"Dropdown item {item_id} matched but no fields were modified (new values might be same as old).")
        else:
            logging.warning(f"No dropdown item found with ID {item_id} for tenant {tenant_id} to update.")

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating dropdown {item_id} for tenant {tenant_id}: {e}")
        raise

def delete_dropdown(db_conn, item_id, user="System", tenant_id="default_tenant"):
    try:
        oid = ObjectId(item_id)
        item_to_delete = db_conn[DROPDOWN_COLLECTION].find_one({"_id": oid, "tenant_id": tenant_id})
        result = db_conn[DROPDOWN_COLLECTION].delete_one({"_id": oid, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"Dropdown item {item_id} deleted by {user} for tenant {tenant_id}.")
            label = item_to_delete.get('label', 'N/A') if item_to_delete else 'N/A'
            value = item_to_delete.get('value', 'N/A') if item_to_delete else 'N/A'
            type_val = item_to_delete.get('type', 'N/A') if item_to_delete else 'N/A'
            # Corrected: Removed db_conn from add_activity call
            add_activity(
                action_type="DELETE_DROPDOWN_ITEM",
                user=user,
                details=f"Deleted dropdown item: Type='{type_val}', Value='{value}', Label='{label}' (ID: {item_id})",
                document_id=oid,
                collection_name=DROPDOWN_COLLECTION,
                tenant_id=tenant_id
            )
        else:
            logging.warning(f"No dropdown item found with ID {item_id} for tenant {tenant_id} to delete.")
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
