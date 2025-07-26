# db/gst_rate_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .activity_log_dal import add_activity
from .ca_tax_dal import manage_ca_tax_entries_for_gst_rate, delete_ca_tax_entries_by_original_id

GST_RATE_COLLECTION = 'gst_rates'
logging.basicConfig(level=logging.INFO)

def create_gst_rate(db_conn, gst_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new GST rate document in the database.
    """
    try:
        now = datetime.utcnow()
        payload = {**gst_data}
        payload.pop('_id', None)

        payload['created_date'] = now
        payload['updated_date'] = now
        payload['updated_user'] = user
        payload['tenant_id'] = tenant_id

        result = db_conn[GST_RATE_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"GST rate '{payload.get('taxName')}' created with ID: {inserted_id} by {user}")

        add_activity(
            action_type="CREATE_GST_RATE",
            user=user,
            details=f"Created GST Rate: Name='{payload.get('taxName')}', Rate={payload.get('taxRate')}%",
            document_id=inserted_id,
            collection_name=GST_RATE_COLLECTION,
            tenant_id=tenant_id
        )

        created_doc = db_conn[GST_RATE_COLLECTION].find_one({"_id": inserted_id})
        if created_doc:
            # Corrected function call with 3 arguments
            manage_ca_tax_entries_for_gst_rate(created_doc, user, tenant_id)

        return inserted_id
    except Exception as e:
        logging.error(f"Error creating GST rate: {e}")
        raise

def get_gst_rate_by_id(db_conn, gst_id, tenant_id="default_tenant"):
    """
    Fetches a single GST rate by its ID.
    """
    try:
        return db_conn[GST_RATE_COLLECTION].find_one({"_id": ObjectId(gst_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching GST rate by ID {gst_id}: {e}")
        raise

def get_all_gst_rates(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant"):
    """
    Fetches all GST rates with pagination and filtering.
    """
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            cursor = db_conn[GST_RATE_COLLECTION].find(query).sort("updated_date", -1).skip(skip).limit(limit)
        else:
            cursor = db_conn[GST_RATE_COLLECTION].find(query).sort("updated_date", -1)

        rate_list = list(cursor)
        total_items = db_conn[GST_RATE_COLLECTION].count_documents(query)
        return rate_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all GST rates with filters {filters}: {e}")
        raise

def update_gst_rate(db_conn, gst_id, update_data, user="System", tenant_id="default_tenant"):
    """
    Updates an existing GST rate by directly setting the provided data,
    without recalculating rates.
    """
    try:
        original_id_obj = ObjectId(gst_id)

        # Prepare payload from frontend data, removing immutable _id
        payload_to_set = {**update_data}
        payload_to_set.pop('_id', None)

        # Set update metadata
        payload_to_set["updated_date"] = datetime.utcnow()
        payload_to_set["updated_user"] = user

        # Perform the update
        result = db_conn[GST_RATE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0:
            logging.info(f"GST rate {gst_id} updated by {user}.")
            add_activity(
                action_type="UPDATE_GST_RATE",
                user=user,
                details=f"Updated GST Rate ID: {gst_id}. Changed fields: {list(payload_to_set.keys())}",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            # After updating, re-evaluate the derived tax accounts
            updated_doc = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj})
            if updated_doc:
                 # Corrected function call with 3 arguments
                 manage_ca_tax_entries_for_gst_rate(updated_doc, user, tenant_id)

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id}: {e}")
        raise


def delete_gst_rate_by_id(db_conn, gst_id, user="System", tenant_id="default_tenant"):
    """
    Deletes a GST rate by its ID.
    """
    try:
        original_id_obj = ObjectId(gst_id)

        doc_to_delete = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if not doc_to_delete:
            return 0

        doc_name = doc_to_delete.get('taxName', str(original_id_obj))

        result = db_conn[GST_RATE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"GST rate {gst_id} ('{doc_name}') deleted by {user}.")
            add_activity(
                action_type="DELETE_GST_RATE",
                user=user,
                details=f"Deleted GST Rate: '{doc_name}' (ID: {gst_id})",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            delete_ca_tax_entries_by_original_id(db_conn, original_id_obj, user, tenant_id)

        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id}: {e}")
        raise
