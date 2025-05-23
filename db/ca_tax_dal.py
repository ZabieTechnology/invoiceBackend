# db/ca_tax_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo
from .activity_log_dal import add_activity # Import activity logger

CA_TAX_COLLECTION = 'ca_tax'

def upsert_ca_tax_entry(tax_entry_data, user="System", tenant_id="default_tenant"):
    """
    Upserts a single CA tax entry and logs the activity.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        if not tax_entry_data.get('originalGstRateId') or not tax_entry_data.get('taxComponent'):
            logging.error("Missing originalGstRateId or taxComponent for CA tax entry upsert.")
            return None

        original_gst_id_obj = ObjectId(tax_entry_data['originalGstRateId'])

        filter_criteria = {
            "originalGstRateId": original_gst_id_obj,
            "taxComponent": tax_entry_data['taxComponent']
        }

        update_data = {
            **tax_entry_data,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id, # Assuming ca_tax entries are also tenanted
            "originalGstRateId": original_gst_id_obj # Ensure it's ObjectId
        }
        update_data.pop('_id', None)

        result = db[CA_TAX_COLLECTION].update_one(
            filter_criteria,
            {
                "$set": update_data,
                "$setOnInsert": {"created_date": now}
            },
            upsert=True
        )

        action_detail_prefix = f"CA Tax Entry ({tax_entry_data['taxComponent']}) for GST Rate ID {str(original_gst_id_obj)}"
        if result.upserted_id:
            logging.info(f"CA tax entry created with ID: {result.upserted_id}")
            add_activity("CREATE_CA_TAX_ENTRY", user, f"{action_detail_prefix} created: Name='{tax_entry_data.get('name')}', Rate={tax_entry_data.get('taxRate')}%", result.upserted_id, CA_TAX_COLLECTION, tenant_id)
            return result.upserted_id
        elif result.matched_count > 0:
            logging.info(f"CA tax entry updated for originalGstRateId {str(original_gst_id_obj)} and component {tax_entry_data['taxComponent']}")
            updated_doc = db[CA_TAX_COLLECTION].find_one(filter_criteria, {"_id": 1})
            doc_id = updated_doc['_id'] if updated_doc else None
            add_activity("UPDATE_CA_TAX_ENTRY", user, f"{action_detail_prefix} updated: Name='{tax_entry_data.get('name')}', Rate={tax_entry_data.get('taxRate')}%", doc_id, CA_TAX_COLLECTION, tenant_id)
            return doc_id
        return None

    except Exception as e:
        logging.error(f"Error upserting CA tax entry: {e}")
        raise

def manage_ca_tax_entries_for_gst_rate(gst_rate_doc, user="System", tenant_id="default_tenant"):
    """
    Creates or updates CA tax entries based on a gst_rates document.
    Handles special logic for "Cess".
    """
    if not gst_rate_doc or not gst_rate_doc.get('_id'):
        logging.error("Invalid gst_rate_doc provided to manage_ca_tax_entries_for_gst_rate.")
        return False

    original_gst_rate_id = gst_rate_doc['_id'] # This is already an ObjectId from the DB
    head = gst_rate_doc.get('head', 'N/A')
    base_code = gst_rate_doc.get('code', 'AUTO')
    main_tax_rate = gst_rate_doc.get('taxRate', 0)
    db = mongo.db # Define db instance

    # Check for "Cess" in head (case-insensitive)
    if "cess" in head.lower():
        cess_entry = {
            "code": f"{base_code}-CESS",
            "name": f"GST Cess @ {main_tax_rate}%",
            "taxType": "GST",
            "head": head,
            "taxRate": main_tax_rate,
            "taxComponent": "Cess",
            "originalGstRateId": original_gst_rate_id
        }
        upsert_ca_tax_entry(cess_entry, user, tenant_id)

        components_to_delete = ["SGST", "CGST", "IGST"]
        for comp in components_to_delete:
            delete_filter = {"originalGstRateId": original_gst_rate_id, "taxComponent": comp}
            deleted_info = db[CA_TAX_COLLECTION].delete_many(delete_filter)
            if deleted_info.deleted_count > 0:
                logging.info(f"Deleted {deleted_info.deleted_count} non-Cess component '{comp}' for GST Rate ID {original_gst_rate_id} due to head change.")
                add_activity("DELETE_CA_TAX_COMPONENT", user, f"Deleted non-Cess component '{comp}' for GST Rate ID {str(original_gst_rate_id)}", None, CA_TAX_COLLECTION, tenant_id)
    else:
        sgst_rate = gst_rate_doc.get('sgstRate', 0)
        sgst_entry = {
            "code": f"{base_code}-SGST",
            "name": f"{head} SGST @ {sgst_rate}%",
            "taxType": "GST", "head": head, "taxRate": sgst_rate,
            "taxComponent": "SGST", "originalGstRateId": original_gst_rate_id
        }
        upsert_ca_tax_entry(sgst_entry, user, tenant_id)

        cgst_rate = gst_rate_doc.get('cgstRate', 0)
        cgst_entry = {
            "code": f"{base_code}-CGST",
            "name": f"{head} CGST @ {cgst_rate}%",
            "taxType": "GST", "head": head, "taxRate": cgst_rate,
            "taxComponent": "CGST", "originalGstRateId": original_gst_rate_id
        }
        upsert_ca_tax_entry(cgst_entry, user, tenant_id)

        igst_rate = gst_rate_doc.get('igstRate', 0)
        igst_entry = {
            "code": f"{base_code}-IGST",
            "name": f"{head} IGST @ {igst_rate}%",
            "taxType": "GST", "head": head, "taxRate": igst_rate,
            "taxComponent": "IGST", "originalGstRateId": original_gst_rate_id
        }
        upsert_ca_tax_entry(igst_entry, user, tenant_id)

        delete_filter = {"originalGstRateId": original_gst_rate_id, "taxComponent": "Cess"}
        deleted_info = db[CA_TAX_COLLECTION].delete_many(delete_filter)
        if deleted_info.deleted_count > 0:
            logging.info(f"Deleted Cess component for GST Rate ID {original_gst_rate_id} due to head change.")
            add_activity("DELETE_CA_TAX_COMPONENT", user, f"Deleted Cess component for GST Rate ID {str(original_gst_rate_id)}", None, CA_TAX_COLLECTION, tenant_id)

    logging.info(f"Managed CA tax entries for GST Rate ID: {original_gst_rate_id}")
    return True

def delete_ca_tax_entries_by_original_id(original_gst_rate_id, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        if not isinstance(original_gst_rate_id, ObjectId):
            original_gst_rate_id = ObjectId(original_gst_rate_id)

        result = db[CA_TAX_COLLECTION].delete_many({"originalGstRateId": original_gst_rate_id})
        count = result.deleted_count
        logging.info(f"Deleted {count} CA tax entries for original GST Rate ID: {original_gst_rate_id}")
        if count > 0:
            add_activity("DELETE_CA_TAX_ENTRIES_BULK", user, f"Deleted {count} CA tax entries linked to GST Rate ID {str(original_gst_rate_id)}", original_gst_rate_id, CA_TAX_COLLECTION, tenant_id)
        return count
    except Exception as e:
        logging.error(f"Error deleting CA tax entries by original ID {original_gst_rate_id}: {e}")
        raise

def get_all_ca_tax_entries(page=1, limit=25, filters=None, tenant_id="default_tenant"):
    try:
        db = mongo.db
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            ca_tax_cursor = db[CA_TAX_COLLECTION].find(query).skip(skip).limit(limit)
        else:
            ca_tax_cursor = db[CA_TAX_COLLECTION].find(query).skip(skip)

        ca_tax_list = list(ca_tax_cursor)
        total_items = db[CA_TAX_COLLECTION].count_documents(query)
        return ca_tax_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all ca_tax entries for tenant {tenant_id}: {e}")
        raise
