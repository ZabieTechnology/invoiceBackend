# db/gst_rate_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo
# Import functions from ca_tax_dal to manage related CA tax entries
from .ca_tax_dal import manage_ca_tax_entries_for_gst_rate, delete_ca_tax_entries_by_original_id
# Import activity logger
from .activity_log_dal import add_activity

GST_RATE_COLLECTION = 'gst_rates'

def create_gst_rate(gst_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new GST rate document in the database and manages related ca_tax entries and activity log.
    Calculates SGST and CGST if taxRate is provided. Handles "Cess" logic.
    """
    try:
        db = mongo.db
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

        gst_data['taxRate'] = rate # This is the main rate (or Cess rate)
        current_head = gst_data.get('head', 'General')

        if "cess" in current_head.lower():
            gst_data['sgstRate'] = 0
            gst_data['cgstRate'] = 0
            gst_data['igstRate'] = 0 # For Cess, IGST is typically not applicable in the same way, main rate is the Cess rate.
                                     # Or, if IGST should also be the cess rate for interstate, adjust logic here.
                                     # For now, assuming Cess is a distinct tax not split further.
        else:
            gst_data['igstRate'] = rate
            gst_data['sgstRate'] = rate / 2
            gst_data['cgstRate'] = rate / 2

        gst_data['taxName'] = gst_data.get('taxName', f"GST {rate}% ({current_head})")
        gst_data['head'] = current_head

        result = db[GST_RATE_COLLECTION].insert_one(gst_data)
        inserted_id = result.inserted_id
        logging.info(f"GST rate '{gst_data.get('taxName')}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            action_type="CREATE_GST_RATE",
            user=user,
            details=f"Created GST Rate: Name='{gst_data.get('taxName')}', Rate={rate}%, Head='{current_head}'",
            document_id=inserted_id,
            collection_name=GST_RATE_COLLECTION,
            tenant_id=tenant_id
        )

        if inserted_id:
            created_gst_rate_doc = db[GST_RATE_COLLECTION].find_one({"_id": inserted_id})
            if created_gst_rate_doc:
                manage_ca_tax_entries_for_gst_rate(created_gst_rate_doc, user, tenant_id)

        return inserted_id
    except Exception as e:
        logging.error(f"Error creating GST rate for tenant {tenant_id}: {e}")
        raise

def get_gst_rate_by_id(gst_id, tenant_id="default_tenant"):
    try:
        db = mongo.db
        return db[GST_RATE_COLLECTION].find_one({"_id": ObjectId(gst_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching GST rate by ID {gst_id} for tenant {tenant_id}: {e}")
        raise

def get_all_gst_rates(page=1, limit=25, filters=None, tenant_id="default_tenant"):
    try:
        db = mongo.db
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            gst_rates_cursor = db[GST_RATE_COLLECTION].find(query).sort("updated_date", -1).skip(skip).limit(limit)
        else:
            gst_rates_cursor = db[GST_RATE_COLLECTION].find(query).sort("updated_date", -1).skip(skip)

        gst_rate_list = list(gst_rates_cursor)
        total_items = db[GST_RATE_COLLECTION].count_documents(query)
        return gst_rate_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all GST rates for tenant {tenant_id}: {e}")
        raise

def update_gst_rate(gst_id, update_data, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        now = datetime.utcnow()
        original_id_obj = ObjectId(gst_id)
        update_data.pop('_id', None)

        update_payload_set = {
            **update_data,
            "updated_date": now,
            "updated_user": user
        }

        if 'taxRate' in update_payload_set:
            try:
                rate = float(update_payload_set['taxRate'])
            except (ValueError, TypeError):
                logging.warning(f"Invalid taxRate value for update in update_gst_rate, defaulting to 0.")
                rate = 0

            update_payload_set['taxRate'] = rate
            current_head = update_payload_set.get('head', 'General') # Get head from update_data or assume General

            if "cess" in current_head.lower():
                update_payload_set['sgstRate'] = 0
                update_payload_set['cgstRate'] = 0
                update_payload_set['igstRate'] = 0 # As above, assuming Cess is distinct
            else:
                update_payload_set['igstRate'] = rate
                update_payload_set['sgstRate'] = rate / 2
                update_payload_set['cgstRate'] = rate / 2

            if 'taxName' not in update_data or update_data.get('taxName', f"GST {rate}% ({current_head})") == f"GST {rate}% ({current_head})":
                 update_payload_set['taxName'] = f"GST {rate}% ({current_head})"

        result = db[GST_RATE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": update_payload_set}
        )

        if result.matched_count > 0:
            logging.info(f"GST rate {gst_id} updated by {user} for tenant {tenant_id}")
            add_activity(
                action_type="UPDATE_GST_RATE",
                user=user,
                details=f"Updated GST Rate ID: {gst_id}. Changed fields: {list(update_payload_set.keys())}",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            updated_gst_rate_doc = db[GST_RATE_COLLECTION].find_one({"_id": original_id_obj})
            if updated_gst_rate_doc:
                manage_ca_tax_entries_for_gst_rate(updated_gst_rate_doc, user, tenant_id)

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id} for tenant {tenant_id}: {e}")
        raise

def delete_gst_rate_by_id(gst_id, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        original_id_obj = ObjectId(gst_id)

        doc_to_delete = db[GST_RATE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('taxName', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        result = db[GST_RATE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"GST rate {gst_id} ('{doc_name}') deleted by {user} for tenant {tenant_id}.")
            add_activity(
                action_type="DELETE_GST_RATE",
                user=user,
                details=f"Deleted GST Rate: '{doc_name}' (ID: {gst_id})",
                document_id=original_id_obj,
                collection_name=GST_RATE_COLLECTION,
                tenant_id=tenant_id
            )
            delete_ca_tax_entries_by_original_id(original_id_obj, user, tenant_id)
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id} for tenant {tenant_id}: {e}")
        raise

def get_gst_tds_setting(tenant_id="default_tenant"):
    from .company_information_dal import get_company_information
    company_info = get_company_information(tenant_id=tenant_id)
    return company_info.get("gstTdsApplicable", "No") if company_info else "No"

def update_gst_tds_setting(is_applicable, user="System", tenant_id="default_tenant"):
    from .company_information_dal import COMPANY_INFO_COLLECTION as CI_COLLECTION
    try:
        db = mongo.db
        now = datetime.utcnow()
        company_info_doc = db[CI_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id": 1})
        doc_id_for_log = company_info_doc['_id'] if company_info_doc else None

        result = db[CI_COLLECTION].update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "gstTdsApplicable": "Yes" if is_applicable else "No",
                    "updated_date": now,
                    "updated_user": user
                },
                "$setOnInsert": {"created_date": now, "tenant_id": tenant_id}
            },
            upsert=True
        )
        if result.modified_count > 0 or result.upserted_id:
            action = "CREATE_COMPANY_INFO_WITH_GST_TDS" if result.upserted_id else "UPDATE_GST_TDS_SETTING"
            final_doc_id = result.upserted_id or doc_id_for_log
            if not final_doc_id:
                 refetched_doc = db[CI_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id":1})
                 final_doc_id = refetched_doc['_id'] if refetched_doc else None

            add_activity(action, user, f"Set GST TDS Applicable to {'Yes' if is_applicable else 'No'}", final_doc_id, CI_COLLECTION, tenant_id)
        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logging.error(f"Error updating GST TDS setting for tenant {tenant_id}: {e}")
        raise
