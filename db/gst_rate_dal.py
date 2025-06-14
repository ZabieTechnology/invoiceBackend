# db/gst_rate_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re # For potential regex use if needed in filters

# Removed: from .database import mongo
# Assuming activity_log_dal.add_activity gets its db connection internally
from .activity_log_dal import add_activity
# Assuming ca_tax_dal functions also get their db connection internally or are passed it
from .ca_tax_dal import manage_ca_tax_entries_for_gst_rate, delete_ca_tax_entries_by_original_id

GST_RATE_COLLECTION = 'gst_rates'
logging.basicConfig(level=logging.INFO)

def create_gst_rate(db_conn, gst_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new GST rate document in the database.
    'db_conn' is the database connection instance.
    """
    try:
        now = datetime.utcnow()

        gst_data['created_date'] = now
        gst_data['updated_date'] = now
        gst_data['updated_user'] = user
        gst_data['tenant_id'] = tenant_id
        gst_data.pop('_id', None)

        try:
            rate = float(gst_data.get('taxRate', 0))
        except (ValueError, TypeError):
            logging.warning("Invalid taxRate value in create_gst_rate, defaulting to 0.")
            rate = 0

        gst_data['taxRate'] = rate
        current_head = gst_data.get('head', 'General') # Default head if not provided

        # Ensure head is a string before calling lower()
        if isinstance(current_head, str) and "cess" in current_head.lower():
            gst_data['sgstRate'] = 0.0
            gst_data['cgstRate'] = 0.0
            gst_data['igstRate'] = 0.0
        else:
            gst_data['igstRate'] = rate
            gst_data['sgstRate'] = rate / 2.0
            gst_data['cgstRate'] = rate / 2.0

        # Ensure taxName is set, defaulting if not provided
        gst_data['taxName'] = gst_data.get('taxName') or f"GST {rate}% ({current_head})"
        gst_data['head'] = current_head


        result = db_conn[GST_RATE_COLLECTION].insert_one(gst_data)
        inserted_id = result.inserted_id
        logging.info(f"GST rate '{gst_data.get('taxName')}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity( # Assuming add_activity gets db_conn internally or doesn't need it
            action_type="CREATE_GST_RATE",
            user=user,
            details=f"Created GST Rate: Name='{gst_data.get('taxName')}', Rate={rate}%, Head='{current_head}'",
            document_id=inserted_id,
            collection_name=GST_RATE_COLLECTION,
            tenant_id=tenant_id
        )

        if inserted_id:
            created_gst_rate_doc = db_conn[GST_RATE_COLLECTION].find_one({"_id": inserted_id, "tenant_id": tenant_id})
            if created_gst_rate_doc:
                # Assuming manage_ca_tax_entries_for_gst_rate takes db_conn if needed
                manage_ca_tax_entries_for_gst_rate(db_conn, created_gst_rate_doc, user, tenant_id)

        return inserted_id
    except Exception as e:
        logging.error(f"Error creating GST rate for tenant {tenant_id}: {e}")
        raise

def get_gst_rate_by_id(db_conn, gst_id, tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        return db_conn[GST_RATE_COLLECTION].find_one({"_id": ObjectId(gst_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching GST rate by ID {gst_id} for tenant {tenant_id}: {e}")
        raise

def get_all_gst_rates(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    'filters' dictionary can contain 'head' for filtering (e.g., with $regex for "output").
    """
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit is not None and limit > 0 else 0

        if limit is not None and limit > 0:
            gst_rates_cursor = db_conn[GST_RATE_COLLECTION].find(query).sort("updated_date", -1).skip(skip).limit(limit)
        else: # Fetch all if limit is not positive or None
            gst_rates_cursor = db_conn[GST_RATE_COLLECTION].find(query).sort("updated_date", -1).skip(skip)

        gst_rate_list = list(gst_rates_cursor)
        total_items = db_conn[GST_RATE_COLLECTION].count_documents(query)
        return gst_rate_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all GST rates for tenant {tenant_id} with filters {filters}: {e}")
        raise

def update_gst_rate(db_conn, gst_id, update_data, user="System", tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(gst_id)
        update_data.pop('_id', None)

        payload_to_set = {
            **update_data,
            "updated_date": now,
            "updated_user": user
        }

        if 'taxRate' in payload_to_set or 'head' in payload_to_set: # Recalculate if rate or head changes
            try:
                rate = float(payload_to_set.get('taxRate', 0)) # Use existing rate if not in payload_to_set
                if 'taxRate' not in payload_to_set: # If only head changed, get current rate
                    current_doc = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
                    if current_doc:
                        rate = float(current_doc.get('taxRate',0))

            except (ValueError, TypeError):
                logging.warning(f"Invalid taxRate value for update in update_gst_rate, defaulting to 0.")
                rate = 0

            payload_to_set['taxRate'] = rate
            current_head = payload_to_set.get('head', 'General')
            if not isinstance(current_head, str): # Ensure head is a string
                current_doc_for_head = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
                current_head = current_doc_for_head.get('head', 'General') if current_doc_for_head else 'General'


            if "cess" in current_head.lower():
                payload_to_set['sgstRate'] = 0.0
                payload_to_set['cgstRate'] = 0.0
                payload_to_set['igstRate'] = 0.0
            else:
                payload_to_set['igstRate'] = rate
                payload_to_set['sgstRate'] = rate / 2.0
                payload_to_set['cgstRate'] = rate / 2.0

            # Update taxName only if it's not explicitly provided in update_data or if it matches the old auto-generated format
            if 'taxName' not in update_data or (update_data.get('taxName') and update_data.get('taxName').startswith("GST ")):
                 payload_to_set['taxName'] = f"GST {rate}% ({current_head})"
            payload_to_set['head'] = current_head


        result = db_conn[GST_RATE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0:
            logging.info(f"GST rate {gst_id} updated by {user} for tenant {tenant_id}")
            add_activity( # Assuming add_activity gets db_conn internally
                action_type="UPDATE_GST_RATE",
                user=user,
                details=f"Updated GST Rate ID: {gst_id}. Changed fields: {list(payload_to_set.keys())}",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            updated_gst_rate_doc = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
            if updated_gst_rate_doc:
                manage_ca_tax_entries_for_gst_rate(db_conn, updated_gst_rate_doc, user, tenant_id) # Pass db_conn

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id} for tenant {tenant_id}: {e}")
        raise

def delete_gst_rate_by_id(db_conn, gst_id, user="System", tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        original_id_obj = ObjectId(gst_id)

        doc_to_delete = db_conn[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('taxName', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        result = db_conn[GST_RATE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"GST rate {gst_id} ('{doc_name}') deleted by {user} for tenant {tenant_id}.")
            add_activity( # Assuming add_activity gets db_conn internally
                action_type="DELETE_GST_RATE",
                user=user,
                details=f"Deleted GST Rate: '{doc_name}' (ID: {gst_id})",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            # Assuming delete_ca_tax_entries_by_original_id takes db_conn if needed
            delete_ca_tax_entries_by_original_id(db_conn, original_id_obj, user, tenant_id)
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id} for tenant {tenant_id}: {e}")
        raise

# --- GST TDS Setting Functions (Assuming they are part of this DAL) ---
# Note: These interact with a different collection (company_information),
# which might be better placed in company_information_dal.py if it exists.
# For now, keeping them here as per the provided file structure.

def get_gst_tds_setting(db_conn, tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    # This function needs to know the collection name for company_information
    # Assuming it's 'company_information' based on typical naming.
    # If you have a COMPANY_INFO_COLLECTION constant, use that.
    from .company_information_dal import COMPANY_INFO_COLLECTION # Import if defined there

    company_info = db_conn[COMPANY_INFO_COLLECTION].find_one({"tenant_id": tenant_id})
    return company_info.get("gstTdsApplicable", "No") if company_info else "No"

def update_gst_tds_setting(db_conn, is_applicable, user="System", tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    from .company_information_dal import COMPANY_INFO_COLLECTION # Import if defined there
    try:
        now = datetime.utcnow()
        company_info_doc = db_conn[COMPANY_INFO_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id": 1})
        doc_id_for_log = company_info_doc['_id'] if company_info_doc else None

        result = db_conn[COMPANY_INFO_COLLECTION].update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "gstTdsApplicable": "Yes" if is_applicable else "No",
                    "updated_date": now,
                    "updated_user": user
                },
                "$setOnInsert": {"created_date": now, "tenant_id": tenant_id} # Ensure tenant_id on insert
            },
            upsert=True
        )
        if result.modified_count > 0 or result.upserted_id:
            action = "CREATE_COMPANY_INFO_WITH_GST_TDS" if result.upserted_id else "UPDATE_GST_TDS_SETTING"
            final_doc_id = result.upserted_id or doc_id_for_log
            if not final_doc_id: # Refetch if it was an upsert and ID wasn't immediately available
                 refetched_doc = db_conn[COMPANY_INFO_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id":1})
                 final_doc_id = refetched_doc['_id'] if refetched_doc else None

            add_activity( # Assuming add_activity gets db_conn internally
                action_type=action,
                user=user,
                details=f"Set GST TDS Applicable to {'Yes' if is_applicable else 'No'}",
                document_id=final_doc_id,
                collection_name=COMPANY_INFO_COLLECTION,
                tenant_id=tenant_id
            )
        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logging.error(f"Error updating GST TDS setting for tenant {tenant_id}: {e}")
        raise
