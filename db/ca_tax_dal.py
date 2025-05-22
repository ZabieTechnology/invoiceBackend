# db/ca_tax_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo

CA_TAX_COLLECTION = 'ca_tax'

def upsert_ca_tax_entry(tax_entry_data, user="System"):
    """
    Upserts a single CA tax entry.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        if not tax_entry_data.get('originalGstRateId') or not tax_entry_data.get('taxComponent'):
            logging.error("Missing originalGstRateId or taxComponent for CA tax entry upsert.")
            return None

        filter_criteria = {
            "originalGstRateId": ObjectId(tax_entry_data['originalGstRateId']),
            "taxComponent": tax_entry_data['taxComponent']
        }

        update_data = {
            **tax_entry_data,
            "updated_date": now,
            "updated_user": user,
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

        if result.upserted_id:
            logging.info(f"CA tax entry created with ID: {result.upserted_id}")
            return result.upserted_id
        elif result.matched_count > 0:
            logging.info(f"CA tax entry updated for originalGstRateId {tax_entry_data['originalGstRateId']} and component {tax_entry_data['taxComponent']}")
            updated_doc = db[CA_TAX_COLLECTION].find_one(filter_criteria, {"_id": 1})
            return updated_doc['_id'] if updated_doc else None
        return None

    except Exception as e:
        logging.error(f"Error upserting CA tax entry: {e}")
        raise

def manage_ca_tax_entries_for_gst_rate(gst_rate_doc, user="System"):
    """
    Creates or updates the three CA tax entries (SGST, CGST, IGST)
    based on a given document from the gst_rates collection.
    """
    if not gst_rate_doc or not gst_rate_doc.get('_id'):
        logging.error("Invalid gst_rate_doc provided to manage_ca_tax_entries_for_gst_rate.")
        return False

    original_gst_rate_id = gst_rate_doc['_id']
    head = gst_rate_doc.get('head', 'N/A')
    base_code = gst_rate_doc.get('code', 'AUTO')

    sgst_rate = gst_rate_doc.get('sgstRate', 0)
    sgst_entry = {
        "code": f"{base_code}-SGST",
        "name": f"{head} SGST @ {sgst_rate}%",
        "taxType": "GST",
        "head": head,
        "taxRate": sgst_rate,
        "taxComponent": "SGST",
        "originalGstRateId": original_gst_rate_id
    }
    upsert_ca_tax_entry(sgst_entry, user)

    cgst_rate = gst_rate_doc.get('cgstRate', 0)
    cgst_entry = {
        "code": f"{base_code}-CGST",
        "name": f"{head} CGST @ {cgst_rate}%",
        "taxType": "GST",
        "head": head,
        "taxRate": cgst_rate,
        "taxComponent": "CGST",
        "originalGstRateId": original_gst_rate_id
    }
    upsert_ca_tax_entry(cgst_entry, user)

    igst_rate = gst_rate_doc.get('igstRate', 0)
    igst_entry = {
        "code": f"{base_code}-IGST",
        "name": f"{head} IGST @ {igst_rate}%",
        "taxType": "GST",
        "head": head,
        "taxRate": igst_rate,
        "taxComponent": "IGST",
        "originalGstRateId": original_gst_rate_id
    }
    upsert_ca_tax_entry(igst_entry, user)

    logging.info(f"Managed CA tax entries for GST Rate ID: {original_gst_rate_id}")
    return True


def delete_ca_tax_entries_by_original_id(original_gst_rate_id):
    """
    Deletes all CA tax entries linked to a specific originalGstRateId.
    """
    try:
        db = mongo.db
        # Ensure original_gst_rate_id is an ObjectId if it's passed as a string
        if not isinstance(original_gst_rate_id, ObjectId):
            original_gst_rate_id = ObjectId(original_gst_rate_id)

        result = db[CA_TAX_COLLECTION].delete_many({"originalGstRateId": original_gst_rate_id})
        logging.info(f"Deleted {result.deleted_count} CA tax entries for original GST Rate ID: {original_gst_rate_id}")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting CA tax entries by original ID {original_gst_rate_id}: {e}")
        raise

def get_all_ca_tax_entries(page=1, limit=25, filters=None): # Renamed from get_all_gst_rates for clarity
    """
    Fetches a paginated list of ca_tax entries, optionally filtered.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            ca_tax_cursor = db[CA_TAX_COLLECTION].find(query).skip(skip).limit(limit)
        else:
            ca_tax_cursor = db[CA_TAX_COLLECTION].find(query).skip(skip)

        ca_tax_list = list(ca_tax_cursor)
        total_items = db[CA_TAX_COLLECTION].count_documents(query)
        return ca_tax_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all ca_tax entries: {e}")
        raise
